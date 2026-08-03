import sys
from pathlib import Path

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, ensure_db_ready, ManagedFile
from app.services.vision_service import VisionService
from config.paths import get_paths

def reprocess_files():
    ensure_db_ready()
    db = SessionLocal()
    paths = get_paths()
    try:
        files = db.query(ManagedFile).all()
        print(f"Reprocessing {len(files)} files...")
        for idx, f in enumerate(files):
            # Resolve physical path
            uploads_dir = paths.data_dir / "uploads"
            disk_matches = list(uploads_dir.glob(f"{f.id}_*"))
            disk_path = disk_matches[0] if disk_matches else None
            
            if disk_path and disk_path.is_file():
                print(f"Reprocessing file {f.file_name} at path {disk_path}...")
                vision_res = VisionService().analyze_file(str(disk_path), mime_type=f.mime_type)
                if vision_res.get("success") and vision_res.get("context"):
                    f.extracted_text = vision_res["context"]
                    db.commit()
                    print(f"SUCCESS! Reprocessed {f.file_name}, extracted text length = {len(f.extracted_text)}")
                else:
                    print(f"FAILED to reprocess {f.file_name}: {vision_res.get('error', 'unknown error')}")
            else:
                print(f"File {f.file_name} does not exist on disk at {disk_path}!")
    finally:
        db.close()

if __name__ == "__main__":
    reprocess_files()
