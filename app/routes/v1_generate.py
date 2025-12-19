import uuid, os, logging, re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Tuple
from datetime import datetime
import uuid as python_uuid

from app.models import GenerateRequest, Profile, ProfileV3
from app.core.tailor import run_tailor
from app.core.tex_compile import render_tex, compile_tex, bundle_pdfs_only
from app.db.database import get_db
from app.db.models import User, Profile as DBProfile, Job as DBJob, Run as DBRun
from app.auth.auth import verify_token
from app.utils.analytics import (
    track_event, track_generation_metric, EventType,
    detect_jd_industry, detect_jd_role_type
)
from app.core.subscription import SUBSCRIPTION_LIVE
from datetime import timedelta

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


def sanitize_filename(text: str, max_length: int = 30) -> str:
    """Sanitize text for use in filenames - remove special chars, truncate"""
    # Remove or replace special characters
    clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', text)
    # Replace spaces with underscores
    clean = re.sub(r'\s+', '_', clean.strip())
    # Truncate if too long
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip('_')
    return clean or 'Unknown'


def generate_file_basename(user_name: str, company: str, job_title: str) -> str:
    """
    Generate a short, unique filename base.
    Format: Firstname_Lastname_Company_Year
    Example: John_Doe_Google_2025
    """
    # Parse user name
    name_parts = user_name.strip().split()
    if len(name_parts) >= 2:
        first_name = sanitize_filename(name_parts[0], 15)
        last_name = sanitize_filename(name_parts[-1], 15)
    elif len(name_parts) == 1:
        first_name = sanitize_filename(name_parts[0], 15)
        last_name = 'User'
    else:
        first_name = 'Resume'
        last_name = 'User'
    
    # Sanitize company name (short)
    company_clean = sanitize_filename(company, 20)
    
    # Current year
    year = datetime.now().year
    
    return f"{first_name}_{last_name}_{company_clean}_{year}"


