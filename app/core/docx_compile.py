"""
DOCX Document Generator for UmukoziHR Resume Tailor
Generates editable Word documents alongside PDF output.

This allows users to make changes to their resumes and cover letters
after generation - a key feature request from user feedback.
"""

import os
import logging
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

logger = logging.getLogger(__name__)

# Use ARTIFACTS_DIR env var if set, otherwise fallback to local path
ART_DIR = os.environ.get("ARTIFACTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "artifacts")))
os.makedirs(ART_DIR, exist_ok=True)


def set_document_margins(doc, margin_inches=0.75):
    """Set document margins for all sections"""
    for section in doc.sections:
        section.top_margin = Inches(margin_inches)
        section.bottom_margin = Inches(margin_inches)
        section.left_margin = Inches(margin_inches)
        section.right_margin = Inches(margin_inches)


def add_horizontal_line(paragraph):
    """Add a horizontal line after a paragraph"""
    p = paragraph._p
    pPr = p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '000000')
    pBdr.append(bottom)
    pPr.append(pBdr)


def create_resume_docx(profile: dict, resume_out: dict, job: dict, out_path: str) -> str:
    """
    Create a professional resume DOCX document.
    
    Args:
        profile: User profile data (name, contacts, etc.)
        resume_out: LLM-generated resume content (summary, experience, etc.)
        job: Job details (company, title, region)
        out_path: Output file path (without extension)
    
    Returns:
        Path to the generated DOCX file
    """
    doc = Document()
    set_document_margins(doc, 0.75)
    
    # === HEADER: Name and Contact Info ===
    name_para = doc.add_paragraph()
    name_run = name_para.add_run(profile.get('name', 'Your Name'))
    name_run.bold = True
    name_run.font.size = Pt(18)
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Contact line
    contacts = profile.get('contacts', {})
    contact_parts = []
    if contacts.get('email'):
        contact_parts.append(contacts['email'])
    if contacts.get('phone'):
        contact_parts.append(contacts['phone'])
    if contacts.get('location'):
        contact_parts.append(contacts['location'])
    
    if contact_parts:
        contact_para = doc.add_paragraph()
        contact_para.add_run(' • '.join(contact_parts))
        contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_para.paragraph_format.space_after = Pt(6)
    
    # Links line
    links = contacts.get('links', [])
    if links:
        links_para = doc.add_paragraph()
        links_para.add_run(' | '.join(links[:3]))  # Max 3 links
        links_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        links_para.paragraph_format.space_after = Pt(12)
    
    # Add horizontal line
    hr_para = doc.add_paragraph()
    add_horizontal_line(hr_para)
    
    # === SUMMARY ===
    summary = resume_out.get('summary', '')
    if summary:
        summary_header = doc.add_paragraph()
        summary_run = summary_header.add_run('SUMMARY')
        summary_run.bold = True
        summary_run.font.size = Pt(11)
        summary_header.paragraph_format.space_before = Pt(12)
        summary_header.paragraph_format.space_after = Pt(4)
        
        summary_para = doc.add_paragraph()
        summary_para.add_run(summary)
        summary_para.paragraph_format.space_after = Pt(10)
    
    # === EXPERIENCE ===
    experience = resume_out.get('experience', [])
    if experience:
        exp_header = doc.add_paragraph()
        exp_run = exp_header.add_run('EXPERIENCE')
        exp_run.bold = True
        exp_run.font.size = Pt(11)
        exp_header.paragraph_format.space_before = Pt(12)
        exp_header.paragraph_format.space_after = Pt(4)
        
        for exp in experience:
            # Role title and company
            role_para = doc.add_paragraph()
            title_run = role_para.add_run(exp.get('title', 'Role'))
            title_run.bold = True
            role_para.add_run(' | ')
            role_para.add_run(exp.get('company', 'Company'))
            role_para.paragraph_format.space_before = Pt(8)
            role_para.paragraph_format.space_after = Pt(0)
            
            # Dates
            dates_para = doc.add_paragraph()
            start = exp.get('start', '')
            end = exp.get('end', 'Present')
            dates_para.add_run(f"{start} - {end}")
            dates_para.paragraph_format.space_after = Pt(4)
            
            # Bullets
            bullets = exp.get('bullets', [])
            for bullet in bullets:
                bullet_para = doc.add_paragraph(style='List Bullet')
                bullet_para.add_run(bullet)
                bullet_para.paragraph_format.space_after = Pt(2)
    
    # === EDUCATION ===
    education = resume_out.get('education', [])
    if education:
        edu_header = doc.add_paragraph()
        edu_run = edu_header.add_run('EDUCATION')
        edu_run.bold = True
        edu_run.font.size = Pt(11)
        edu_header.paragraph_format.space_before = Pt(12)
        edu_header.paragraph_format.space_after = Pt(4)
        
        for edu in education:
            edu_para = doc.add_paragraph()
            degree_run = edu_para.add_run(edu.get('degree', 'Degree'))
            degree_run.bold = True
            edu_para.add_run(f" - {edu.get('school', 'University')}")
            
            period = edu.get('period', '')
            if period:
                edu_para.add_run(f" ({period})")
            
            edu_para.paragraph_format.space_after = Pt(4)
    
    # === SKILLS ===
    skills = resume_out.get('skills', [])
    if skills:
        skills_header = doc.add_paragraph()
        skills_run = skills_header.add_run('SKILLS')
        skills_run.bold = True
        skills_run.font.size = Pt(11)
        skills_header.paragraph_format.space_before = Pt(12)
        skills_header.paragraph_format.space_after = Pt(4)
        
        skills_para = doc.add_paragraph()
        skills_para.add_run(' • '.join(skills))
        skills_para.paragraph_format.space_after = Pt(8)
    
    # === PROJECTS (if present) ===
    projects = resume_out.get('projects', [])
    if projects:
        proj_header = doc.add_paragraph()
        proj_run = proj_header.add_run('PROJECTS')
        proj_run.bold = True
        proj_run.font.size = Pt(11)
        proj_header.paragraph_format.space_before = Pt(12)
        proj_header.paragraph_format.space_after = Pt(4)
        
        for proj in projects:
            proj_para = doc.add_paragraph()
            name_run = proj_para.add_run(proj.get('name', 'Project'))
            name_run.bold = True
            
            stack = proj.get('stack', '')
            if stack:
                proj_para.add_run(f" ({stack})")
            
            proj_para.paragraph_format.space_after = Pt(2)
            
            # Project bullets
            for bullet in proj.get('bullets', []):
                bullet_para = doc.add_paragraph(style='List Bullet')
                bullet_para.add_run(bullet)
                bullet_para.paragraph_format.space_after = Pt(2)
    
    # === CERTIFICATIONS (if present) ===
    certifications = resume_out.get('certifications', [])
    if certifications:
        cert_header = doc.add_paragraph()
        cert_run = cert_header.add_run('CERTIFICATIONS')
        cert_run.bold = True
        cert_run.font.size = Pt(11)
        cert_header.paragraph_format.space_before = Pt(12)
        cert_header.paragraph_format.space_after = Pt(4)
        
        for cert in certifications:
            cert_para = doc.add_paragraph()
            cert_para.add_run(f"• {cert.get('name', 'Certification')}")
            issuer = cert.get('issuer', '')
            year = cert.get('year', '')
            if issuer or year:
                cert_para.add_run(f" - {issuer} ({year})" if issuer and year else f" - {issuer or year}")
    
    # === AWARDS (if present) ===
    awards = resume_out.get('awards', [])
    if awards:
        awards_header = doc.add_paragraph()
        awards_run = awards_header.add_run('AWARDS')
        awards_run.bold = True
        awards_run.font.size = Pt(11)
        awards_header.paragraph_format.space_before = Pt(12)
        awards_header.paragraph_format.space_after = Pt(4)
        
        for award in awards:
            award_para = doc.add_paragraph()
            award_para.add_run(f"• {award.get('name', 'Award')}")
            year = award.get('year', '')
            if year:
                award_para.add_run(f" ({year})")
    
    # === LANGUAGES (if present) ===
    languages = resume_out.get('languages', [])
    if languages:
        lang_header = doc.add_paragraph()
        lang_run = lang_header.add_run('LANGUAGES')
        lang_run.bold = True
        lang_run.font.size = Pt(11)
        lang_header.paragraph_format.space_before = Pt(12)
        lang_header.paragraph_format.space_after = Pt(4)
        
        lang_para = doc.add_paragraph()
        lang_texts = [f"{l.get('language', 'Language')} ({l.get('proficiency', 'Proficient')})" for l in languages]
        lang_para.add_run(' • '.join(lang_texts))
    
    # Save the document
    docx_path = f"{out_path}_resume.docx"
    doc.save(docx_path)
    logger.info(f"Resume DOCX created: {docx_path}")
    
    return docx_path


