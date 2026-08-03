import sqlite3
import os

db_path = 'data/assistant.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE model_catalog SET score_reasoning=65.0, score_conversational=85.0 WHERE name='llama3.2:1b'")
    conn.commit()
    conn.close()
    print("Updated data/assistant.db")
else:
    print(f"DB not found at {db_path}")
