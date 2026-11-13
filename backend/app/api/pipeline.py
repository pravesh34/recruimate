"""Application-pipeline endpoints: track target jobs from pool to offer."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.models import JobPosting, PipelineEntry, User, get_db
from .deps import get_current_user, iso
from .schemas import PipelineCreate, PipelineUpdate

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

STATUSES = ("new", "shortlisted", "applied", "interview", "offer", "rejected", "closed")


def _entry_to_dict(entry: PipelineEntry) -> dict:
    return {
        "id": entry.id,
        "job_posting_id": entry.job_posting_id,
        "title": entry.title,
        "company": entry.company,
        "url": entry.url,
        "source": entry.source,
        "status": entry.status,
        "notes": entry.notes,
        "next_action_at": iso(entry.next_action_at) if entry.next_action_at else None,
        "created_at": iso(entry.created_at),
        "updated_at": iso(entry.updated_at),
    }


def _own_entry(db: Session, entry_id: int, user: User) -> PipelineEntry:
    entry = db.get(PipelineEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(404, "Pipeline entry not found.")
    return entry


@router.get("")
def list_pipeline(
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List the caller's pipeline, newest activity first, with status counts."""
    query = db.query(PipelineEntry).filter(PipelineEntry.user_id == user.id)
    if status:
        if status not in STATUSES:
            raise HTTPException(400, f"Unknown status '{status}'.")
        query = query.filter(PipelineEntry.status == status)
    rows = query.order_by(PipelineEntry.updated_at.desc(), PipelineEntry.id.desc()).all()

    summary = {name: 0 for name in STATUSES}
    # SQLite returns naive datetimes; the stored values are UTC, so compare
    # against a naive UTC "now".
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    due: list[dict] = []
    for row in db.query(PipelineEntry).filter(PipelineEntry.user_id == user.id).all():
        summary[row.status] = summary.get(row.status, 0) + 1
        if row.next_action_at and row.next_action_at <= now:
            due.append({"id": row.id, "title": row.title, "company": row.company})

    return {"entries": [_entry_to_dict(r) for r in rows], "summary": summary, "due": due[:10]}


@router.post("")
def create_entry(
    payload: PipelineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start tracking a job. ``job_id`` snapshots a pool posting; otherwise a
    manual ``title`` (+ optional company/url) is required."""
    if payload.status and payload.status not in STATUSES:
        raise HTTPException(400, f"Unknown status '{payload.status}'.")

    posting = None
    if payload.job_id is not None:
        posting = db.get(JobPosting, payload.job_id)
        if not posting or (posting.user_id is not None and posting.user_id != user.id):
            raise HTTPException(404, "Pool job not found.")

    entry = PipelineEntry(
        user_id=user.id,
        job_posting_id=posting.id if posting else None,
        title=(posting.title if posting else payload.title or "")[:255],
        company=(posting.company if posting else payload.company or "")[:255],
        url=(posting.url if posting else payload.url or "")[:1024],
        source=(posting.source if posting else payload.source or "manual")[:64],
        status=payload.status or "new",
        notes=(payload.notes or "")[:4000],
    )
    if not entry.title:
        raise HTTPException(400, "Provide a job_id from your pool, or a title.")
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _entry_to_dict(entry)


@router.patch("/{entry_id}")
def update_entry(
    entry_id: int,
    payload: PipelineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Move a job through the pipeline or edit notes / next action."""
    entry = _own_entry(db, entry_id, user)
    if payload.status is not None:
        if payload.status not in STATUSES:
            raise HTTPException(400, f"Unknown status '{payload.status}'.")
        entry.status = payload.status
    if payload.notes is not None:
        entry.notes = payload.notes[:4000]
    if payload.next_action_at is not None:
        raw = payload.next_action_at.strip()
        if not raw:
            entry.next_action_at = None
        else:
            try:
                entry.next_action_at = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError as exc:
                raise HTTPException(400, f"Invalid date: {raw}") from exc
    db.commit()
    db.refresh(entry)
    return _entry_to_dict(entry)


@router.delete("/{entry_id}")
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = _own_entry(db, entry_id, user)
    db.delete(entry)
    db.commit()
    return {"deleted": True, "id": entry_id}
