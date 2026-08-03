import sys
from pathlib import Path

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, ensure_db_ready, ManagedFile

def inspect_db():
    ensure_db_ready()
    db = SessionLocal()
    try:
        files = db.query(ManagedFile).all()
        print(f"Total uploaded files in database: {len(files)}")
        for idx, f in enumerate(files):
            print(f"\n--- File #{idx+1}: {f.file_name} ---")
            print(f"ID: {f.id}")
            print(f"Mime: {f.mime_type}")
            print(f"Size: {f.file_size} bytes")
            print(f"Extracted text length: {len(f.extracted_text) if f.extracted_text else None}")
            if f.extracted_text:
                print("First 300 characters of extracted text:")
                print(f.extracted_text[:300])
            else:
                print("WARNING: Extracted text is EMPTY or None!")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_db()