def process_single_job(
    job_data: dict,
    profile_to_use,
    full_profile_v3,
    user_name: str,
    run_id: str
) -> Tuple[dict, float, float, float, bool, bool, any]:
    """
    Process a single job - designed to run in parallel.
    Returns: (artifact, llm_duration, tex_duration, pdf_duration, resume_success, cover_success, llm_output)
    """
    from app.models import JobJD
    
    j = JobJD(**job_data) if isinstance(job_data, dict) else job_data
    
    # Generate short filename
    base = generate_file_basename(user_name, j.company, j.title)
    # Add a short unique suffix to prevent collisions
    unique_suffix = run_id[:6]
    base = f"{base}_{unique_suffix}"
    
    # LLM processing
    llm_start = time.time()
    out = run_tailor(profile_to_use, j, full_profile_v3=full_profile_v3)
    llm_duration = time.time() - llm_start
    
    # TEX rendering
    tex_start = time.time()
    resume_ctx = {"profile": profile_to_use.model_dump(), "out": out.resume.model_dump(), "job": j.model_dump()}
    cover_letter_ctx = {"profile": profile_to_use.model_dump(), "out": out.cover_letter.model_dump(), "job": j.model_dump()}
    resume_tex_path, cover_letter_tex_path = render_tex(resume_ctx, cover_letter_ctx, j.region, base)
    tex_duration = time.time() - tex_start
    
    # PDF compilation
    pdf_start = time.time()
    resume_pdf_success = compile_tex(resume_tex_path)
    cover_letter_pdf_success = compile_tex(cover_letter_tex_path)
    pdf_duration = time.time() - pdf_start
    
    # Build artifact
    resume_pdf_path = resume_tex_path.replace('.tex', '.pdf')
    cover_letter_pdf_path = cover_letter_tex_path.replace('.tex', '.pdf')
    
    artifact = {
        "job_id": j.id or j.title,
        "company": j.company,
        "region": j.region,
        "resume_tex": f"/artifacts/{os.path.basename(resume_tex_path)}",
        "cover_letter_tex": f"/artifacts/{os.path.basename(cover_letter_tex_path)}",
        "created_at": datetime.now().isoformat(),
        "pdf_compilation": {
            "resume_success": resume_pdf_success,
            "cover_letter_success": cover_letter_pdf_success
        }
    }
    
    if resume_pdf_success and os.path.exists(resume_pdf_path):
        artifact["resume_pdf"] = f"/artifacts/{os.path.basename(resume_pdf_path)}"
    
    if cover_letter_pdf_success and os.path.exists(cover_letter_pdf_path):
        artifact["cover_letter_pdf"] = f"/artifacts/{os.path.basename(cover_letter_pdf_path)}"
    
    return (artifact, llm_duration, tex_duration, pdf_duration, resume_pdf_success, cover_letter_pdf_success, out)


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

    # Run tailor with FULL ProfileV3 for complete context
    try:
        out = run_tailor(legacy_profile, job_jd, full_profile_v3=profile_v3)
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
    full_profile_v3 = None  # Track full ProfileV3 for LLM context

    if user_id:
        # v1.3: Read profile from database for authenticated users
        logger.info("Authenticated user - loading profile from database")
        db_profile = db.query(DBProfile).filter(DBProfile.user_id == python_uuid.UUID(user_id)).first()

        if db_profile:
            full_profile_v3 = ProfileV3(**db_profile.profile_data)
            profile_to_use = convert_v3_profile_to_legacy(full_profile_v3)
            profile_version = db_profile.version
            logger.info(f"Loaded profile version {profile_version} from database")
            logger.info(f"Full profile has {len(full_profile_v3.certifications)} certifications, "
                        f"{len(full_profile_v3.awards)} awards, {len(full_profile_v3.languages)} languages")
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

    # Get user's name for file naming
    user_name = "Resume_User"  # Default
    if full_profile_v3 and full_profile_v3.basics:
        user_name = full_profile_v3.basics.full_name
    elif profile_to_use and hasattr(profile_to_use, 'name'):
        user_name = profile_to_use.name
    
    logger.info(f"User name for file naming: {user_name}")

    # Process ALL jobs CONCURRENTLY for maximum speed
    artifacts = []
    job_results = []  # Store results with their indices for DB persistence
    generation_start_time = time.time()
    
    # Prepare job data for concurrent processing
    job_data_list = [j.model_dump() for j in request.jobs]
    
    logger.info(f"Starting CONCURRENT processing of {len(request.jobs)} jobs")
    
    # Use ThreadPoolExecutor for concurrent I/O-bound operations (LLM calls)
    # This is the key for making 10 jobs feel fast - they all process simultaneously
    max_workers = min(len(request.jobs), 10)  # Max 10 concurrent LLM calls
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all jobs at once
        future_to_idx = {
            executor.submit(
                process_single_job,
                job_data_list[idx],
                profile_to_use,
                full_profile_v3,
                user_name,
                f"{run_id}_{idx}"  # Unique run_id per job
            ): idx
            for idx in range(len(request.jobs))
        }
        
        # Collect results as they complete
        completed_count = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            completed_count += 1
            try:
                result = future.result()
                artifact, llm_dur, tex_dur, pdf_dur, resume_ok, cover_ok, llm_output = result
                job_results.append({
                    'idx': idx,
                    'artifact': artifact,
                    'llm_duration': llm_dur,
                    'tex_duration': tex_dur,
                    'pdf_duration': pdf_dur,
                    'resume_success': resume_ok,
                    'cover_success': cover_ok,
                    'llm_output': llm_output,
                    'job': request.jobs[idx]
                })
                logger.info(f"Job {completed_count}/{len(request.jobs)} completed: {request.jobs[idx].company}")
            except Exception as e:
                logger.error(f"Job {idx} failed: {e}")
                # Track failed generation event
                if user_id:
                    track_event(
                        db=db,
                        event_type=EventType.GENERATION_ERROR,
                        user_id=user_id,
                        event_data={"job_title": request.jobs[idx].title, "company": request.jobs[idx].company, "error": str(e)}
                    )
                raise HTTPException(400, f"LLM/validation error for {request.jobs[idx].company}: {e}")
    
    # Sort results by original index to maintain order
    job_results.sort(key=lambda x: x['idx'])
    
    # Build artifacts list and persist runs
    for result in job_results:
        artifact = result['artifact']
        artifacts.append(artifact)
        
        # Persist Run for authenticated users
        if user_id and db_jobs:
            db_job = db_jobs[result['idx']]
            j = result['job']
            
            db_run = DBRun(
                user_id=python_uuid.UUID(user_id),
                job_id=db_job.id,
                status="completed",
                profile_version=profile_version,
                llm_output=result['llm_output'].model_dump(),
                artifacts_urls=artifact,
                created_at=datetime.utcnow()
            )
            db.add(db_run)
            db.flush()
            
            # Track generation metrics
            total_job_duration = result['llm_duration'] + result['tex_duration'] + result['pdf_duration']
            track_generation_metric(
                db=db,
                run_id=str(db_run.id),
                user_id=user_id,
                total_duration=total_job_duration,
                llm_duration=result['llm_duration'],
                tex_render_duration=result['tex_duration'],
                pdf_compile_duration=result['pdf_duration'],
                success=True,
                region=j.region,
                resume_pdf_success=result['resume_success'],
                cover_letter_pdf_success=result['cover_success'],
                jd_text_length=len(j.jd_text),
                keywords_matched_count=len(result['llm_output'].ats.jd_keywords_matched) if result['llm_output'].ats else 0,
                jd_industry=detect_jd_industry(j.jd_text),
                jd_role_type=detect_jd_role_type(j.jd_text, j.title)
            )

    # Commit all runs at once for authenticated users
    if user_id:
        db.commit()
        
        # Increment usage counter (only for successful generations, only if subscription is live)
        if SUBSCRIPTION_LIVE:
            user_uuid = python_uuid.UUID(user_id)
            user = db.query(User).filter(User.id == user_uuid).first()
            if user:
                # Initialize usage reset date if not set
                now = datetime.utcnow()
                if not user.usage_reset_at:
                    user.usage_reset_at = now + timedelta(days=30)
                elif user.usage_reset_at <= now:
                    # Reset if past reset date
                    user.monthly_generations_used = 0
                    user.usage_reset_at = now + timedelta(days=30)
                
                # Increment usage by number of successful jobs
                successful_count = len([r for r in results if r.get('resume_success') or r.get('cover_success')])
                user.monthly_generations_used = (user.monthly_generations_used or 0) + successful_count
                db.commit()
                logger.info(f"Usage updated: user={user_id}, added={successful_count}, total={user.monthly_generations_used}")
        
        # Track generation complete event
        total_duration = time.time() - generation_start_time
        track_event(
            db=db,
            event_type=EventType.GENERATION_COMPLETE,
            user_id=user_id,
            event_data={
                "run_id": run_id,
                "jobs_count": len(request.jobs),
                "total_duration": round(total_duration, 2)
            }
        )
    
    zip_path = bundle_pdfs_only(run_id, user_name)
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
