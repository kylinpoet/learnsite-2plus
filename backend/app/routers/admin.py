from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.auth import Principal, require_roles
from ..core.database import get_db
from ..models import MigrationBatch, School, UserRole
from ..schemas import AdminOverviewResponse, MigrationBatchSummary

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverviewResponse)
def admin_overview(
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    if principal.role == UserRole.PLATFORM_ADMIN:
        schools = db.scalars(select(School).order_by(School.id)).all()
    else:
        schools = db.scalars(select(School).where(School.id == principal.school_id)).all()

    batch = db.scalar(
        select(MigrationBatch)
        .where(MigrationBatch.school_id == principal.school_id)
        .order_by(MigrationBatch.created_at.desc())
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No migration batch found.")

    return AdminOverviewResponse(
        school_name=principal.school_name,
        admin_name=principal.display_name,
        active_school_count=len(schools),
        managed_schools=schools,
        active_migration=MigrationBatchSummary(
            name=batch.name,
            status=batch.status.value,
            progress=batch.progress,
            current_step=batch.current_step,
            error_count=batch.error_count,
            preview_rows=batch.preview_rows,
        ),
        guardrails=[
            "所有迁移批次都必须支持 dry-run 预检。",
            "学校管理员默认只能看到本校数据，跨校操作需要更高权限。",
            "高风险操作必须先显示学校、学期、批次上下文，再允许执行。",
        ],
    )
