import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any

# Profile Schemas
class ProfileBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "Brazil"
    zip_code: Optional[str] = None
    cpf: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    resume_hosted_url: Optional[str] = None
    current_title: Optional[str] = None
    current_company: Optional[str] = None

class ProfileUpdate(ProfileBase):
    pass

class ProfileResponse(ProfileBase):
    id: int
    resume_path: Optional[str] = None
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

# SearchCriteria Schemas
class SearchCriteriaBase(BaseModel):
    name: str
    keywords: List[str]
    location: Optional[str] = None
    remote_only: bool = False
    date_posted_filter: str = "past_week"
    experience_levels: Optional[List[str]] = None
    blacklist_companies: List[str] = []
    blacklist_keywords: List[str] = []
    max_per_session: int = 10
    is_active: bool = True
    company: Optional[str] = None
    order: int = 0

class SearchCriteriaCreate(SearchCriteriaBase):
    pass

class SearchCriteriaResponse(SearchCriteriaBase):
    id: int
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

# Job Schemas
class JobResponse(BaseModel):
    id: int
    linkedin_id: str
    title: str
    company: str
    location: Optional[str] = None
    remote: Optional[bool] = None
    description: Optional[str] = None
    url: str
    easy_apply: bool
    posted_at: Optional[datetime.datetime] = None
    status: str
    discovered_at: datetime.datetime
    search_id: Optional[int] = None
    skip_reason: Optional[str] = None
    priority: int = 0
    connected_profiles: Optional[List[str]] = []
    model_config = ConfigDict(from_attributes=True)

class JobApprove(BaseModel):
    mode: Optional[str] = "review"

class JobSkip(BaseModel):
    reason: str

class BulkJobAction(BaseModel):
    job_ids: List[int]

# Application Schemas
class ApplicationResponse(BaseModel):
    id: int
    job_id: int
    status: str
    fields_filled: Optional[List[dict]] = None
    resume_used: Optional[str] = None
    submitted_at: datetime.datetime
    updated_at: datetime.datetime
    notes: Optional[str] = None
    job: Optional[JobResponse] = None
    model_config = ConfigDict(from_attributes=True)

class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

# QAEntry Schemas
class QAEntryBase(BaseModel):
    question: str
    answer: str
    field_type: str = "text"
    options_hash: Optional[str] = None
    notes: Optional[str] = None

class QAEntryCreate(QAEntryBase):
    pass

class QAEntryUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    field_type: Optional[str] = None
    options_hash: Optional[str] = None
    notes: Optional[str] = None

class QAEntryResponse(QAEntryBase):
    id: int
    normalized_question: str
    times_used: int
    last_used_at: Optional[datetime.datetime] = None
    source: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

# LogEntry Schemas
class LogEntryResponse(BaseModel):
    id: int
    session_id: str
    timestamp: datetime.datetime
    level: str
    category: str
    message: str
    company: Optional[str] = None
    job_title: Optional[str] = None
    job_url: Optional[str] = None
    job_id: Optional[int] = None
    extra: dict
    model_config = ConfigDict(from_attributes=True)

# Session Schemas
class SessionResponse(BaseModel):
    id: str
    status: str
    mode: str
    started_at: Optional[datetime.datetime] = None
    ended_at: Optional[datetime.datetime] = None
    jobs_found: int
    jobs_applied: int
    jobs_skipped: int
    jobs_failed: int
    popups_shown: int
    search_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

# Settings Schemas
class SettingResponse(BaseModel):
    key: str
    value: str
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

class SettingUpdate(BaseModel):
    value: str

class BotTask(BaseModel):
    type: str  # "process_queue" | "search"
    target: Optional[str] = None  # "all" | "prioritized"
    search_id: Optional[int] = None

class BotStartPayload(BaseModel):
    search_id: Optional[int] = None
    search_ids: Optional[List[int]] = None
    tasks: Optional[List[BotTask]] = None
    mode: str = "review"  # review | auto

class BotAnswerPayload(BaseModel):
    popup_id: str
    answer: Any
    save: bool = True


# RecruiterContact Schemas
class RecruiterContactBase(BaseModel):
    job_id: Optional[int] = None
    name: Optional[str] = None
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    websites: Optional[List[str]] = []
    connection_status: Optional[str] = "unknown"
    company: Optional[str] = None
    notes: Optional[str] = None

class RecruiterContactUpdate(BaseModel):
    name: Optional[str] = None
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    websites: Optional[List[str]] = None
    connection_status: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None

class RecruiterContactResponse(RecruiterContactBase):
    id: int
    discovered_at: datetime.datetime
    updated_at: datetime.datetime
    job: Optional[JobResponse] = None
    model_config = ConfigDict(from_attributes=True)

# ContactLog Schemas
class ContactLogResponse(BaseModel):
    id: int
    recruiter_id: Optional[int] = None
    job_id: Optional[int] = None
    template_id: Optional[int] = None
    type: str
    status: str
    subject: Optional[str] = None
    body: str
    sent_at: datetime.datetime
    is_non_connected: bool
    recruiter: Optional[RecruiterContactResponse] = None
    job: Optional[JobResponse] = None
    model_config = ConfigDict(from_attributes=True)

# MessageTemplate Schemas
class MessageTemplateBase(BaseModel):
    name: str
    language: str
    type: str
    subject: Optional[str] = None
    body: str
    is_active: bool = True

class MessageTemplateUpdate(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    type: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    is_active: Optional[bool] = None

class MessageTemplateResponse(MessageTemplateBase):
    id: int
    used_day: Optional[int] = 0
    used_week: Optional[int] = 0
    used_month: Optional[int] = 0
    used_all: Optional[int] = 0
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

class ConnectionStats(BaseModel):
    weekly_non_connected_sent: int
    weekly_non_connected_limit: int = 10

