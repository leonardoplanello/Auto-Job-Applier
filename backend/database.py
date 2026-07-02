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
            if job_columns and "connected_profiles" not in job_columns:
                cursor.execute("ALTER TABLE jobs ADD COLUMN connected_profiles JSON")
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
            
            # Migrate profile table
            cursor.execute("PRAGMA table_info(profile)")
            profile_columns = [row[1] for row in cursor.fetchall()]
            if profile_columns and "resume_hosted_url" not in profile_columns:
                cursor.execute("ALTER TABLE profile ADD COLUMN resume_hosted_url TEXT")
                conn.commit()

            # Migrate contact_logs table
            cursor.execute("PRAGMA table_info(contact_logs)")
            cl_columns = [row[1] for row in cursor.fetchall()]
            if cl_columns and "template_id" not in cl_columns:
                cursor.execute("ALTER TABLE contact_logs ADD COLUMN template_id INTEGER")
                conn.commit()

            # Migrate message_templates table
            cursor.execute("PRAGMA table_info(message_templates)")
            mt_columns = [row[1] for row in cursor.fetchall()]
            if mt_columns and "is_active" not in mt_columns:
                cursor.execute("ALTER TABLE message_templates ADD COLUMN is_active BOOLEAN DEFAULT 1")
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


def seed_default_templates():
    from backend.models import MessageTemplate
    db = SessionLocal()
    try:
        if db.query(MessageTemplate).count() == 0:
            templates = [
                MessageTemplate(
                    name="LinkedIn Message (Portuguese)",
                    language="pt",
                    type="linkedin_message",
                    body="Olá, {recruiter_name}. Acabei de me candidatar à vaga de {job} na {company} e gostaria de reforçar meu interesse. Possuo experiência relevante e gostaria de me conectar. Abraço!"
                ),
                MessageTemplate(
                    name="Email (Portuguese)",
                    language="pt",
                    type="email",
                    subject="Candidatura: {job} - {candidate_name}",
                    body="Prezado(a) {recruiter_name},\n\nEspero que este e-mail o(a) encontre bem.\n\nEscrevo para expressar meu interesse na vaga de {job} na {company}, para a qual acabei de me candidatar através do LinkedIn.\n\nVocê pode visualizar meu currículo atualizado por meio deste link:\n{resume_link}\n\nFico à disposição para conversar e compartilhar mais detalhes.\n\nAtenciosamente,\n{candidate_name}"
                ),
                MessageTemplate(
                    name="LinkedIn Message (English)",
                    language="en",
                    type="linkedin_message",
                    body="Hi {recruiter_name}, I just applied for the {job} position at {company} and wanted to express my enthusiasm. I'd love to connect and share how my background fits the role. Best!"
                ),
                MessageTemplate(
                    name="Email (English)",
                    language="en",
                    type="email",
                    subject="Application: {job} - {candidate_name}",
                    body="Dear {recruiter_name},\n\nI hope this email finds you well.\n\nI am writing to express my strong interest in the {job} position at {company}, which I recently applied for via LinkedIn.\n\nYou can review my updated resume here:\n{resume_link}\n\nI look forward to the possibility of discussing this opportunity further.\n\nBest regards,\n{candidate_name}"
                )
            ]
            db.add_all(templates)
            db.commit()
    except Exception as e:
        print(f"Seeding error: {e}")
    finally:
        db.close()

