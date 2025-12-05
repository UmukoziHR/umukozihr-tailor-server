import uuid, os, logging
import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from app.models import GenerateRequest, Profile, ProfileV3
from app.core.tailor import run_tailor
from app.core.tex_compile import render_tex, compile_tex, bundle
from app.db.database import get_db
from app.db.models import User, Profile as DBProfile, Job as DBJob, Run as DBRun
from app.auth.auth import verify_token
from datetime import datetime
import uuid as python_uuid

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Optional auth - returns user_id if authenticated, None otherwise"""
    if not credentials:
        return None

    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        return None

    try:
        # Convert string UUID from JWT back to UUID object for database query
        user_id_str = payload["sub"]
        user_id_uuid = python_uuid.UUID(user_id_str)

        # Verify user exists
        user = db.query(User).filter(User.id == user_id_uuid).first()
        return str(user.id) if user else None
    except (ValueError, KeyError) as e:
        logger.error(f"Error processing user token: {e}")
        return None


def convert_v3_profile_to_legacy(profile_v3: ProfileV3) -> Profile:
    """Convert v1.3 ProfileV3 to legacy v1.2 Profile for tailor compatibility"""
    from app.models import Contact, Role, Education, Project

    # Convert experience
    legacy_experience = [
        Role(
            title=exp.title,
            company=exp.company,
            start=exp.start,
            end=exp.end,
            bullets=exp.bullets
        )
        for exp in profile_v3.experience
    ]

    # Convert education
    legacy_education = [
        Education(
            school=edu.school,
            degree=edu.degree,
            period=f"{edu.start} - {edu.end}" if edu.start and edu.end else ""
        )
        for edu in profile_v3.education
    ]

    # Convert projects
    legacy_projects = [
        Project(
            name=proj.name,
            stack=proj.stack,
            bullets=proj.bullets
        )
        for proj in profile_v3.projects
    ]

    # Convert skills (flatten from Skill objects to simple strings)
    legacy_skills = [skill.name for skill in profile_v3.skills]

    # Create legacy profile
    return Profile(
        name=profile_v3.basics.full_name,
        contacts=Contact(
            email=profile_v3.basics.email,
            phone=profile_v3.basics.phone,
            location=profile_v3.basics.location,
            links=profile_v3.basics.links
        ),
        summary=profile_v3.basics.summary,
        skills=legacy_skills,
        experience=legacy_experience,
        education=legacy_education,
        projects=legacy_projects
    )


def run_generation_for_job(db: Session, user_id: str, job: DBJob, profile_data: dict, profile_version: int) -> DBRun:
    """
    Helper function to run generation for a single job
    Used by both /generate and /history/{run_id}/regenerate endpoints
    """
    run_id = str(uuid.uuid4())
    logger.info(f"Running generation for job: {job.title} at {job.company}, run_id: {run_id}")

    # Convert profile data to ProfileV3, then to legacy Profile
    profile_v3 = ProfileV3(**profile_data)
    legacy_profile = convert_v3_profile_to_legacy(profile_v3)

    # Create JobJD from DBJob
    from app.models import JobJD
    job_jd = JobJD(
        id=job.title,
        region=job.region,
        company=job.company,
        title=job.title,
        jd_text=job.jd_text
    )

    # Run tailor
    try:
        out = run_tailor(legacy_profile, job_jd)
        logger.info(f"LLM processing completed for job: {job.title}")
    except Exception as e:
        logger.error(f"LLM/validation error for job {job.title}: {e}")
        raise HTTPException(400, f"LLM/validation error: {e}")

    # Render and compile
    base = f"{run_id}_{job.title.replace(' ', '_')}"
    resume_ctx = {"profile": legacy_profile.model_dump(), "out": out.resume.model_dump(), "job": job_jd.model_dump()}
    cover_letter_ctx = {"profile": legacy_profile.model_dump(), "out": out.cover_letter.model_dump(), "job": job_jd.model_dump()}

    resume_tex_path, cover_letter_tex_path = render_tex(resume_ctx, cover_letter_ctx, job.region, base)

    logger.info(f"Starting PDF compilation for job: {job.title}")
    resume_pdf_success = compile_tex(resume_tex_path)
    cover_letter_pdf_success = compile_tex(cover_letter_tex_path)

    # Build artifacts URLs
    artifacts_urls = {
        "resume_tex": f"/artifacts/{os.path.basename(resume_tex_path)}",
        "cover_letter_tex": f"/artifacts/{os.path.basename(cover_letter_tex_path)}",
        "pdf_compilation": {
            "resume_success": resume_pdf_success,
            "cover_letter_success": cover_letter_pdf_success
        }
    }

    resume_pdf_path = resume_tex_path.replace('.tex', '.pdf')
    cover_letter_pdf_path = cover_letter_tex_path.replace('.tex', '.pdf')

    if resume_pdf_success and os.path.exists(resume_pdf_path):
        artifacts_urls["resume_pdf"] = f"/artifacts/{os.path.basename(resume_pdf_path)}"

    if cover_letter_pdf_success and os.path.exists(cover_letter_pdf_path):
        artifacts_urls["cover_letter_pdf"] = f"/artifacts/{os.path.basename(cover_letter_pdf_path)}"

    # Create Run record
    db_run = DBRun(
        id=python_uuid.UUID(run_id),
        user_id=python_uuid.UUID(user_id),
        job_id=job.id,
        status="completed",
        profile_version=profile_version,
        llm_output=out.model_dump(),
        artifacts_urls=artifacts_urls,
        created_at=datetime.utcnow()
    )

    db.add(db_run)
    db.commit()
    db.refresh(db_run)

    return db_run


@router.post("/")
def generate(
    request: GenerateRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate documents
    - Authenticated users: Read profile from database, persist jobs and runs
    - Unauthenticated users: Use profile from request body (legacy v1.2 behavior)
    """
    run_id = str(uuid.uuid4())
    logger.info(f"Starting document generation for run_id: {run_id}")
    logger.info(f"User authenticated: {bool(user_id)}, Jobs count: {len(request.jobs)}")

    # Determine profile source
    profile_to_use = request.profile
    profile_version = None

    if user_id:
        # v1.3: Read profile from database for authenticated users
        logger.info("Authenticated user - loading profile from database")
        db_profile = db.query(DBProfile).filter(DBProfile.user_id == python_uuid.UUID(user_id)).first()

        if db_profile:
            profile_v3 = ProfileV3(**db_profile.profile_data)
            profile_to_use = convert_v3_profile_to_legacy(profile_v3)
            profile_version = db_profile.version
            logger.info(f"Loaded profile version {profile_version} from database")
        else:
            logger.error("No profile found in database for authenticated user")
            raise HTTPException(status_code=404, detail="Profile not found. Please complete onboarding first.")
    elif not request.profile:
        # Unauthenticated AND no profile in request
        logger.error("No profile provided and user not authenticated")
        raise HTTPException(status_code=400, detail="Profile required for unauthenticated requests")

    # Persist jobs for authenticated users
    db_jobs = []
    if user_id:
        for j in request.jobs:
            db_job = DBJob(
                user_id=python_uuid.UUID(user_id),
                company=j.company,
                title=j.title,
                jd_text=j.jd_text,
                region=j.region,
                created_at=datetime.utcnow()
            )
            db.add(db_job)
            db_jobs.append(db_job)
        db.commit()
        for db_job in db_jobs:
            db.refresh(db_job)

    # Process synchronously for all users
    artifacts = []
    for idx, j in enumerate(request.jobs):
        logger.info(f"Processing job: {j.id or j.title} for company: {j.company}")

        # Get corresponding DB job for authenticated users
        db_job = db_jobs[idx] if user_id and db_jobs else None

        try:
            out = run_tailor(profile_to_use, j)
            logger.info(f"LLM processing completed for job: {j.id or j.title}")
        except Exception as e:
            logger.error(f"LLM/validation error for job {j.id or j.title}: {e}")
            raise HTTPException(400, f"LLM/validation error: {e}")

        base = f"{run_id}_{(j.id or j.title).replace(' ', '_')}"
        resume_ctx = {"profile": profile_to_use.model_dump(), "out": out.resume.model_dump(), "job": j.model_dump()}
        cover_letter_ctx = {"profile": profile_to_use.model_dump(), "out": out.cover_letter.model_dump(), "job": j.model_dump()}

        resume_tex_path, cover_letter_tex_path = render_tex(resume_ctx, cover_letter_ctx, j.region, base)

        # Compile to PDFs - this is the primary goal
        logger.info(f"Starting PDF compilation for job: {j.id or j.title}")
        resume_pdf_success = compile_tex(resume_tex_path)
        cover_letter_pdf_success = compile_tex(cover_letter_tex_path)
        
        # Check PDF paths
        resume_pdf_path = resume_tex_path.replace('.tex', '.pdf')
        cover_letter_pdf_path = cover_letter_tex_path.replace('.tex', '.pdf')
        
        artifact = {
            "job_id": j.id or j.title,
            "region": j.region,
            "resume_tex": f"/artifacts/{os.path.basename(resume_tex_path)}",
            "cover_letter_tex": f"/artifacts/{os.path.basename(cover_letter_tex_path)}",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "pdf_compilation": {
                "resume_success": resume_pdf_success,
                "cover_letter_success": cover_letter_pdf_success
            }
        }
        
        # Add PDF download links if compilation succeeded
        if resume_pdf_success and os.path.exists(resume_pdf_path):
            artifact["resume_pdf"] = f"/artifacts/{os.path.basename(resume_pdf_path)}"
            logger.info(f"Resume PDF ready for download: {artifact['resume_pdf']}")
        else:
            logger.warning(f"Resume PDF compilation failed for job {j.id or j.title} - TEX file available")
            
        if cover_letter_pdf_success and os.path.exists(cover_letter_pdf_path):
            artifact["cover_letter_pdf"] = f"/artifacts/{os.path.basename(cover_letter_pdf_path)}"
            logger.info(f"Cover letter PDF ready for download: {artifact['cover_letter_pdf']}")
        else:
            logger.warning(f"Cover letter PDF compilation failed for job {j.id or j.title} - TEX file available")
        
        # Optional: Include TEX content for preview (but PDFs are the main goal)
        if os.path.exists(resume_tex_path):
            with open(resume_tex_path, 'r', encoding='utf-8') as f:
                content = f.read()
                artifact["resume_tex_content"] = content  # Full content as required by project specs
                artifact["resume_tex_preview"] = content[:1000] + "..." if len(content) > 1000 else content
        if os.path.exists(cover_letter_tex_path):
            with open(cover_letter_tex_path, 'r', encoding='utf-8') as f:
                content = f.read()
                artifact["cover_letter_tex_content"] = content  # Full content as required by project specs
                artifact["cover_letter_tex_preview"] = content[:1000] + "..." if len(content) > 1000 else content

        artifacts.append(artifact)

        # Persist Run for authenticated users
        if user_id and db_job:
            db_run = DBRun(
                user_id=python_uuid.UUID(user_id),
                job_id=db_job.id,
                status="completed",
                profile_version=profile_version,
                llm_output=out.model_dump(),
                artifacts_urls=artifact,
                created_at=datetime.utcnow()
            )
            db.add(db_run)

    # Commit all runs at once for authenticated users
    if user_id:
        db.commit()
    
    zip_path = bundle(run_id)
    logger.info(f"Document generation completed for run_id: {run_id}")
    logger.info(f"Generated {len(artifacts)} artifacts, bundle: {zip_path}")
    
    return {
        "run_id": run_id,  # Changed from "run" to "run_id" for frontend compatibility
        "run": run_id,     # Keep both for backward compatibility
        "artifacts": artifacts, 
        "zip": f"/artifacts/{os.path.basename(zip_path)}", 
        "authenticated": bool(user_id),
        "user_id": user_id,
        "status": "completed"  # Since we process synchronously, it's always completed
    }

