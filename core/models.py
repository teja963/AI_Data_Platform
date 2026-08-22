from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, UniqueConstraint, LargeBinary
from datetime import datetime
from core.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    full_name = Column(String)
    email = Column(String, unique=True)
    phone_number = Column(String)
    role = Column(String, default="user") # 'admin' or 'user'
    is_approved = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    otp_secret = Column(String, nullable=True)
    otp_code = Column(String, nullable=True) # For email/phone verification
    otp_expiry = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSectionAccess(Base):
    __tablename__ = "user_section_access"
    __table_args__ = (
        UniqueConstraint("user_id", "section", name="uq_user_section_access"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    section = Column(String)
    allowed = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LoginEvent(Base):
    __tablename__ = "login_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String)
    logged_in_at = Column(DateTime, default=datetime.utcnow)

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    module = Column(String)
    category = Column(String)
    difficulty = Column(String)
    # store raw JSON payload of the question for fidelity
    payload = Column(Text)
    # legacy fields for compatibility
    question = Column(Text)
    solution = Column(Text)


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (
        UniqueConstraint("user_id", "track", "question_key", name="uq_progress_user_track_question"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    question_id = Column(Integer, nullable=True)
    track = Column(String, default="sql")
    question_key = Column(String)
    status = Column(String)  # solved / unsolved
    attempts = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CodingSubmission(Base):
    __tablename__ = "coding_submissions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String)
    track = Column(String)
    question_key = Column(String)
    question_title = Column(String)
    correct = Column(Boolean, default=False)
    elapsed_ms = Column(Integer, default=0)
    code = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)


class VirtualKubernetesLab(Base):
    __tablename__ = "virtual_kubernetes_labs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String, unique=True, nullable=False)
    state_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PracticeLabState(Base):
    __tablename__ = "practice_lab_states"
    __table_args__ = (
        UniqueConstraint("username", "lab_key", name="uq_practice_lab_user_key"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String, nullable=False)
    lab_key = Column(String, nullable=False)
    state_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InterviewRun(Base):
    __tablename__ = "interview_runs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    score = Column(Integer)
    accuracy = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserActivitySummary(Base):
    __tablename__ = "user_activity_summary"
    __table_args__ = (
        UniqueConstraint("user_id", "section", name="uq_activity_user_section"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    section = Column(String)
    total_seconds = Column(Integer, default=0)
    visit_count = Column(Integer, default=0)
    last_seen = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserActivityDaily(Base):
    __tablename__ = "user_activity_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "section", "activity_date", name="uq_activity_user_section_date"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    section = Column(String)
    activity_date = Column(String)
    total_seconds = Column(Integer, default=0)
    visit_count = Column(Integer, default=0)
    last_seen = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SectionPerformanceDaily(Base):
    __tablename__ = "section_performance_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "section", "activity_date", name="uq_perf_user_section_date"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    section = Column(String)
    activity_date = Column(String)
    render_count = Column(Integer, default=0)
    total_ms = Column(Integer, default=0)
    max_ms = Column(Integer, default=0)
    last_ms = Column(Integer, default=0)
    last_seen = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QueryPerformanceDaily(Base):
    __tablename__ = "query_performance_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "track", "activity_date", name="uq_query_perf_user_track_date"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    track = Column(String)
    activity_date = Column(String)
    run_count = Column(Integer, default=0)
    total_ms = Column(Integer, default=0)
    max_ms = Column(Integer, default=0)
    last_ms = Column(Integer, default=0)
    last_seen = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ArchitectureDiagram(Base):
    __tablename__ = "architecture_diagrams"

    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(Text, nullable=True)
    file_name = Column(String)
    content_type = Column(String, nullable=True)
    file_data = Column(LargeBinary)
    source_url = Column(String, nullable=True)
    collection = Column(String, default="architecture")
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobPosting(Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_job_source_external_id"),
    )

    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)
    external_id = Column(String, nullable=False)
    company = Column(String, nullable=False)
    title = Column(String, nullable=False)
    location = Column(Text, nullable=True)
    work_mode = Column(String, nullable=True)
    department = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    job_url = Column(Text, nullable=False)
    posted_at = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    match_score = Column(Integer, default=0, nullable=False)
    match_reason = Column(Text, nullable=True)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserJobState(Base):
    __tablename__ = "user_job_states"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_job_state"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_postings.id"), nullable=False)
    status = Column(String, default="new", nullable=False)
    first_notified_at = Column(DateTime, nullable=True)
    last_viewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobScanRun(Base):
    __tablename__ = "job_scan_runs"

    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default="running", nullable=False)
    discovered_count = Column(Integer, default=0, nullable=False)
    matched_count = Column(Integer, default=0, nullable=False)
    inserted_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)


class ApplicationProfile(Base):
    __tablename__ = "application_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_application_profile_user"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    encrypted_profile = Column(LargeBinary, nullable=False)
    resume_filename = Column(String, nullable=True)
    encrypted_resume = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApplicationSiteCredential(Base):
    __tablename__ = "application_site_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "site_host", name="uq_application_credential_site"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    site_host = Column(String, nullable=False)
    encrypted_credentials = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApplicationDraft(Base):
    __tablename__ = "application_drafts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_postings.id"), nullable=False)
    status = Column(String, default="queued", nullable=False)
    source = Column(String, nullable=False)
    official_url = Column(Text, nullable=False)
    encrypted_result = Column(LargeBinary, nullable=True)
    artifact_dir = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    submission_approved_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)