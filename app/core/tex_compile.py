import os, subprocess, zipfile, glob, datetime, logging, re
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template

# Setup logging
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # server/app
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
# Use ARTIFACTS_DIR env var if set, otherwise fallback to local path
ART_DIR = os.environ.get("ARTIFACTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "artifacts")))
os.makedirs(ART_DIR, exist_ok=True)


def latex_escape(text):
    """
    Escape special LaTeX characters in text.
    Must escape: & % $ # _ { } ~ ^ \
    """
    if not isinstance(text, str):
        return text
    
    # Order matters! Escape backslash first, then others
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]
    
    for char, escaped in replacements:
        text = text.replace(char, escaped)
    
    return text


def latex_escape_dict(d):
    """Recursively escape all string values in a dict/list structure."""
    if isinstance(d, dict):
        return {k: latex_escape_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [latex_escape_dict(item) for item in d]
    elif isinstance(d, str):
        return latex_escape(d)
    else:
        return d


env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(disabled_extensions=("tex",)),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Add latex_escape filter to Jinja2 environment
env.filters['latex_escape'] = latex_escape

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
    # Escape all LaTeX special characters in the context data
    resume_ctx_escaped = latex_escape_dict(resume_ctx)
    cl_ctx_escaped = latex_escape_dict(cl_ctx)
    
    resume_template_name: str = REGION_RESUME_TEMPLATE.get(region, REGION_RESUME_TEMPLATE["GL"])
    cover_letter_template_name: str  = REGION_LETTER_TEMPLATE.get(region, REGION_LETTER_TEMPLATE["GL"])
    resume_template: Template = env.get_template(resume_template_name)
    cover_letter_template: Template  = env.get_template(cover_letter_template_name)
    tex_resume: str = resume_template.render(**resume_ctx_escaped)
    tex_cover_letter: str = cover_letter_template.render(**cl_ctx_escaped)
    resume_path: str = os.path.join(ART_DIR, f"{out_base}_resume.tex")
    cover_letter_path: str  = os.path.join(ART_DIR, f"{out_base}_cover.tex")
    open(resume_path, "w", encoding="utf-8").write(tex_resume)
    open(cover_letter_path,  "w", encoding="utf-8").write(tex_cover_letter)
    return resume_path, cover_letter_path

def compile_tex(tex_path: str) -> bool:
    """
    Compile LaTeX to PDF using native TeX Live (latexmk).
    TeX Live is installed in the Docker image - this is our standard compilation method.
    """
    import shutil
    
    cwd = os.path.dirname(tex_path)
    fname = os.path.basename(tex_path)
    pdf_path = tex_path.replace('.tex', '.pdf')
    
    # Check if latexmk is available
    latexmk_path = shutil.which('latexmk')
    if not latexmk_path:
        logger.error("latexmk not found in PATH! PDF compilation impossible.")
        logger.error(f"Current PATH: {os.environ.get('PATH', 'NOT SET')}")
        return False
    
    logger.info(f"Compiling {fname} with latexmk at {latexmk_path}...")
    logger.info(f"Working directory: {cwd}")
    
    try:
        result = subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", fname],
            cwd=cwd, capture_output=True, text=True, timeout=120
        )
        
        if result.returncode != 0:
            logger.error(f"latexmk failed for {fname} (return code: {result.returncode})")
            logger.error(f"STDOUT (last 1000 chars): {result.stdout[-1000:] if result.stdout else 'None'}")
            logger.error(f"STDERR (last 1000 chars): {result.stderr[-1000:] if result.stderr else 'None'}")
            
            # Try to find and log the .log file for more details
            log_file = tex_path.replace('.tex', '.log')
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    log_content = f.read()
                    # Find error lines
                    error_lines = [l for l in log_content.split('\n') if '!' in l or 'Error' in l]
                    if error_lines:
                        logger.error(f"LaTeX errors: {error_lines[:10]}")
            return False
        
        if os.path.exists(pdf_path):
            logger.info(f"PDF compiled successfully: {pdf_path}")
            return True
        else:
            logger.error(f"latexmk completed but PDF not found: {pdf_path}")
            logger.error(f"Files in {cwd}: {os.listdir(cwd)}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"latexmk timed out after 120s for {fname}")
        return False
    except Exception as e:
        logger.error(f"Exception during latexmk execution: {type(e).__name__}: {e}")
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
