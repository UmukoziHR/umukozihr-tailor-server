from celery import Celery
import os, uuid, logging
from datetime import datetime
from app.core.tailor import run_tailor
from app.core.tex_compile import render_tex, compile_tex, bundle
from app.db.database import SessionLocal
from app.db.models import Run
from app.storage.s3 import upload_to_s3
from app.models import Profile, JobJD

logger = logging.getLogger(__name__)

celery_app = Celery(
    'tasks',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

@celery_app.task
def process_generation(run_id: str, profile_data: dict, jobs_data: list):
    db = SessionLocal()
    run = db.query(Run).filter(Run.id == run_id).first()
    
    if not run:
        db.close()
        return {"error": "Run not found"}
    
    try:
        # update status using SQLAlchemy ORM
        db.query(Run).filter(Run.id == run_id).update({"status": "processing"})
        db.commit()
        
        # convert dicts back to models
        profile = Profile(**profile_data)
        jobs = [JobJD(**job_data) for job_data in jobs_data]
        
        # generate artifacts using your existing logic
        artifacts = []
        artifact_urls = {}
        
        for job in jobs:
            try:
                out = run_tailor(profile, job)
            except Exception as e:
                raise Exception(f"LLM/validation error: {e}")
            
            base = f"{run_id}_{(job.id or job.title).replace(' ', '_')}"
            resume_ctx = {"profile": profile.model_dump(), "out": out.resume.model_dump(), "job": job.model_dump()}
            cover_letter_ctx = {"profile": profile.model_dump(), "out": out.cover_letter.model_dump(), "job": job.model_dump()}

            resume_tex, cover_letter_tex = render_tex(resume_ctx, cover_letter_ctx, job.region, base)

            for path in (resume_tex, cover_letter_tex):
                compile_tex(path)
            
            # Check if PDFs were generated
            resume_pdf_path = os.path.join(os.path.dirname(resume_tex), os.path.basename(resume_tex).replace('.tex','.pdf'))
            cover_letter_pdf_path = os.path.join(os.path.dirname(cover_letter_tex), os.path.basename(cover_letter_tex).replace('.tex','.pdf'))
            
            artifact = {
                "job_id": job.id or job.title,
                "region": job.region,
                "resume_tex": f"/artifacts/{os.path.basename(resume_tex)}",
                "cover_letter_tex": f"/artifacts/{os.path.basename(cover_letter_tex)}",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            
            # Upload to S3 if configured, otherwise use local paths
            try:
                s3_resume_tex = upload_to_s3(resume_tex)
                s3_cover_tex = upload_to_s3(cover_letter_tex)
                artifact_urls[f"{job.id or job.title}_resume_tex"] = s3_resume_tex
                artifact_urls[f"{job.id or job.title}_cover_tex"] = s3_cover_tex
                
                if os.path.exists(resume_pdf_path):
                    artifact["resume_pdf"] = f"/artifacts/{os.path.basename(resume_tex).replace('.tex','.pdf')}"
                    s3_resume_pdf = upload_to_s3(resume_pdf_path)
                    artifact_urls[f"{job.id or job.title}_resume_pdf"] = s3_resume_pdf
                    
                if os.path.exists(cover_letter_pdf_path):
                    artifact["cover_letter_pdf"] = f"/artifacts/{os.path.basename(cover_letter_tex).replace('.tex','.pdf')}"
                    s3_cover_pdf = upload_to_s3(cover_letter_pdf_path)
                    artifact_urls[f"{job.id or job.title}_cover_pdf"] = s3_cover_pdf
                    
            except Exception as upload_error:
                logger.warning(f"S3 upload failed, using local paths: {upload_error}")
                # Keep local paths if S3 fails
                pass
                
            artifacts.append(artifact)
        
        # Create zip bundle
        zip_path = bundle(run_id)
        if zip_path:
            try:
                s3_zip_url = upload_to_s3(zip_path)
                artifact_urls["zip"] = s3_zip_url
            except Exception:
                artifact_urls["zip"] = f"/artifacts/{os.path.basename(zip_path)}"
        
        # update run with results using SQLAlchemy ORM
        db.query(Run).filter(Run.id == run_id).update({
            "status": "completed",
            "llm_output": {"artifacts": artifacts},
            "artifacts_urls": artifact_urls
        })
        db.commit()
        
        return {"status": "completed", "artifacts": artifacts, "artifact_urls": artifact_urls}
        
    except Exception as e:
        # update run with error using SQLAlchemy ORM
        db.query(Run).filter(Run.id == run_id).update({
            "status": "failed",
            "llm_output": {"error": str(e)}
        })
        db.commit()
        return {"error": str(e)}
    finally:
        db.close()