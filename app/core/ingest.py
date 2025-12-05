from pydoc import doc
from typing import Any, List
from pypdf import PdfReader
from docx import Document

def text_from_pdf(path:str)->str:
    r: Any = PdfReader(path)
    return "\n".join([p.extract_text() or "" for p in r.pages])

def text_from_docx(path:str)->str:
    d: Any = Document(path)
    return "\n".join([p.text for p in d.paragraphs])

def text_from_txt(path:str)->str:
    with open(path, 'r', encoding='utf-8') as file:
        return file.read() 

def extract_text(file_type:str, path:str)->str:
    match file_type:
        case "pdf":
            return text_from_pdf(path)
        case "docx":
            return text_from_docx(path)
        case "txt":
            return text_from_txt(path)
        case _:
            raise ValueError(f"Unsupported file type: {file_type}")

# Later: parse into Profile fields; for now keep your form-based Profile and treat file upload optional.