@router.get("/status/{run_id}")
def get_generation_status(run_id: str, user_id: str = Depends(get_current_user)):
    """Get generation status - for frontend polling compatibility
    
    Since we process synchronously, this endpoint simulates async behavior
    by checking if artifacts exist for the given run_id.
    """
    logger.info(f"Status check requested for run_id: {run_id}")
    
    # Check if artifacts exist for this run_id in the artifacts directory
    artifacts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "artifacts"))
    
    # Look for files matching this run_id pattern
    matching_files = []
    if os.path.exists(artifacts_dir):
        for filename in os.listdir(artifacts_dir):
            if filename.startswith(run_id):
                matching_files.append(filename)
    
    if matching_files:
        # Process exists and completed - reconstruct artifacts list
        artifacts = []
        zip_file = None
        
        for filename in matching_files:
            if filename.endswith('.zip'):
                zip_file = f"/artifacts/{filename}"
            elif filename.endswith('.pdf'):
                # Group PDFs by job
                base_name = filename.replace(f"{run_id}_", "").replace('.pdf', '')
                # Handle both _cover and _cover_letter patterns
                job_id = base_name.split('_resume')[0].split('_cover')[0]
                
                # Find or create artifact for this job
                artifact = next((a for a in artifacts if a['job_id'] == job_id), None)
                if not artifact:
                    artifact = {
                        "job_id": job_id,
                        "region": "US",  # Default, could be extracted from filename
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                    artifacts.append(artifact)
                
                if 'resume' in filename:
                    artifact["resume_pdf"] = f"/artifacts/{filename}"
                elif 'cover' in filename:  # This will match both _cover and _cover_letter
                    artifact["cover_letter_pdf"] = f"/artifacts/{filename}"
        
        return {
            "status": "completed",
            "run_id": run_id,
            "artifacts": artifacts,
            "zip": zip_file,
            "message": "Documents generated successfully"
        }
    else:
        # No artifacts found - might be processing or failed
        return {
            "status": "processing",
            "run_id": run_id,
            "message": "Documents are being generated..."
        }
