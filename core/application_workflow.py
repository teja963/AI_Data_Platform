import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import case

from core.db import Base, SessionLocal, engine
from core.models import (
    ApplicationDraft,
    ApplicationProfile,
    ApplicationSiteCredential,
    JobPosting,
    User,
)


APPLICATION_ENCRYPTION_KEY_ENV = "APP_DATA_ENCRYPTION_KEY"
_APPLICATION_SCHEMA_READY = False


def ensure_application_schema():
    global _APPLICATION_SCHEMA_READY
    if _APPLICATION_SCHEMA_READY:
        return
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ApplicationProfile.__table__,
            ApplicationSiteCredential.__table__,
            ApplicationDraft.__table__,
        ],
    )
    _APPLICATION_SCHEMA_READY = True


def _encryption_key():
    key = os.getenv(APPLICATION_ENCRYPTION_KEY_ENV, "").strip()
    if not key:
        try:
            import streamlit as st

            key = str(st.secrets.get(APPLICATION_ENCRYPTION_KEY_ENV, "")).strip()
        except Exception:
            key = ""
    if not key:
        raise RuntimeError(
            f"{APPLICATION_ENCRYPTION_KEY_ENV} is required to store applicant data."
        )
    return key.encode("utf-8")


def encryption_configured():
    try:
        Fernet(_encryption_key())
        return True
    except (RuntimeError, ValueError):
        return False


def _fernet():
    try:
        return Fernet(_encryption_key())
    except ValueError as error:
        raise RuntimeError(
            f"{APPLICATION_ENCRYPTION_KEY_ENV} is not a valid Fernet key."
        ) from error


def _encrypt_json(value):
    payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
    return _fernet().encrypt(payload)


def _decrypt_json(value):
    if not value:
        return {}
    try:
        return json.loads(_fernet().decrypt(bytes(value)).decode("utf-8"))
    except InvalidToken as error:
        raise RuntimeError(
            "Applicant data cannot be decrypted with the configured encryption key."
        ) from error


def _encrypt_bytes(value):
    return _fernet().encrypt(value) if value else None


def _decrypt_bytes(value):
    if not value:
        return None
    try:
        return _fernet().decrypt(bytes(value))
    except InvalidToken as error:
        raise RuntimeError(
            "Resume cannot be decrypted with the configured encryption key."
        ) from error


def load_application_profile(username, include_resume=False):
    ensure_application_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return {}
        row = session.query(ApplicationProfile).filter_by(user_id=user.id).first()
        if row:
            profile = _decrypt_json(row.encrypted_profile)
            profile["_resume_filename"] = row.resume_filename or ""
            if include_resume:
                profile["_resume_bytes"] = _decrypt_bytes(row.encrypted_resume)
            return profile
        return {
            "full_name": user.full_name or "",
            "email": user.email or "",
            "phone": user.phone_number or "",
            "_resume_filename": "",
        }
    finally:
        session.close()


def save_application_profile(
    username,
    profile,
    resume_filename=None,
    resume_bytes=None,
):
    ensure_application_schema()
    clean_profile = {
        key: str(value or "").strip()
        for key, value in (profile or {}).items()
        if not key.startswith("_")
    }
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            raise ValueError("User account was not found.")
        row = session.query(ApplicationProfile).filter_by(user_id=user.id).first()
        if row is None:
            row = ApplicationProfile(
                user_id=user.id,
                encrypted_profile=_encrypt_json(clean_profile),
            )
            session.add(row)
        else:
            row.encrypted_profile = _encrypt_json(clean_profile)
        if resume_bytes is not None:
            row.resume_filename = (resume_filename or "resume.pdf")[:255]
            row.encrypted_resume = _encrypt_bytes(resume_bytes)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _site_host(site_url):
    value = str(site_url or "").strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower().strip(".")
    if not host or "." not in host:
        raise ValueError("Enter a valid career-site URL or hostname.")
    return host


def save_site_credential(username, site_url, login_email, password):
    if not str(login_email or "").strip() or not str(password or ""):
        raise ValueError("Login email and password are required.")
    ensure_application_schema()
    host = _site_host(site_url)
    encrypted = _encrypt_json(
        {
            "login_email": str(login_email).strip(),
            "password": str(password),
        }
    )
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            raise ValueError("User account was not found.")
        row = (
            session.query(ApplicationSiteCredential)
            .filter_by(user_id=user.id, site_host=host)
            .first()
        )
        if row is None:
            row = ApplicationSiteCredential(
                user_id=user.id,
                site_host=host,
                encrypted_credentials=encrypted,
            )
            session.add(row)
        else:
            row.encrypted_credentials = encrypted
        session.commit()
        return host
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_site_credentials(username):
    ensure_application_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return []
        rows = (
            session.query(ApplicationSiteCredential)
            .filter_by(user_id=user.id)
            .order_by(ApplicationSiteCredential.site_host.asc())
            .all()
        )
        result = []
        for row in rows:
            credentials = _decrypt_json(row.encrypted_credentials)
            result.append(
                {
                    "id": row.id,
                    "site_host": row.site_host,
                    "login_email": credentials.get("login_email", ""),
                    "updated_at": row.updated_at,
                }
            )
        return result
    finally:
        session.close()


def delete_site_credential(username, credential_id):
    ensure_application_schema()
    session = SessionLocal()
    try:
        row = (
            session.query(ApplicationSiteCredential)
            .join(User, User.id == ApplicationSiteCredential.user_id)
            .filter(
                ApplicationSiteCredential.id == credential_id,
                User.username == username,
            )
            .first()
        )
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def queue_application_draft(username, job_id):
    ensure_application_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        job = session.query(JobPosting).filter_by(id=job_id).first()
        if not user or not job:
            raise ValueError("User or job was not found.")
        profile = session.query(ApplicationProfile).filter_by(user_id=user.id).first()
        if not profile:
            raise ValueError("Save your encrypted Application Profile first.")
        active = (
            session.query(ApplicationDraft)
            .filter(
                ApplicationDraft.user_id == user.id,
                ApplicationDraft.job_id == job.id,
                ApplicationDraft.status.in_(
                    (
                        "queued",
                        "preparing",
                        "approved_for_submission",
                        "submitting",
                    )
                ),
            )
            .order_by(ApplicationDraft.id.desc())
            .first()
        )
        if active:
            return active.id
        draft = ApplicationDraft(
            user_id=user.id,
            job_id=job.id,
            status="queued",
            source=job.source,
            official_url=job.job_url,
        )
        session.add(draft)
        session.commit()
        return draft.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _draft_dict(draft, job, include_result=True):
    result = _decrypt_json(draft.encrypted_result) if include_result else {}
    return {
        "id": draft.id,
        "job_id": draft.job_id,
        "company": job.company if job else "Unknown company",
        "title": job.title if job else "Unknown role",
        "location": job.location if job else "",
        "official_url": draft.official_url,
        "source": draft.source,
        "status": draft.status,
        "result": result,
        "artifact_dir": draft.artifact_dir,
        "error_message": draft.error_message or "",
        "requested_at": draft.requested_at,
        "started_at": draft.started_at,
        "completed_at": draft.completed_at,
        "reviewed_at": draft.reviewed_at,
        "submission_approved_at": draft.submission_approved_at,
        "submitted_at": draft.submitted_at,
    }


def list_application_drafts(username, limit=30):
    ensure_application_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return []
        rows = (
            session.query(ApplicationDraft, JobPosting)
            .join(JobPosting, JobPosting.id == ApplicationDraft.job_id)
            .filter(ApplicationDraft.user_id == user.id)
            .order_by(ApplicationDraft.requested_at.desc(), ApplicationDraft.id.desc())
            .limit(limit)
            .all()
        )
        return [_draft_dict(draft, job) for draft, job in rows]
    finally:
        session.close()


def latest_application_draft(username, job_id):
    ensure_application_schema()
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return None
        row = (
            session.query(ApplicationDraft, JobPosting)
            .join(JobPosting, JobPosting.id == ApplicationDraft.job_id)
            .filter(
                ApplicationDraft.user_id == user.id,
                ApplicationDraft.job_id == job_id,
            )
            .order_by(ApplicationDraft.id.desc())
            .first()
        )
        return _draft_dict(*row) if row else None
    finally:
        session.close()


