import os, subprocess, zipfile, glob, datetime, logging
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template

# Setup logging
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # server/app
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
# Use the same artifacts directory as main.py
ART_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "artifacts"))
os.makedirs(ART_DIR, exist_ok=True)

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(disabled_extensions=("tex",)),
    trim_blocks=True,
    lstrip_blocks=True,
)

REGION_RESUME_TEMPLATE: dict[str, str] = {
    "US": "resume_us_onepage.tex.j2",
    "EU": "resume_eu_twopage.tex.j2",
    "GL": "resume_gl_onepage.tex.j2",
}

REGION_LETTER_TEMPLATE: dict[str, str] = {
    "US": "cover_letter_simple.tex.j2",
    "EU": "cover_letter_simple.tex.j2",
    "GL": "cover_letter_standard_global.tex.j2",
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
    """Compile LaTeX using Docker container"""
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
    """Compile LaTeX to PDF. Returns True if successful, False otherwise."""
    cwd = os.path.dirname(tex_path)
    fname = os.path.basename(tex_path)
    pdf_path = tex_path.replace('.tex', '.pdf')
    
    logger.info(f"Starting LaTeX compilation for {fname}")
    
    # Try local latexmk first
    try:
        result = _latexmk(cwd, fname)
        if os.path.exists(pdf_path):
            logger.info(f"PDF compiled successfully with latexmk: {pdf_path}")
            return True
        else:
            logger.warning(f"latexmk completed but PDF not found: {pdf_path}")
    except Exception as e1:
        logger.warning(f"Local latexmk failed for {fname}: {e1}")
        
        # Try Docker as fallback
        try:
            logger.info(f"Attempting Docker compilation for {fname}")
            result = _docker_latexmk(cwd, fname)
            if os.path.exists(pdf_path):
                logger.info(f"PDF compiled successfully with Docker: {pdf_path}")
                return True
            else:
                logger.warning(f"Docker latexmk completed but PDF not found: {pdf_path}")
        except Exception as e2:
            logger.error(f"Both compilation methods failed for {fname}")
            logger.error(f"Local error: {e1}")
            logger.error(f"Docker error: {e2}")
            logger.info(f"TEX source file available for manual compilation: {tex_path}")
    
    return False

def bundle(run_id:str):
    """Create ZIP bundle with PDFs prioritized"""
    zip_path = os.path.join(ART_DIR, f"{run_id}_bundle.zip")
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # First, add PDFs (primary deliverables)
        pdf_files = glob.glob(os.path.join(ART_DIR, f"{run_id}_*.pdf"))
        for f in pdf_files:
            zf.write(f, arcname=os.path.basename(f))
            logger.info(f"Added PDF to bundle: {os.path.basename(f)}")
        
        # Then add TEX files (for manual compilation if needed)
        tex_files = glob.glob(os.path.join(ART_DIR, f"{run_id}_*.tex"))
        for f in tex_files:
            zf.write(f, arcname=os.path.basename(f))
            logger.info(f"Added TEX to bundle: {os.path.basename(f)}")
    
    logger.info(f"Bundle created: {zip_path} ({len(pdf_files)} PDFs, {len(tex_files)} TEX files)")
    return zip_path
