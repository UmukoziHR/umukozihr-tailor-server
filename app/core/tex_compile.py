import os, subprocess, zipfile, glob, datetime, logging
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template

# Setup logging
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # server/app
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
# Use ARTIFACTS_DIR env var if set, otherwise fallback to local path
ART_DIR = os.environ.get("ARTIFACTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "artifacts")))
os.makedirs(ART_DIR, exist_ok=True)

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(disabled_extensions=("tex",)),
    trim_blocks=True,
    lstrip_blocks=True,
)

REGION_RESUME_TEMPLATE: dict[str, str] = {
    "US": "resume_us.tex.j2",
    "EU": "resume_eu.tex.j2",
    "GL": "resume_global.tex.j2",
}

REGION_LETTER_TEMPLATE: dict[str, str] = {
    "US": "cover_letter_us.tex.j2",
    "EU": "cover_letter_eu.tex.j2",
    "GL": "cover_letter_global.tex.j2",
}

def render_tex(resume_ctx:dict, cl_ctx:dict, region:str, out_base:str):
    resume_template_name: str = REGION_RESUME_TEMPLATE.get(region, REGION_RESUME_TEMPLATE["GL"])
    cover_letter_template_name: str  = REGION_LETTER_TEMPLATE.get(region, REGION_LETTER_TEMPLATE["GL"])
    resume_template: Template = env.get_template(resume_template_name)
    cover_letter_template: Template  = env.get_template(cover_letter_template_name)
    tex_resume: str = resume_template.render(**resume_ctx)
    tex_cover_letter: str = cover_letter_template.render(**cl_ctx)
    resume_path: str = os.path.join(ART_DIR, f"{out_base}_resume.tex")
    cover_letter_path: str  = os.path.join(ART_DIR, f"{out_base}_cover.tex")
    open(resume_path, "w", encoding="utf-8").write(tex_resume)
    open(cover_letter_path,  "w", encoding="utf-8").write(tex_cover_letter)
    return resume_path, cover_letter_path

def _latexmk(cwd:str, fname:str):
    """Compile LaTeX using local latexmk"""
    result = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", fname],
        cwd=cwd, capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise Exception(f"latexmk failed with code {result.returncode}: {result.stderr}")
    return result

def _docker_latexmk(cwd:str, fname:str):
    """Compile LaTeX using Docker container (for local dev on Windows)"""
    # Convert Windows path to Docker-compatible format
    docker_path = cwd.replace('\\', '/').replace('C:', '/c')
    result = subprocess.run([
        "docker","run","--rm","-v",f"{docker_path}:/data","blang/latex:ctanfull",
        "latexmk","-pdf","-interaction=nonstopmode","-halt-on-error",fname
    ], capture_output=True, text=True, timeout=240)
    if result.returncode != 0:
        raise Exception(f"Docker latexmk failed with code {result.returncode}: {result.stderr}")
    return result


def compile_tex(tex_path:str) -> bool:
    """
    Compile LaTeX to PDF using native TeX Live. Returns True if successful, False otherwise.
    
    Compilation methods:
    1. Local latexmk (production on AWS with TeX Live installed)
    2. Docker latexmk (local dev fallback on Windows)
    """
    cwd = os.path.dirname(tex_path)
    fname = os.path.basename(tex_path)
    pdf_path = tex_path.replace('.tex', '.pdf')
    
    logger.info(f"Starting LaTeX compilation for {fname}")
    
    # Method 1: Try local latexmk (production - AWS has TeX Live installed)
    try:
        result = _latexmk(cwd, fname)
        if os.path.exists(pdf_path):
            logger.info(f"PDF compiled successfully with latexmk: {pdf_path}")
            return True
        else:
            logger.warning(f"latexmk completed but PDF not found: {pdf_path}")
    except Exception as e1:
        logger.info(f"Local latexmk not available: {type(e1).__name__}")
        
        # Method 2: Try Docker as fallback (local dev on Windows)
        try:
            logger.info(f"Attempting Docker compilation for {fname}")
            result = _docker_latexmk(cwd, fname)
            if os.path.exists(pdf_path):
                logger.info(f"PDF compiled successfully with Docker: {pdf_path}")
                return True
            else:
                logger.warning(f"Docker latexmk completed but PDF not found: {pdf_path}")
        except Exception as e2:
            logger.error(f"All compilation methods failed for {fname}")
            logger.error(f"Local latexmk: {e1}")
            logger.error(f"Docker: {e2}")
            logger.info(f"TEX source file available for manual compilation: {tex_path}")
    
    return False

def bundle(run_id:str):
    """Create ZIP bundle with PDFs prioritized - DEPRECATED, use bundle_pdfs_only"""
    return bundle_pdfs_only(run_id, "Resume_User")


def bundle_pdfs_only(run_id: str, user_name: str = "Resume_User"):
    """
    Create ZIP bundle with PDFs and DOCX files.
    Uses short, user-friendly naming: Firstname_Lastname_Resumes_Year.zip
    
    Includes:
    - PDF files (for ATS and print)
    - DOCX files (for user editing)
    """
    import re
    
    # Sanitize user name for filename
    name_parts = user_name.strip().split()
    if len(name_parts) >= 2:
        first = re.sub(r'[^a-zA-Z0-9]', '', name_parts[0])[:15]
        last = re.sub(r'[^a-zA-Z0-9]', '', name_parts[-1])[:15]
    elif len(name_parts) == 1:
        first = re.sub(r'[^a-zA-Z0-9]', '', name_parts[0])[:15]
        last = 'User'
    else:
        first = 'Resume'
        last = 'User'
    
    year = datetime.datetime.now().year
    zip_filename = f"{first}_{last}_Resumes_{year}.zip"
    zip_path = os.path.join(ART_DIR, zip_filename)
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add PDFs (primary output for ATS and print)
        pdf_files = glob.glob(os.path.join(ART_DIR, f"*{run_id}*.pdf")) + \
                    glob.glob(os.path.join(ART_DIR, f"{run_id}_*.pdf"))
        # Also look for files matching the new naming pattern
        all_pdfs = set()
        for pattern in [f"*{run_id[:6]}*.pdf", f"{run_id}_*.pdf"]:
            for f in glob.glob(os.path.join(ART_DIR, pattern)):
                all_pdfs.add(f)
        
        for f in all_pdfs:
            zf.write(f, arcname=os.path.basename(f))
            logger.info(f"Added PDF to bundle: {os.path.basename(f)}")
        
        # Add DOCX files (for user editing - key feature request)
        all_docx = set()
        for pattern in [f"*{run_id[:6]}*.docx", f"{run_id}_*.docx"]:
            for f in glob.glob(os.path.join(ART_DIR, pattern)):
                all_docx.add(f)
        
        for f in all_docx:
            zf.write(f, arcname=os.path.basename(f))
            logger.info(f"Added DOCX to bundle: {os.path.basename(f)}")
        
        # TEX files are intentionally NOT included to avoid Windows path length issues
        # Users can download them individually if needed
    
    logger.info(f"Bundle created: {zip_path} ({len(all_pdfs)} PDFs, {len(all_docx)} DOCX files)")
    return zip_path
