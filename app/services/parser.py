#解析：按扩展名路由->纯文本
import io

from docx import Document
from pypdf import PdfReader


def parse(filename:str,data:bytes):
    ext = filename.rsplit(".",1)[-1].lower()
    if ext not in ("pdf","docx","md","txt"):
        raise RuntimeError(f"暂不支持的文件类型：{ext}")
    try:
        if ext == "pdf":
            reader = PdfReader(io.BytesIO(data))
            text_parts=[]
            for page in reader.pages:
                text_parts.append(page.extract_text())
            full_text = "\n".join(text_parts)
            return  full_text
        elif ext == "docx":
            doc = Document(io.BytesIO(data))
            text_parts = []
            for p in doc.paragraphs:
                if p.text.strip():
                    text_parts.append(p.text)
            full_text = "\n".join(text_parts)
            return full_text
        else:
            return data.decode("utf-8",errors="ignore")
    except Exception as e:
        raise RuntimeError(f"解析{filename}失败，{e}") from e
