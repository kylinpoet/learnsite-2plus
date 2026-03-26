from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.clock import utc_now
from ..core.database import get_db
from ..core.resource_storage import resolve_interactive_asset_path
from ..models import ActivitySubmission, CourseActivity
from ..schemas import ActivitySubmissionResponse, ActivitySubmissionSummary

router = APIRouter(prefix="/public", tags=["public"])


def _public_submission_url(submission_key: str) -> str:
    return f"/api/public/activities/{submission_key}/submit"


def _payload_preview(payload_json: str, *, limit: int = 120) -> str:
    compact = " ".join(payload_json.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _serialize_activity_submission(submission: ActivitySubmission) -> ActivitySubmissionSummary:
    return ActivitySubmissionSummary(
        id=submission.id,
        submitted_by_name=submission.submitted_by_name,
        submitted_at=submission.created_at.strftime("%Y-%m-%d %H:%M"),
        payload_preview=_payload_preview(submission.payload_json),
    )


def _inject_runtime(html_text: str, *, activity_id: int, public_submission_url: str) -> str:
    script = f"""
<script>
window.LEARNSITE_ACTIVITY_CONTEXT = {{
  activityId: {activity_id},
  publicSubmissionUrl: {json.dumps(public_submission_url)},
}};
window.learnsiteSubmit = async function(payload) {{
  if (window.parent && window.parent !== window) {{
    window.parent.postMessage({{
      type: 'learnsite:activity-submit',
      activityId: {activity_id},
      payload: payload ?? {{}},
      publicSubmissionUrl: {json.dumps(public_submission_url)}
    }}, '*');
    return {{ ok: true, mode: 'bridge' }};
  }}

  const response = await fetch({json.dumps(public_submission_url)}, {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(payload ?? {{}})
  }});
  return await response.json();
}};
</script>
""".strip()

    lower_text = html_text.lower()
    body_index = lower_text.rfind("</body>")
    if body_index >= 0:
        return f"{html_text[:body_index]}{script}{html_text[body_index:]}"
    return f"{html_text}\n{script}"


def _get_activity_by_launch_key(db: Session, launch_key: str) -> CourseActivity:
    activity = db.scalar(
        select(CourseActivity).where(
            CourseActivity.interactive_launch_key == launch_key,
        )
    )
    if activity is None or not activity.interactive_storage_key or not activity.interactive_entry_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive activity not found.")
    return activity


@router.get("/activities/{launch_key}/{asset_path:path}")
def serve_activity_asset(
    launch_key: str,
    asset_path: str,
    db: Session = Depends(get_db),
):
    activity = _get_activity_by_launch_key(db, launch_key)
    resolved_asset_path = asset_path or activity.interactive_entry_file or "index.html"

    try:
        file_path = resolve_interactive_asset_path(activity.interactive_storage_key, resolved_asset_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive asset file is missing.")

    if file_path.suffix.lower() in {".html", ".htm"}:
        html_text = file_path.read_text(encoding="utf-8")
        return HTMLResponse(
            _inject_runtime(
                html_text,
                activity_id=activity.id,
                public_submission_url=_public_submission_url(activity.interactive_submission_key or ""),
            )
        )

    return FileResponse(path=file_path)


@router.post("/activities/{submission_key}/submit", response_model=ActivitySubmissionResponse)
def submit_activity_payload(
    submission_key: str,
    payload: Any = Body(default={}),
    db: Session = Depends(get_db),
) -> ActivitySubmissionResponse:
    activity = db.scalar(
        select(CourseActivity).where(
            CourseActivity.interactive_submission_key == submission_key,
        )
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive activity submission API not found.")

    now = utc_now()
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    submitter_name = "interactive-page"
    if isinstance(payload, dict):
        candidate = payload.get("student_name") or payload.get("studentName") or payload.get("username")
        if isinstance(candidate, str) and candidate.strip():
            submitter_name = candidate.strip()

    submission = ActivitySubmission(
        school_id=activity.school_id,
        course_id=activity.course_id,
        activity_id=activity.id,
        session_id=None,
        submitted_by_user_id=None,
        submitted_by_name=submitter_name,
        payload_json=payload_json,
        created_at=now,
        updated_at=now,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return ActivitySubmissionResponse(
        message="Interactive activity payload received.",
        submission=_serialize_activity_submission(submission),
        updated_at=now,
    )
