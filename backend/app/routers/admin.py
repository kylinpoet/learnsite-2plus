from __future__ import annotations

import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.auth import hash_password
from ..core.auth import Principal, require_roles
from ..core.database import get_db
from ..models import (
    AcademicTerm,
    Classroom,
    LegacyIdMapping,
    MigrationBatch,
    MigrationPreviewItem,
    MigrationStatus,
    ResourceCategory,
    School,
    TeacherClassroomAssignment,
    User,
    UserRole,
)
from ..schemas import (
    AcademicTermCreateRequest,
    AcademicTermSummary,
    AdminOverviewResponse,
    AdminClassroomSummary,
    AdminStudentSummary,
    AdminTeacherSummary,
    GovernanceSchoolSnapshot,
    LegacyMappingSummary,
    MessageResponse,
    MigrationBatchSummary,
    MigrationFixRequest,
    MigrationPreviewRow,
    AdminStudentImportResponse,
    PasswordResetRequest,
    ResourceCategoryCreateRequest,
    ResourceCategoryStatusRequest,
    ResourceCategorySummary,
    StudentImportResult,
    StudentImportRequest,
    StudentAssignmentRequest,
    TeacherAccountSaveRequest,
    UserStatusUpdateRequest,
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


def _get_term(db: Session, school: School, term_id: int) -> AcademicTerm:
    term = db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.id == term_id,
            AcademicTerm.school_id == school.id,
        )
    )
    if term is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic term not found.")
    return term


def _get_student(db: Session, school: School, student_id: int) -> User:
    student = db.scalar(
        select(User).where(
            User.id == student_id,
            User.school_id == school.id,
            User.role == UserRole.STUDENT,
        )
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    return student


def _get_teacher_account(db: Session, school: School, teacher_id: int) -> User:
    teacher = db.scalar(
        select(User).where(
            User.id == teacher_id,
            User.school_id == school.id,
            User.role.in_((UserRole.TEACHER, UserRole.SCHOOL_ADMIN)),
        )
    )
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher account not found.")
    return teacher


def _get_classroom(db: Session, school: School, classroom_id: int) -> Classroom:
    classroom = db.scalar(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.school_id == school.id,
        )
    )
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classroom not found.")
    return classroom


def _get_resource_category(db: Session, school: School, category_id: int) -> ResourceCategory:
    category = db.scalar(
        select(ResourceCategory).where(
            ResourceCategory.id == category_id,
            ResourceCategory.school_id == school.id,
        )
    )
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource category not found.")
    return category


def _serialize_resource_categories(db: Session, school: School) -> list[ResourceCategorySummary]:
    categories = db.scalars(
        select(ResourceCategory)
        .where(ResourceCategory.school_id == school.id)
        .order_by(ResourceCategory.sort_order, ResourceCategory.id)
    ).all()
    return [
        ResourceCategorySummary(
            id=category.id,
            name=category.name,
            description=category.description,
            sort_order=category.sort_order,
            active=category.active,
        )
        for category in categories
    ]


def _ensure_manageable_role(principal: Principal, role: UserRole) -> None:
    if role == UserRole.SCHOOL_ADMIN and principal.role != UserRole.PLATFORM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins can manage school admin accounts.",
        )
    if role not in {UserRole.TEACHER, UserRole.SCHOOL_ADMIN}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported teacher account role.")


def _ensure_manageable_teacher(principal: Principal, teacher: User) -> None:
    _ensure_manageable_role(principal, teacher.role)
    if teacher.id == principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot modify the active session account from this panel.",
        )


def _validate_classroom_ids(db: Session, school: School, classroom_ids: list[int]) -> list[int]:
    if not classroom_ids:
        return []
    normalized_ids = sorted({classroom_id for classroom_id in classroom_ids})
    classrooms = db.scalars(
        select(Classroom).where(
            Classroom.school_id == school.id,
            Classroom.id.in_(normalized_ids),
        )
    ).all()
    found_ids = {classroom.id for classroom in classrooms}
    if found_ids != set(normalized_ids):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more classrooms are invalid.")
    return normalized_ids


def _sync_teacher_classroom_assignments(
    db: Session,
    school: School,
    teacher: User,
    classroom_ids: list[int],
) -> None:
    normalized_ids = _validate_classroom_ids(db, school, classroom_ids)
    existing_rows = db.scalars(
        select(TeacherClassroomAssignment).where(
            TeacherClassroomAssignment.school_id == school.id,
            TeacherClassroomAssignment.teacher_user_id == teacher.id,
        )
    ).all()
    existing_ids = {row.classroom_id for row in existing_rows}

    for row in existing_rows:
        if row.classroom_id not in normalized_ids:
            db.delete(row)

    for classroom_id in normalized_ids:
        if classroom_id not in existing_ids:
            db.add(
                TeacherClassroomAssignment(
                    school_id=school.id,
                    teacher_user_id=teacher.id,
                    classroom_id=classroom_id,
                )
            )


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


def _format_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _parse_iso_date(value: str | None, field_name: str) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must use YYYY-MM-DD format.",
        ) from exc


def _serialize_term(term: AcademicTerm) -> AcademicTermSummary:
    return AcademicTermSummary(
        id=term.id,
        school_year_label=term.school_year_label,
        term_name=term.term_name,
        start_on=_format_date(term.start_on),
        end_on=_format_date(term.end_on),
        is_active=term.is_active,
        sort_order=term.sort_order,
    )


def _serialize_classrooms(db: Session, school: School) -> list[AdminClassroomSummary]:
    classrooms = db.scalars(
        select(Classroom).where(Classroom.school_id == school.id).order_by(Classroom.grade_label, Classroom.name)
    ).all()
    students = db.scalars(
        select(User).where(
            User.school_id == school.id,
            User.role == UserRole.STUDENT,
            User.active.is_(True),
        )
    ).all()
    counts: dict[int, int] = {}
    for student in students:
        if student.classroom_id is not None:
            counts[student.classroom_id] = counts.get(student.classroom_id, 0) + 1

    return [
        AdminClassroomSummary(
            id=classroom.id,
            name=classroom.name,
            grade_label=classroom.grade_label,
            student_count=counts.get(classroom.id, 0),
        )
        for classroom in classrooms
    ]


def _serialize_students(db: Session, school: School) -> list[AdminStudentSummary]:
    students = db.scalars(
        select(User).where(
            User.school_id == school.id,
            User.role == UserRole.STUDENT,
        )
    ).all()
    students.sort(key=lambda student: (student.classroom_id is None, student.classroom_id or 0, student.username))
    classroom_map = {
        classroom.id: classroom
        for classroom in db.scalars(select(Classroom).where(Classroom.school_id == school.id)).all()
    }
    return [
        AdminStudentSummary(
            id=student.id,
            username=student.username,
            display_name=student.display_name,
            classroom_id=student.classroom_id,
            classroom_name=classroom_map.get(student.classroom_id).name if student.classroom_id in classroom_map else None,
            active=student.active,
        )
        for student in students
    ]


def _serialize_teacher_accounts(db: Session, school: School) -> list[AdminTeacherSummary]:
    accounts = db.scalars(
        select(User).where(
            User.school_id == school.id,
            User.role.in_((UserRole.TEACHER, UserRole.SCHOOL_ADMIN)),
        )
    ).all()
    accounts.sort(key=lambda teacher: (teacher.role != UserRole.SCHOOL_ADMIN, teacher.username))
    classroom_map = {
        classroom.id: classroom
        for classroom in db.scalars(select(Classroom).where(Classroom.school_id == school.id)).all()
    }
    assignment_rows = db.scalars(
        select(TeacherClassroomAssignment).where(TeacherClassroomAssignment.school_id == school.id)
    ).all()
    assignment_map: dict[int, list[int]] = {}
    for row in assignment_rows:
        assignment_map.setdefault(row.teacher_user_id, []).append(row.classroom_id)

    return [
        AdminTeacherSummary(
            id=teacher.id,
            username=teacher.username,
            display_name=teacher.display_name,
            role=teacher.role,
            active=teacher.active,
            assigned_classroom_ids=sorted(assignment_map.get(teacher.id, [])),
            assigned_classroom_names=[
                classroom_map[classroom_id].name
                for classroom_id in sorted(assignment_map.get(teacher.id, []))
                if classroom_id in classroom_map
            ],
        )
        for teacher in accounts
    ]


