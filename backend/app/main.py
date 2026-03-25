from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .core.migrations import upgrade_database_schema
from .routers.admin import router as admin_router
from .routers.auth import public_router, router as auth_router
from .routers.student import router as student_router
from .routers.teacher import router as teacher_router
from .seed import seed_demo_data

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    upgrade_database_schema()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(public_router)
api_router.include_router(auth_router)
api_router.include_router(student_router)
api_router.include_router(teacher_router)
api_router.include_router(admin_router)
app.include_router(api_router)
