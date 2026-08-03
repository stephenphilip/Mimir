import sys
from pathlib import Path

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypdf import PdfReader
# import pytesseract
from PIL import Image

def debug_pdf():
    pdf_path = Path("data/uploads/5aeeca72-568b-45e0-8e38-48d3828248a9_Stephen_BA_Resume (2).pdf")
    if not pdf_path.exists():
        print(f"Error: File {pdf_path} does not exist!")
        return

    print("--- 1. Testing native text extraction ---")
    try:
        reader = PdfReader(str(pdf_path))
        print(f"Total pages: {len(reader.pages)}")
        for idx, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            print(f"Page {idx+1} native text length: {len(txt)}")
            print(f"First 100 chars of page {idx+1} native text: {repr(txt[:100])}")
            print(f"Page {idx+1} images count: {len(page.images)}")
            for img_idx, img in enumerate(page.images):
                print(f"  - Image {img_idx+1}: name={img.name}, size={len(img.data)} bytes")
    except Exception as e:
        print(f"Failed native extraction: {e}")

    print("\n--- 2. Testing direct Tesseract OCR fallback ---")
    try:
        import pytesseract
        print("Pytesseract loaded successfully.")
    except Exception as e:
        print(f"Pytesseract import failed: {e}")

if __name__ == "__main__":
    debug_pdf()