def _serialize_terms(db: Session, school: School) -> tuple[AcademicTermSummary | None, list[AcademicTermSummary]]:
    terms = db.scalars(
        select(AcademicTerm)
        .where(AcademicTerm.school_id == school.id)
        .order_by(AcademicTerm.school_year_label.desc(), AcademicTerm.sort_order.asc(), AcademicTerm.id.asc())
    ).all()
    active_term = next((term for term in terms if term.is_active), None)
    return (_serialize_term(active_term) if active_term else None, [_serialize_term(term) for term in terms])


def _deactivate_terms(db: Session, school_id: int) -> None:
    terms = db.scalars(select(AcademicTerm).where(AcademicTerm.school_id == school_id, AcademicTerm.is_active.is_(True))).all()
    for term in terms:
        term.is_active = False


def _parse_import_rows(rows_text: str) -> list[tuple[str, str, str | None]]:
    parsed: list[tuple[str, str, str | None]] = []
    for raw_line in rows_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tokens = [token.strip() for token in re.split(r"[\t,，]+", line) if token.strip()]
        if len(tokens) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each student row must include at least username and display name.",
            )
        first_token = tokens[0].lower()
        if first_token in {"username", "student_id", "account", "学号"}:
            continue
        username = tokens[0]
        display_name = tokens[1]
        password = tokens[2] if len(tokens) > 2 else None
        parsed.append((username, display_name, password))
    if not parsed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No valid student rows found.")
    return parsed


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
    active_term, academic_terms = _serialize_terms(db, current_school)
    classrooms = _serialize_classrooms(db, current_school)
    teacher_accounts = _serialize_teacher_accounts(db, current_school)
    students = _serialize_students(db, current_school)
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
        active_term=active_term,
        academic_terms=academic_terms,
        classrooms=classrooms,
        resource_categories=_serialize_resource_categories(db, current_school),
        teacher_accounts=teacher_accounts,
        students=students,
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


