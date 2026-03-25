from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.auth import Principal, require_roles
from ..core.database import get_db
from ..models import LegacyIdMapping, MigrationBatch, MigrationPreviewItem, MigrationStatus, School, UserRole
from ..schemas import (
    AdminOverviewResponse,
    GovernanceSchoolSnapshot,
    LegacyMappingSummary,
    MessageResponse,
    MigrationBatchSummary,
    MigrationFixRequest,
    MigrationPreviewRow,
)

router = APIRouter(prefix="/admin", tags=["admin"])

RESOLVED_PREVIEW_STATUSES = {"mapped", "resolved"}


def _get_managed_schools(db: Session, principal: Principal) -> list[School]:
    if principal.role == UserRole.PLATFORM_ADMIN:
        return db.scalars(select(School).order_by(School.id)).all()
    return db.scalars(select(School).where(School.id == principal.school_id)).all()


def _resolve_scope_school(db: Session, principal: Principal, school_code: str | None) -> School:
    if principal.role != UserRole.PLATFORM_ADMIN:
        if school_code and school_code != principal.school_code:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another school.")
        school = db.scalar(select(School).where(School.id == principal.school_id))
        if school is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found.")
        return school

    if school_code:
        school = db.scalar(select(School).where(School.code == school_code))
    else:
        school = db.scalar(select(School).where(School.id == principal.school_id))
    if school is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found.")
    return school


