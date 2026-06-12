"""用 pypdf 提取 PDF 文本 → 存为 markdown"""
import sys
import os
from pathlib import Path

# 用 ai-tutor 的 venv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from pypdf import PdfReader
except ImportError:
    print("pypdf not available, trying pdfminer...")
    from pdfminer.high_level import extract_text
    USE_PDFMINER = True
else:
    USE_PDFMINER = False

PDF_PATH = r"C:\Users\yhn\Desktop\v2026 5.2-3图的连通性和矩阵表示.pdf"
OUT_PATH = r"C:\Users\yhn\Desktop\ai-tutor\data\图的连通性和矩阵表示.md"

def extract_with_pypdf(path):
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        pages.append(f"## 第 {i+1} 页\n\n{text}")
    return "\n\n".join(pages)

def extract_with_pdfminer(path):
    text = extract_text(path)
    return text

def main():
    print(f"正在提取: {PDF_PATH}")
    
    if USE_PDFMINER:
        text = extract_with_pdfminer(PDF_PATH)
    else:
        text = extract_with_pypdf(PDF_PATH)
    
    out = Path(OUT_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    
    size_kb = len(text) / 1024
    lines = text.count("\n")
    print(f"✅ 提取完成! → {out}")
    print(f"   大小: {size_kb:.1f} KB, {lines} 行")

if __name__ == "__main__":
    main()