def create_cover_letter_docx(profile: dict, cover_letter_out: dict, job: dict, out_path: str) -> str:
    """
    Create a professional cover letter DOCX document.
    
    Args:
        profile: User profile data (name, contacts, etc.)
        cover_letter_out: LLM-generated cover letter content
        job: Job details (company, title, region)
        out_path: Output file path (without extension)
    
    Returns:
        Path to the generated DOCX file
    """
    doc = Document()
    set_document_margins(doc, 1.0)  # Standard letter margins
    
    # === SENDER INFO (top right) ===
    contacts = profile.get('contacts', {})
    
    # Name
    name_para = doc.add_paragraph()
    name_run = name_para.add_run(profile.get('name', 'Your Name'))
    name_run.bold = True
    name_run.font.size = Pt(12)
    name_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    # Contact details
    if contacts.get('email'):
        email_para = doc.add_paragraph()
        email_para.add_run(contacts['email'])
        email_para.paragraph_format.space_after = Pt(0)
    
    if contacts.get('phone'):
        phone_para = doc.add_paragraph()
        phone_para.add_run(contacts['phone'])
        phone_para.paragraph_format.space_after = Pt(0)
    
    if contacts.get('location'):
        loc_para = doc.add_paragraph()
        loc_para.add_run(contacts['location'])
    
    # Add some space
    doc.add_paragraph()
    
    # === DATE ===
    from datetime import datetime
    date_para = doc.add_paragraph()
    date_para.add_run(datetime.now().strftime("%B %d, %Y"))
    date_para.paragraph_format.space_after = Pt(12)
    
    # === RECIPIENT ===
    recipient_para = doc.add_paragraph()
    recipient_para.add_run("Hiring Manager")
    recipient_para.paragraph_format.space_after = Pt(0)
    
    company_para = doc.add_paragraph()
    company_para.add_run(job.get('company', 'Company Name'))
    company_para.paragraph_format.space_after = Pt(12)
    
    # === SUBJECT LINE ===
    subject_para = doc.add_paragraph()
    subject_run = subject_para.add_run(f"Re: Application for {job.get('title', 'Position')}")
    subject_run.bold = True
    subject_para.paragraph_format.space_after = Pt(12)
    
    # === GREETING ===
    # Use address field from LLM or default greeting
    greeting = cover_letter_out.get('address', 'Dear Hiring Manager,')
    greeting_para = doc.add_paragraph()
    greeting_para.add_run(greeting)
    greeting_para.paragraph_format.space_after = Pt(12)
    
    # === BODY CONTENT ===
    # The LLM outputs structured fields: intro, why_you, evidence, why_them, close
    # Combine them into a proper cover letter format
    
    # Introduction paragraph
    intro = cover_letter_out.get('intro', '')
    if intro:
        intro_para = doc.add_paragraph()
        intro_para.add_run(intro)
        intro_para.paragraph_format.space_after = Pt(10)
        intro_para.paragraph_format.line_spacing = 1.15
    
    # Why you're a great fit paragraph
    why_you = cover_letter_out.get('why_you', '')
    if why_you:
        why_para = doc.add_paragraph()
        why_para.add_run(why_you)
        why_para.paragraph_format.space_after = Pt(10)
        why_para.paragraph_format.line_spacing = 1.15
    
    # Evidence bullet points (key achievements)
    evidence = cover_letter_out.get('evidence', [])
    if evidence:
        for point in evidence:
            bullet_para = doc.add_paragraph(style='List Bullet')
            bullet_para.add_run(point)
            bullet_para.paragraph_format.space_after = Pt(4)
            bullet_para.paragraph_format.left_indent = Inches(0.25)
    
    # Why them paragraph (company-specific interest)
    why_them = cover_letter_out.get('why_them', '')
    if why_them:
        doc.add_paragraph()  # Add spacing after bullets
        why_them_para = doc.add_paragraph()
        why_them_para.add_run(why_them)
        why_them_para.paragraph_format.space_after = Pt(10)
        why_them_para.paragraph_format.line_spacing = 1.15
    
    # === CLOSING ===
    close_text = cover_letter_out.get('close', '')
    if close_text:
        close_para = doc.add_paragraph()
        close_para.add_run(close_text)
        close_para.paragraph_format.space_after = Pt(16)
        close_para.paragraph_format.line_spacing = 1.15
    
    # Closing salutation
    closing_para = doc.add_paragraph()
    closing_para.add_run("Sincerely,")
    closing_para.paragraph_format.space_after = Pt(24)
    
    # === SIGNATURE ===
    sig_para = doc.add_paragraph()
    sig_run = sig_para.add_run(profile.get('name', 'Your Name'))
    sig_run.bold = True
    
    # Save the document
    docx_path = f"{out_path}_cover.docx"
    doc.save(docx_path)
    logger.info(f"Cover letter DOCX created: {docx_path}")
    
    return docx_path


def render_docx(resume_ctx: dict, cl_ctx: dict, out_base: str) -> tuple:
    """
    Render both resume and cover letter as DOCX files.
    
    Args:
        resume_ctx: Context dict with 'profile', 'out' (resume), and 'job' keys
        cl_ctx: Context dict with 'profile', 'out' (cover letter), and 'job' keys
        out_base: Base filename (without extension)
    
    Returns:
        Tuple of (resume_docx_path, cover_letter_docx_path)
    """
    out_path = os.path.join(ART_DIR, out_base)
    
    try:
        resume_docx = create_resume_docx(
            profile=resume_ctx['profile'],
            resume_out=resume_ctx['out'],
            job=resume_ctx['job'],
            out_path=out_path
        )
    except Exception as e:
        logger.error(f"Failed to create resume DOCX: {e}")
        resume_docx = None
    
    try:
        cover_docx = create_cover_letter_docx(
            profile=cl_ctx['profile'],
            cover_letter_out=cl_ctx['out'],
            job=cl_ctx['job'],
            out_path=out_path
        )
    except Exception as e:
        logger.error(f"Failed to create cover letter DOCX: {e}")
        cover_docx = None
    
    return resume_docx, cover_docx
