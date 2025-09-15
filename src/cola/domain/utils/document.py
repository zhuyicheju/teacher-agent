from langchain.text_splitter import RecursiveCharacterTextSplitter
from docx import Document
from pdfminer.high_level import extract_text


ALLOWED_EXTENSIONS = {'pdf', 'docx'}

def read_document(file_path: str):
    if file_path.endswith('.pdf'):
         return extract_text(file_path)
    elif file_path.endswith('.docx'):
        doc = Document(file_path)
        return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
    else:
        raise ValueError("Unsupported file format. Only PDF and Word files are supported.")

def split_document(content: str):
    separators = ["\n\n", "\n", "。", "！", "？", "；", "，", ",", " "]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=separators
    )
    segments = splitter.split_text(content)
    return [seg.strip() for seg in segments if seg.strip()]

def allowed_file(filename: str) -> bool:
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS