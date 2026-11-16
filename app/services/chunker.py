#切分：固定窗口 500+10% overlap
import re

def _clean(text: str)->str:
    text = text.replace("\r\n","\n").replace("\r","\n")
    text = text.replace("\u3000"," ")
    text = re.sub(r"\t+", " ", text)
    text = re.sub(r"\n\s*\n","\n",text)
    return text.strip()

def _find_break(text: str,start: int,end: int)->int:
    low = start+(end-start)//2
    for sep in ("\n","。","！","？","，","："):
        idx = text.rfind(sep,low,end)
        if idx!=-1:
            return idx+1
    return end

def chunk_text(text: str,chunk_size: int=500,overlap: int=50)->list[str]:
    if not (0 <= overlap < chunk_size):
        raise ValueError("overlap must be in [0, chunk_size)")
    text = _clean(text)
    chunks = []
    start = 0
    n = len(text)
    while start<n:
        end = min(start+chunk_size,n)
        if end<n:
            end = _find_break(text,start,end)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end>=n:
            break
        start = max(end - overlap,start+1)
    return chunks