def _get_batch(db: Session, school: School, batch_id: int) -> MigrationBatch:
    batch = db.scalar(
        select(MigrationBatch).where(
            MigrationBatch.id == batch_id,
            MigrationBatch.school_id == school.id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Migration batch not found.")
    return batch


def _get_preview_item(
    db: Session,
    batch: MigrationBatch,
    preview_item_id: int,
) -> MigrationPreviewItem:
    preview_item = db.scalar(
        select(MigrationPreviewItem).where(
            MigrationPreviewItem.id == preview_item_id,
            MigrationPreviewItem.batch_id == batch.id,
        )
    )
    if preview_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview item not found.")
    return preview_item


def _requires_resolution(preview_row: MigrationPreviewItem) -> bool:
    return preview_row.status not in RESOLVED_PREVIEW_STATUSES


def _serialize_preview_row(preview_row: MigrationPreviewItem) -> MigrationPreviewRow:
    return MigrationPreviewRow(
        id=preview_row.id,
        field_name=preview_row.field_name,
        legacy_value=preview_row.legacy_value,
        new_value=preview_row.new_value,
        status=preview_row.status,
        issue_detail=preview_row.issue_detail,
        resolution_note=preview_row.resolution_note,
        resolved_at=preview_row.resolved_at.strftime("%Y-%m-%d %H:%M") if preview_row.resolved_at else None,
        requires_resolution=_requires_resolution(preview_row),
    )


def _recalculate_batch_health(batch: MigrationBatch) -> None:
    unresolved_count = sum(1 for row in batch.preview_rows if _requires_resolution(row))
    batch.error_count = unresolved_count
    if unresolved_count == 0 and batch.status in {
        MigrationStatus.DRAFT,
        MigrationStatus.VALIDATED,
        MigrationStatus.PREVIEWED,
        MigrationStatus.PARTIALLY_FAILED,
    }:
        batch.status = MigrationStatus.PREVIEWED
        batch.progress = 68
        batch.current_step = "所有预览问题已修复，可以重新执行迁移。"
    elif unresolved_count > 0 and batch.status in {
        MigrationStatus.DRAFT,
        MigrationStatus.VALIDATED,
        MigrationStatus.PREVIEWED,
            MigrationStatus.PARTIALLY_FAILED,
    }:
        batch.current_step = f"还有 {unresolved_count} 条预览问题需要人工修复。"


def _can_execute_batch(batch: MigrationBatch) -> bool:
    return batch.status in {
        MigrationStatus.DRAFT,
        MigrationStatus.VALIDATED,
        MigrationStatus.PREVIEWED,
        MigrationStatus.PARTIALLY_FAILED,
        MigrationStatus.ROLLED_BACK,
    } and batch.error_count == 0


def _can_rollback_batch(mappings: list[LegacyIdMapping], batch: MigrationBatch) -> bool:
    return batch.status in {
        MigrationStatus.COMPLETED,
        MigrationStatus.PARTIALLY_FAILED,
    } and any(mapping.active for mapping in mappings)


def _serialize_batch(batch: MigrationBatch) -> MigrationBatchSummary:
    return MigrationBatchSummary(
        id=batch.id,
        name=batch.name,
        status=batch.status.value,
        progress=batch.progress,
        current_step=batch.current_step,
        error_count=batch.error_count,
        preview_rows=[_serialize_preview_row(row) for row in batch.preview_rows],
    )


def _build_school_snapshot(
    db: Session,
    school: School,
    current_school_id: int,
) -> GovernanceSchoolSnapshot:
    batch = db.scalar(
        select(MigrationBatch)
        .where(MigrationBatch.school_id == school.id)
        .order_by(MigrationBatch.created_at.desc())
    )
    if batch is None:
        return GovernanceSchoolSnapshot(
            school=school,
            unresolved_preview_count=0,
            is_current=school.id == current_school_id,
        )

    _recalculate_batch_health(batch)
    mappings = db.scalars(
        select(LegacyIdMapping)
        .where(LegacyIdMapping.batch_id == batch.id)
        .order_by(LegacyIdMapping.id.desc())
    ).all()
    return GovernanceSchoolSnapshot(
        school=school,
        latest_batch_name=batch.name,
        latest_batch_status=batch.status.value,
        latest_batch_progress=batch.progress,
        current_step=batch.current_step,
        unresolved_preview_count=batch.error_count,
        can_execute_migration=_can_execute_batch(batch),
        can_rollback_migration=_can_rollback_batch(mappings, batch),
        is_current=school.id == current_school_id,
    )


def _overview_payload(db: Session, principal: Principal, school_code: str | None = None) -> AdminOverviewResponse:
    schools = _get_managed_schools(db, principal)
    current_school = _resolve_scope_school(db, principal, school_code)
    batch = db.scalar(
        select(MigrationBatch)
        .where(MigrationBatch.school_id == current_school.id)
        .order_by(MigrationBatch.created_at.desc())
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No migration batch found.")

    _recalculate_batch_health(batch)
    mappings = db.scalars(
        select(LegacyIdMapping)
        .where(LegacyIdMapping.batch_id == batch.id)
        .order_by(LegacyIdMapping.id.desc())
    ).all()
    return AdminOverviewResponse(
        school_name=current_school.name,
        admin_name=principal.display_name,
        active_school_count=len(schools),
        current_school=current_school,
        managed_schools=schools,
        school_snapshots=[_build_school_snapshot(db, school, current_school.id) for school in schools],
        active_migration=_serialize_batch(batch),
        legacy_mappings=[LegacyMappingSummary.model_validate(mapping) for mapping in mappings],
        can_execute_migration=_can_execute_batch(batch),
        can_rollback_migration=_can_rollback_batch(mappings, batch),
        unresolved_preview_count=batch.error_count,
        guardrails=[
            "所有导入批次都必须支持 dry-run 预检。",
            "有 warning 或 error 的预览行必须先人工修复，再允许执行迁移。",
            "学校管理员默认只可操作本校数据，跨校治理需要更高权限。",
        ],
    )


@router.get("/overview", response_model=AdminOverviewResponse)
def admin_overview(
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    return _overview_payload(db, principal, school_code)


def _build_mapping(preview_row: MigrationPreviewItem, batch: MigrationBatch) -> LegacyIdMapping:
    if preview_row.field_name == "班级":
        entity_type = "classroom"
    elif preview_row.field_name == "学号映射":
        entity_type = "student"
    else:
        entity_type = "generic"

    return LegacyIdMapping(
        batch_id=batch.id,
        school_id=batch.school_id,
        entity_type=entity_type,
        legacy_id=preview_row.legacy_value,
        new_id=preview_row.new_value,
        active=True,
    )


@router.post("/migrations/{batch_id}/preview-items/{preview_item_id}/resolve", response_model=AdminOverviewResponse)
def resolve_preview_item(
    batch_id: int,
    preview_item_id: int,
    payload: MigrationFixRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    batch = _get_batch(db, school, batch_id)
    preview_item = _get_preview_item(db, batch, preview_item_id)

    preview_item.new_value = payload.new_value
    preview_item.status = payload.status
    preview_item.resolution_note = payload.resolution_note
    preview_item.resolved_by_user_id = principal.user_id
    preview_item.resolved_at = datetime.utcnow()

    _recalculate_batch_health(batch)
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/migrations/{batch_id}/execute", response_model=AdminOverviewResponse)
def execute_migration(
    batch_id: int,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    batch = _get_batch(db, school, batch_id)
    _recalculate_batch_health(batch)
    if batch.error_count > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resolve preview issues before execution.")
    if batch.status not in {
        MigrationStatus.DRAFT,
        MigrationStatus.VALIDATED,
        MigrationStatus.PREVIEWED,
        MigrationStatus.PARTIALLY_FAILED,
        MigrationStatus.ROLLED_BACK,
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Batch cannot be executed in current state.")

    batch.status = MigrationStatus.EXECUTING
    batch.progress = 92
    batch.current_step = "正在写入兼容映射与迁移结果。"
    db.flush()

    existing_keys = {
        (mapping.legacy_id, mapping.new_id, mapping.entity_type)
        for mapping in db.scalars(select(LegacyIdMapping).where(LegacyIdMapping.batch_id == batch.id)).all()
    }
    preview_rows = db.scalars(
        select(MigrationPreviewItem).where(MigrationPreviewItem.batch_id == batch.id).order_by(MigrationPreviewItem.id)
    ).all()
    for preview_row in preview_rows:
        if preview_row.status not in RESOLVED_PREVIEW_STATUSES:
            continue
        key = (preview_row.legacy_value, preview_row.new_value, _build_mapping(preview_row, batch).entity_type)
        if key in existing_keys:
            mapping = db.scalar(
                select(LegacyIdMapping).where(
                    LegacyIdMapping.batch_id == batch.id,
                    LegacyIdMapping.legacy_id == preview_row.legacy_value,
                    LegacyIdMapping.new_id == preview_row.new_value,
                )
            )
            if mapping:
                mapping.active = True
            continue
        db.add(_build_mapping(preview_row, batch))
        existing_keys.add(key)

    batch.status = MigrationStatus.COMPLETED
    batch.current_step = "迁移执行完成，可以开始核验结果。"
    batch.progress = 100
    batch.error_count = 0
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/migrations/{batch_id}/rollback", response_model=AdminOverviewResponse)
def rollback_migration(
    batch_id: int,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    batch = _get_batch(db, school, batch_id)
    active_mappings = db.scalars(
        select(LegacyIdMapping).where(
            LegacyIdMapping.batch_id == batch.id,
            LegacyIdMapping.active.is_(True),
        )
    ).all()
    if not active_mappings:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active mappings to rollback.")

    for mapping in active_mappings:
        mapping.active = False

    batch.status = MigrationStatus.ROLLED_BACK
    batch.progress = 0
    batch.current_step = "已回滚本批次执行结果，等待重新确认。"
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/migrations/{batch_id}/reset", response_model=MessageResponse)
def reset_migration_status(
    batch_id: int,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    school = _resolve_scope_school(db, principal, school_code)
    batch = _get_batch(db, school, batch_id)
    batch.status = MigrationStatus.PREVIEWED
    batch.progress = 68
    batch.current_step = "已恢复到预览确认阶段。"
    db.commit()
    return MessageResponse(message="Migration batch reset.", updated_at=batch.updated_at)
