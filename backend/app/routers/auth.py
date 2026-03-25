from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.auth import (
    build_session,
    get_current_principal,
    principal_to_session_info,
    verify_password,
)
from ..core.database import get_db
from ..models import School, ThemeStyle, User, UserRole
from ..schemas import (
    BootstrapResponse,
    LoginRequest,
    LoginResponse,
    SessionInfo,
    ThemeStyleOption,
)

public_router = APIRouter()
router = APIRouter(prefix="/auth", tags=["auth"])


@public_router.get("/bootstrap", response_model=BootstrapResponse)
def get_bootstrap(db: Session = Depends(get_db)) -> BootstrapResponse:
    schools = db.scalars(select(School).order_by(School.id)).all()
    return BootstrapResponse(
        schools=schools,
        theme_styles=[
            ThemeStyleOption(
                id=ThemeStyle.WORKSHOP,
                name="Classroom Workshop",
                description="暖纸面、课堂感、任务舞台",
            ),
            ThemeStyleOption(
                id=ThemeStyle.MATERIAL,
                name="Material Design",
                description="结构清晰、层次明确、现代规范",
            ),
            ThemeStyleOption(
                id=ThemeStyle.NATURAL,
                name="Natural",
                description="大地色、有机感、自然温暖",
            ),
        ],
    )


def _redirect_path_for_role(role: UserRole) -> str:
    if role == UserRole.STUDENT:
        return "/student/home"
    if role in (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN):
        return "/teacher/console"
    return "/"


def _allowed_roles_for_login(role: str) -> tuple[UserRole, ...]:
    if role == "student":
        return (UserRole.STUDENT,)
    if role == "teacher":
        return (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)
    return (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    school = db.scalar(select(School).where(School.code == payload.school_code))
    if school is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found.")

    user = db.scalar(
        select(User).where(
            User.school_id == school.id,
            User.username == payload.username,
            User.active.is_(True),
        )
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    if user.role not in _allowed_roles_for_login(payload.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role mismatch.")

    principal = build_session(user, school)
    session = principal_to_session_info(principal)
    return LoginResponse(session=session, redirect_path=_redirect_path_for_role(user.role))


@router.get("/me", response_model=SessionInfo)
def me(principal=Depends(get_current_principal)) -> SessionInfo:
    return principal_to_session_info(principal)