def claim_next_application_draft():
    ensure_application_schema()
    session = SessionLocal()
    try:
        stale_before = datetime.utcnow() - timedelta(minutes=20)
        (
            session.query(ApplicationDraft)
            .filter(
                ApplicationDraft.status == "preparing",
                ApplicationDraft.started_at < stale_before,
            )
            .update(
                {
                    ApplicationDraft.status: "queued",
                    ApplicationDraft.error_message: "Recovered an interrupted preparation.",
                },
                synchronize_session=False,
            )
        )
        (
            session.query(ApplicationDraft)
            .filter(
                ApplicationDraft.status == "submitting",
                ApplicationDraft.started_at < stale_before,
            )
            .update(
                {
                    ApplicationDraft.status: "needs_attention",
                    ApplicationDraft.error_message: (
                        "Submission worker was interrupted. Verify the employer's application "
                        "history before approving another attempt."
                    ),
                },
                synchronize_session=False,
            )
        )
        session.commit()
        draft = (
            session.query(ApplicationDraft)
            .filter(
                ApplicationDraft.status.in_(("queued", "approved_for_submission"))
            )
            .order_by(
                case(
                    (ApplicationDraft.status == "approved_for_submission", 0),
                    else_=1,
                ),
                ApplicationDraft.requested_at.asc(),
            )
            .with_for_update(skip_locked=True)
            .first()
        )
        if not draft:
            session.rollback()
            return None
        action = (
            "submit" if draft.status == "approved_for_submission" else "prepare"
        )
        draft.status = "submitting" if action == "submit" else "preparing"
        draft.started_at = datetime.utcnow()
        draft.error_message = None
        session.commit()
        return {"id": draft.id, "action": action}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_draft_worker_payload(draft_id):
    ensure_application_schema()
    session = SessionLocal()
    try:
        row = (
            session.query(ApplicationDraft, ApplicationProfile, JobPosting)
            .join(
                ApplicationProfile,
                ApplicationProfile.user_id == ApplicationDraft.user_id,
            )
            .join(JobPosting, JobPosting.id == ApplicationDraft.job_id)
            .filter(ApplicationDraft.id == draft_id)
            .first()
        )
        if not row:
            raise ValueError("Application draft was not found.")
        draft, profile, job = row
        host = _site_host(draft.official_url)
        credential = (
            session.query(ApplicationSiteCredential)
            .filter_by(user_id=draft.user_id, site_host=host)
            .first()
        )
        return {
            "draft_id": draft.id,
            "username_key": str(draft.user_id),
            "source": draft.source,
            "official_url": draft.official_url,
            "company": job.company,
            "title": job.title,
            "profile": _decrypt_json(profile.encrypted_profile),
            "resume_filename": profile.resume_filename,
            "resume_bytes": _decrypt_bytes(profile.encrypted_resume),
            "site_credential": (
                {
                    **_decrypt_json(credential.encrypted_credentials),
                    "site_host": credential.site_host,
                }
                if credential
                else None
            ),
        }
    finally:
        session.close()


def complete_application_draft(draft_id, result, artifact_dir=None):
    ensure_application_schema()
    session = SessionLocal()
    try:
        draft = session.query(ApplicationDraft).filter_by(id=draft_id).first()
        if not draft:
            raise ValueError("Application draft was not found.")
        blockers = result.get("blockers") or []
        if result.get("submitted"):
            draft.status = "submitted"
            draft.submitted_at = datetime.utcnow()
        else:
            draft.status = "needs_attention" if blockers else "ready_for_review"
        draft.encrypted_result = _encrypt_json(result)
        draft.artifact_dir = artifact_dir
        draft.error_message = None
        draft.completed_at = datetime.utcnow()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def fail_application_draft(draft_id, error):
    ensure_application_schema()
    session = SessionLocal()
    try:
        draft = session.query(ApplicationDraft).filter_by(id=draft_id).first()
        if draft:
            if draft.status == "submitting":
                draft.status = "needs_attention"
                draft.error_message = (
                    f"Submission worker stopped: {error}. Verify the employer's application "
                    "history before approving another attempt."
                )[:2000]
            else:
                draft.status = "failed"
                draft.error_message = str(error)[:2000]
            draft.completed_at = datetime.utcnow()
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def mark_application_reviewed(username, draft_id):
    ensure_application_schema()
    session = SessionLocal()
    try:
        draft = (
            session.query(ApplicationDraft)
            .join(User, User.id == ApplicationDraft.user_id)
            .filter(ApplicationDraft.id == draft_id, User.username == username)
            .first()
        )
        if not draft:
            return False
        if draft.status not in {"ready_for_review", "needs_attention"}:
            raise ValueError("Only completed preparations can be reviewed.")
        draft.reviewed_at = datetime.utcnow()
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def approve_application_submission(username, draft_id):
    ensure_application_schema()
    session = SessionLocal()
    try:
        draft = (
            session.query(ApplicationDraft)
            .join(User, User.id == ApplicationDraft.user_id)
            .filter(ApplicationDraft.id == draft_id, User.username == username)
            .first()
        )
        if not draft:
            return False
        if draft.status != "ready_for_review":
            raise ValueError("Resolve all preparation blockers before submission.")
        result = _decrypt_json(draft.encrypted_result)
        if result.get("blockers") or result.get("required_attention"):
            raise ValueError("Resolve all required fields before submission.")
        now = datetime.utcnow()
        draft.status = "approved_for_submission"
        draft.reviewed_at = now
        draft.submission_approved_at = now
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