@router.post("/resource-categories", response_model=AdminOverviewResponse)
def create_resource_category(
    payload: ResourceCategoryCreateRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    normalized_name = payload.name.strip()
    existing = db.scalar(
        select(ResourceCategory).where(
            ResourceCategory.school_id == school.id,
            ResourceCategory.name == normalized_name,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource category already exists.")

    db.add(
        ResourceCategory(
            school_id=school.id,
            name=normalized_name,
            description=payload.description.strip() if payload.description and payload.description.strip() else None,
            sort_order=payload.sort_order,
            active=True,
        )
    )
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/resource-categories/{category_id}/status", response_model=AdminOverviewResponse)
def update_resource_category_status(
    category_id: int,
    payload: ResourceCategoryStatusRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    category = _get_resource_category(db, school, category_id)
    if not payload.active:
        active_count = db.scalar(
            select(func.count(ResourceCategory.id)).where(
                ResourceCategory.school_id == school.id,
                ResourceCategory.active.is_(True),
            )
        )
        if category.active and active_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="At least one active resource category must remain available.",
            )
    category.active = payload.active
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/terms", response_model=AdminOverviewResponse)
def create_term(
    payload: AcademicTermCreateRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    existing = db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.school_id == school.id,
            AcademicTerm.school_year_label == payload.school_year_label.strip(),
            AcademicTerm.term_name == payload.term_name.strip(),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Academic term already exists.")

    if payload.activate_now:
        _deactivate_terms(db, school.id)

    existing_terms = db.scalars(select(AcademicTerm).where(AcademicTerm.school_id == school.id)).all()
    start_on = _parse_iso_date(payload.start_on, "start_on")
    end_on = _parse_iso_date(payload.end_on, "end_on")
    if start_on and end_on and end_on < start_on:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="end_on must be after start_on.")

    term = AcademicTerm(
        school_id=school.id,
        school_year_label=payload.school_year_label.strip(),
        term_name=payload.term_name.strip(),
        start_on=start_on,
        end_on=end_on,
        is_active=payload.activate_now,
        sort_order=len(existing_terms) + 1,
    )
    db.add(term)
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/terms/{term_id}/activate", response_model=AdminOverviewResponse)
def activate_term(
    term_id: int,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    term = _get_term(db, school, term_id)
    _deactivate_terms(db, school.id)
    term.is_active = True
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/teachers", response_model=AdminOverviewResponse)
def save_teacher_account(
    payload: TeacherAccountSaveRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    role = UserRole(payload.role)
    _ensure_manageable_role(principal, role)

    username = payload.username.strip()
    display_name = payload.display_name.strip()
    if not username or not display_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Username and display name are required.")

    account = _get_teacher_account(db, school, payload.teacher_id) if payload.teacher_id is not None else None
    if account is not None:
        _ensure_manageable_teacher(principal, account)

    conflict = db.scalar(
        select(User).where(
            User.school_id == school.id,
            User.username == username,
        )
    )
    if conflict is not None and (account is None or conflict.id != account.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists in this school.")

    if account is None:
        account = User(
            school_id=school.id,
            classroom_id=None,
            username=username,
            display_name=display_name,
            password_hash=hash_password(payload.password or "222221"),
            role=role,
            active=True,
        )
        db.add(account)
    else:
        account.username = username
        account.display_name = display_name
        account.role = role
        if payload.password:
            account.password_hash = hash_password(payload.password)

    if role == UserRole.TEACHER:
        _sync_teacher_classroom_assignments(db, school, account, payload.classroom_ids)
    else:
        _sync_teacher_classroom_assignments(db, school, account, [])

    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/teachers/{teacher_id}/reset-password", response_model=AdminOverviewResponse)
def reset_teacher_password(
    teacher_id: int,
    payload: PasswordResetRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    teacher = _get_teacher_account(db, school, teacher_id)
    _ensure_manageable_teacher(principal, teacher)
    teacher.password_hash = hash_password(payload.new_password)
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/teachers/{teacher_id}/status", response_model=AdminOverviewResponse)
def update_teacher_status(
    teacher_id: int,
    payload: UserStatusUpdateRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    teacher = _get_teacher_account(db, school, teacher_id)
    _ensure_manageable_teacher(principal, teacher)
    teacher.active = payload.active
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/students/{student_id}/assign-classroom", response_model=AdminOverviewResponse)
def assign_student_classroom(
    student_id: int,
    payload: StudentAssignmentRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    student = _get_student(db, school, student_id)
    classroom = _get_classroom(db, school, payload.classroom_id)
    student.classroom_id = classroom.id
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/students/{student_id}/reset-password", response_model=AdminOverviewResponse)
def reset_student_password(
    student_id: int,
    payload: PasswordResetRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    student = _get_student(db, school, student_id)
    student.password_hash = hash_password(payload.new_password)
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/students/{student_id}/status", response_model=AdminOverviewResponse)
def update_student_status(
    student_id: int,
    payload: UserStatusUpdateRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    school = _resolve_scope_school(db, principal, school_code)
    student = _get_student(db, school, student_id)
    student.active = payload.active
    db.commit()
    return _overview_payload(db, principal, school.code)


@router.post("/students/import", response_model=AdminStudentImportResponse)
def import_students(
    payload: StudentImportRequest,
    school_code: str | None = Query(default=None),
    principal: Principal = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminStudentImportResponse:
    school = _resolve_scope_school(db, principal, school_code)
    classroom = _get_classroom(db, school, payload.classroom_id)
    rows = _parse_import_rows(payload.rows_text)

    imported_count = 0
    updated_count = 0
    skipped_count = 0
    seen_usernames: set[str] = set()

    for username, display_name, password in rows:
        if username in seen_usernames:
            skipped_count += 1
            continue
        seen_usernames.add(username)

        existing = db.scalar(
            select(User).where(
                User.school_id == school.id,
                User.username == username,
            )
        )
        if existing is not None:
            if existing.role != UserRole.STUDENT:
                skipped_count += 1
                continue
            existing.display_name = display_name
            existing.classroom_id = classroom.id
            existing.active = True
            if password:
                existing.password_hash = hash_password(password)
            updated_count += 1
            continue

        db.add(
            User(
                school_id=school.id,
                classroom_id=classroom.id,
                username=username,
                display_name=display_name,
                password_hash=hash_password(password or payload.default_password),
                role=UserRole.STUDENT,
                active=True,
            )
        )
        imported_count += 1

    db.commit()
    return AdminStudentImportResponse(
        overview=_overview_payload(db, principal, school.code),
        result=StudentImportResult(
            imported_count=imported_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
        ),
    )


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
