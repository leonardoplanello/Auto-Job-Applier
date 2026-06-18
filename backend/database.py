import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Resolve data directory absolute path (e.g. e:\1CODE\Auto_job_applier_linkedIn\user_data)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "user_data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "sessions"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "user_files"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "qa"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "exports"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "jobs"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "logs"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "logs", "screenshots"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "applications"), exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "app.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def run_migrations():
    import sqlite3
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Migrate jobs table
            cursor.execute("PRAGMA table_info(jobs)")
            job_columns = [row[1] for row in cursor.fetchall()]
            if job_columns and "priority" not in job_columns:
                cursor.execute("ALTER TABLE jobs ADD COLUMN priority INTEGER DEFAULT 0")
                conn.commit()
                
            # Migrate search_criteria table
            cursor.execute("PRAGMA table_info(search_criteria)")
            sc_columns = [row[1] for row in cursor.fetchall()]
            if sc_columns and "location" not in sc_columns:
                cursor.execute("ALTER TABLE search_criteria ADD COLUMN location TEXT")
                conn.commit()
                
            if sc_columns and "company" not in sc_columns:
                cursor.execute("ALTER TABLE search_criteria ADD COLUMN company TEXT")
                conn.commit()
                
            if sc_columns and "order" not in sc_columns:
                cursor.execute("ALTER TABLE search_criteria ADD COLUMN \"order\" INTEGER DEFAULT 0")
                conn.commit()
                
                # If locations column exists, migrate data from locations to location
                if "locations" in sc_columns:
                    cursor.execute("SELECT id, locations FROM search_criteria")
                    rows = cursor.fetchall()
                    for sc_id, locs_json in rows:
                        if locs_json:
                            try:
                                import json
                                locs = json.loads(locs_json)
                                if isinstance(locs, list) and len(locs) > 0:
                                    first_loc = locs[0]
                                    cursor.execute("UPDATE search_criteria SET location = ? WHERE id = ?", (first_loc, sc_id))
                            except Exception as e:
                                print(f"Error migrating location for id {sc_id}: {e}")
                    conn.commit()
        except Exception as e:
            print(f"Migration error: {e}")
        finally:
            conn.close()

run_migrations()

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
