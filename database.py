import sqlite3
import os

UPLOAD_FOLDER ="uploads"

def save_uploaded_file(uplaoaded_file, item_id):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file_path = os.path.join(UPLOAD_FOLDER, f"item{item_id}_{uplaoaded_file.name}")
    with open(file_path, "wb") as f:
        f.write(uplaoaded_file.getbuffer())
    return file_path

def save_uploaded_file_bytes(file_bytes, file_name, item_id):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file_path = os.path.join(UPLOAD_FOLDER, f"item{item_id}_{file_name}")
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return file_path

def get_connection():
    return sqlite3.connect("inventory.db")

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(""" 
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            purchase_date TEXT,
            price REAL,
            store TEXT,
            warranty_expiry TEXT,
            quantity INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            removed_date TEXT
    )
""")

     # Migration: add user_id column to items if it doesn't exist yet (multi-user support)
    cursor.execute("PRAGMA table_info(items)")
    columns = [col[1] for col in cursor.fetchall()]
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN user_id TEXT")


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repairs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        repair_date TEXT,
        description TEXT,
        cost REAL,
        repairer_name TEXT,
        repairer_contact TEXT,
        next_service_due TEXT,
        status TEXT DEFAULT 'completed',
        notes TEXT,
        FOREIGN KEY (item_id) REFERENCES items (id)
        )  
""")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            repair_id INTEGER,
            doc_type TEXT,
            file_path TEXT NOT NULL,
            file_name TEXT,
            uploaded_date TEXT,
            notes TEXT,
            FOREIGN KEY (item_id) REFERENCES items (id),
            FOREIGN KEY (repair_id) REFERENCES repairs (id)
        )
    """)
    
    cursor.execute("PRAGMA table_info(documents)")
    doc_columns = [col[1] for col in cursor.fetchall()]
    if "extracted_text" not in doc_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN extracted_text TEXT")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
    