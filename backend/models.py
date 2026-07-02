import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from backend.database import Base

class Profile(Base):
    __tablename__ = "profile"

    id = Column(Integer, primary_key=True, default=1)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, default="Brazil")
    zip_code = Column(String, nullable=True)
    cpf = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    portfolio_url = Column(String, nullable=True)
    current_title = Column(String, nullable=True)
    current_company = Column(String, nullable=True)
    resume_path = Column(String, nullable=True)
    resume_hosted_url = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class SearchCriteria(Base):
    __tablename__ = "search_criteria"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    keywords = Column(JSON, nullable=False)              # JSON List of strings
    location = Column(String, nullable=True)
    remote_only = Column(Boolean, default=False)
    date_posted_filter = Column(String, default="past_week")  # "any" | "past_day" | "past_week" | "past_month"
    experience_levels = Column(JSON, nullable=True)     # JSON List of strings
    blacklist_companies = Column(JSON, default=list)    # JSON List of strings
    blacklist_keywords = Column(JSON, default=list)     # JSON List of strings
    max_per_session = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    company = Column(String, nullable=True)
    order = Column(Integer, default=0)

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    linkedin_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    remote = Column(Boolean, nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String, nullable=False)
    easy_apply = Column(Boolean, default=True)
    posted_at = Column(DateTime, nullable=True)
    status = Column(String, default="discovered")  # discovered | queued | applying | applied | skipped | failed | review_pending
    discovered_at = Column(DateTime, default=datetime.datetime.utcnow)
    search_id = Column(Integer, ForeignKey("search_criteria.id"), nullable=True)
    skip_reason = Column(String, nullable=True)
    priority = Column(Integer, default=0)
    connected_profiles = Column(JSON, default=list)

    search_criteria = relationship("SearchCriteria")

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True)
    status = Column(String, default="submitted")  # submitted | viewed | responded | rejected | ghosted | withdrawn
    fields_filled = Column(JSON, nullable=True)    # JSON: [{label, value, source}]
    resume_used = Column(String, nullable=True)
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    notes = Column(Text, nullable=True)

    job = relationship("Job")

class QAEntry(Base):
    __tablename__ = "qa_bank"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text, nullable=False)
    normalized_question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    field_type = Column(String, default="text")  # text | select | number | radio | checkbox
    options_hash = Column(String, nullable=True)
    times_used = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    source = Column(String, default="user")      # user | imported
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    level = Column(String, nullable=False)     # success | info | warning | error | action | debug
    category = Column(String, nullable=False)  # auth | search | apply | qa | bot | system
    message = Column(Text, nullable=False)
    company = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    job_url = Column(String, nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    extra = Column(JSON, default=dict)

    job = relationship("Job")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)  # UUID
    status = Column(String, default="idle")  # idle | running | paused | waiting_user | stopped | finished
    mode = Column(String, default="review")  # review | auto
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    jobs_found = Column(Integer, default=0)
    jobs_applied = Column(Integer, default=0)
    jobs_skipped = Column(Integer, default=0)
    jobs_failed = Column(Integer, default=0)
    popups_shown = Column(Integer, default=0)
    search_id = Column(Integer, ForeignKey("search_criteria.id"), nullable=True)

    search_criteria = relationship("SearchCriteria")

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class RecruiterContact(Base):
    __tablename__ = "recruiter_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    name = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    websites = Column(JSON, default=list) # JSON List of strings
    connection_status = Column(String, default="unknown") # 1st, 2nd, 3rd, pending, unknown
    company = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    discovered_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    job = relationship("Job")


class ContactLog(Base):
    __tablename__ = "contact_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recruiter_id = Column(Integer, ForeignKey("recruiter_contacts.id"), nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    template_id = Column(Integer, ForeignKey("message_templates.id"), nullable=True)
    type = Column(String, nullable=False) # linkedin_message | email
    status = Column(String, default="sent") # sent | failed | pending_confirmation
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_non_connected = Column(Boolean, default=False)

    recruiter = relationship("RecruiterContact")
    job = relationship("Job")
    template = relationship("MessageTemplate")


class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    language = Column(String, nullable=False) # pt | en | es
    type = Column(String, nullable=False) # linkedin_message | email
    subject = Column(String, nullable=True) # only for email
    body = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


