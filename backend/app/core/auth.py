from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from secrets import token_urlsafe
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from .config import get_settings
from ..models import School, ThemeStyle, User, UserRole
from ..schemas import SessionInfo


@dataclass(slots=True)
class Principal:
    token: str
    user_id: int
    role: UserRole
    username: str
    display_name: str
    school_id: int
    school_code: str
    school_name: str
    theme_style: ThemeStyle
    expires_at: datetime


SESSION_STORE: dict[str, Principal] = {}
PBKDF2_ITERATIONS = 390_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_digest = base64.b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${encoded_salt}${encoded_digest}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        algorithm, iteration_text, encoded_salt, encoded_digest = password_hash.split("$", maxsplit=3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    iterations = int(iteration_text)
    salt = base64.b64decode(encoded_salt.encode("ascii"))
    stored_digest = base64.b64decode(encoded_digest.encode("ascii"))
    candidate = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, stored_digest)


def build_session(user: User, school: School) -> Principal:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=get_settings().session_ttl_minutes)
    token = token_urlsafe(32)
    principal = Principal(
        token=token,
        user_id=user.id,
        role=user.role,
        username=user.username,
        display_name=user.display_name,
        school_id=school.id,
        school_code=school.code,
        school_name=school.name,
        theme_style=school.theme_style,
        expires_at=expires_at,
    )
    SESSION_STORE[token] = principal
    return principal


def principal_to_session_info(principal: Principal) -> SessionInfo:
    return SessionInfo(
        token=principal.token,
        role=principal.role,
        username=principal.username,
        display_name=principal.display_name,
        school_code=principal.school_code,
        school_name=principal.school_name,
        theme_style=principal.theme_style,
        expires_at=principal.expires_at,
    )


def revoke_session(token: str) -> None:
    SESSION_STORE.pop(token, None)


def _extract_token(authorization: str | None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return None


def get_current_principal(
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    resolved_token = _extract_token(authorization)
    if not resolved_token or resolved_token not in SESSION_STORE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing session token.",
        )
    principal = SESSION_STORE[resolved_token]
    if principal.expires_at <= datetime.now(timezone.utc):
        revoke_session(resolved_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        )
    return principal


def require_roles(*allowed_roles: UserRole) -> Callable[[Principal], Principal]:
    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Current session cannot access this resource.",
            )
        return principal

    return dependency
