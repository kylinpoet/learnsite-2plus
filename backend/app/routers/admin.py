from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.auth import Principal, require_roles
from ..core.database import get_db
from ..models import LegacyIdMapping, MigrationBatch, MigrationPreviewItem, MigrationStatus, School, UserRole
from ..schemas import AdminOverviewResponse, LegacyMappingSummary, MessageResponse, MigrationBatchSummary

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_managed_schools(db: Session, principal: Principal) -> list[School]:
    if principal.role == UserRole.PLATFORM_ADMIN:
        return db.scalars(select(School).order_by(School.id)).all()
    return db.scalars(select(School).where(School.id == principal.school_id)).all()


def _get_batch(db: Session, principal: Principal, batch_id: int) -> MigrationBatch:
    batch = db.scalar(
        select(MigrationBatch).where(
            MigrationBatch.id == batch_id,
            MigrationBatch.school_id == principal.school_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Migration batch not found.")
    return batch


def _serialize_batch(batch: MigrationBatch) -> MigrationBatchSummary:
    return MigrationBatchSummary(
        id=batch.id,
        name=batch.name,
        status=batch.status.value,
        progress=batch.progress,
        current_step=batch.current_step,
        error_count=batch.error_count,
        preview_rows=batch.preview_rows,
    )


def _overview_payload(db: Session, principal: Principal) -> AdminOverviewResponse:
    schools = _get_managed_schools(db, principal)
    batch = db.scalar(
        select(MigrationBatch)
        .where(MigrationBatch.school_id == principal.school_id)
        .order_by(MigrationBatch.created_at.desc())
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No migration batch found.")

    mappings = db.scalars(
        select(LegacyIdMapping)
        .where(LegacyIdMapping.batch_id == batch.id)
        .order_by(LegacyIdMapping.id.desc())
    ).all()
    return AdminOverviewResponse(
        school_name=principal.school_name,
        admin_name=principal.display_name,
        active_school_count=len(schools),
        managed_schools=schools,
        active_migration=_serialize_batch(batch),
        legacy_mappings=[LegacyMappingSummary.model_validate(mapping) for mapping in mappings],
        can_execute_migration=batch.status in {
            MigrationStatus.DRAFT,
            MigrationStatus.VALIDATED,
            MigrationStatus.PREVIEWED,
            MigrationStatus.PARTIALLY_FAILED,
            MigrationStatus.ROLLED_BACK,
        },
        can_rollback_migration=batch.status in {
            MigrationStatus.COMPLETED,
            MigrationStatus.PARTIALLY_FAILED,
        }
        and any(mapping.active for mapping in mappings),
        guardrails=[
            "所有迁移批次都必须支持 dry-run 预检。",
            "学校管理员默认只能看到本校数据，跨校操作需要更高权限。",
            "高风险操作必须先显示学校、学期、批次上下文，再允许执行。",
        ],
    )


@router.get("/overview", response_model=AdminOverviewResponse)
def admin_overview(
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    return _overview_payload(db, principal)


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


@router.post("/migrations/{batch_id}/execute", response_model=AdminOverviewResponse)
def execute_migration(
    batch_id: int,
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    batch = _get_batch(db, principal, batch_id)
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
    batch.current_step = "正在写入兼容映射与迁移结果"
    db.flush()

    existing_keys = {
        (mapping.legacy_id, mapping.new_id, mapping.entity_type)
        for mapping in db.scalars(select(LegacyIdMapping).where(LegacyIdMapping.batch_id == batch.id)).all()
    }
    preview_rows = db.scalars(
        select(MigrationPreviewItem).where(MigrationPreviewItem.batch_id == batch.id).order_by(MigrationPreviewItem.id)
    ).all()
    for preview_row in preview_rows:
        if preview_row.status != "mapped":
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

    if batch.error_count > 0:
        batch.status = MigrationStatus.PARTIALLY_FAILED
        batch.current_step = "执行完成，但仍有告警需要人工处理"
    else:
        batch.status = MigrationStatus.COMPLETED
        batch.current_step = "迁移执行完成，可开始核验结果"
    batch.progress = 100
    db.commit()
    return _overview_payload(db, principal)


@router.post("/migrations/{batch_id}/rollback", response_model=AdminOverviewResponse)
def rollback_migration(
    batch_id: int,
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    batch = _get_batch(db, principal, batch_id)
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
    batch.current_step = "已回滚本批次执行结果，等待重新确认"
    db.commit()
    return _overview_payload(db, principal)


@router.post("/migrations/{batch_id}/reset", response_model=MessageResponse)
def reset_migration_status(
    batch_id: int,
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    batch = _get_batch(db, principal, batch_id)
    batch.status = MigrationStatus.PREVIEWED
    batch.progress = 68
    batch.current_step = "已恢复到预览确认阶段"
    db.commit()
    return MessageResponse(message="Migration batch reset.", updated_at=batch.updated_at)
