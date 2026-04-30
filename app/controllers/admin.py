"""Admin controller - CRUD for users, roles, and LLM settings."""

from typing import Optional
from uuid import UUID

from litestar import Controller, get, post, put
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import require_role
from app.models.entities import User
from app.repositories.base import BaseRepository
from app.schemas.schemas import (
    SettingsResponse,
    SettingsUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)


_runtime_settings: dict = {}


def _get_runtime_settings() -> dict:
    if not _runtime_settings:
        from app.config import settings
        _runtime_settings["llm_model_name"] = settings.llm_model_name
        _runtime_settings["llm_temperature"] = settings.llm_temperature
        _runtime_settings["llm_max_tokens"] = settings.llm_max_tokens
        _runtime_settings["llm_request_timeout_seconds"] = settings.llm_request_timeout_seconds
    return _runtime_settings


async def provide_user_repo(db_session: AsyncSession) -> BaseRepository[User]:
    return BaseRepository(db_session, User)


class AdminController(Controller):
    """CRUD operations for admin users, roles, and LLM settings."""

    path = "/api/v1/admin"
    tags = ["Admin"]
    guards = [require_role("admin")]
    dependencies = {"user_repo": Provide(provide_user_repo)}

    @get("/users")
    async def list_users(self, user_repo: BaseRepository[User]) -> list[UserResponse]:
        users = await user_repo.list_all(limit=1000)
        return [
            UserResponse(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role_id=u.role_id,
                is_active=u.is_active,
                created_at=u.created_at.isoformat() if u.created_at else "",
            )
            for u in users
        ]

    @post("/users")
    async def create_user(
        self, data: UserCreate, user_repo: BaseRepository[User]
    ) -> UserResponse:
        user = User(
            email=data.email,
            full_name=data.full_name,
            role_id=data.role_id,
            is_active=data.is_active,
        )
        saved = await user_repo.save(user)
        return UserResponse(
            id=saved.id,
            email=saved.email,
            full_name=saved.full_name,
            role_id=saved.role_id,
            is_active=saved.is_active,
            created_at=saved.created_at.isoformat() if saved.created_at else "",
        )

    @put("/users/{user_id:uuid}")
    async def update_user(
        self, user_id: UUID, data: UserUpdate, user_repo: BaseRepository[User]
    ) -> UserResponse:
        user = await user_repo.get(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.role_id is not None:
            user.role_id = data.role_id
        if data.is_active is not None:
            user.is_active = data.is_active
        saved = await user_repo.save(user)
        return UserResponse(
            id=saved.id,
            email=saved.email,
            full_name=saved.full_name,
            role_id=saved.role_id,
            is_active=saved.is_active,
            created_at=saved.created_at.isoformat() if saved.created_at else "",
        )

    @get("/settings")
    async def get_settings(self) -> SettingsResponse:
        settings_dict = _get_runtime_settings()
        return SettingsResponse(
            llm_model_name=settings_dict["llm_model_name"],
            llm_temperature=settings_dict["llm_temperature"],
            llm_max_tokens=settings_dict["llm_max_tokens"],
            llm_request_timeout_seconds=settings_dict["llm_request_timeout_seconds"],
        )

    @put("/settings")
    async def update_settings(self, data: SettingsUpdate) -> SettingsResponse:
        settings_dict = _get_runtime_settings()
        if data.llm_model_name is not None:
            settings_dict["llm_model_name"] = data.llm_model_name
        if data.llm_temperature is not None:
            settings_dict["llm_temperature"] = data.llm_temperature
        if data.llm_max_tokens is not None:
            settings_dict["llm_max_tokens"] = data.llm_max_tokens
        if data.llm_request_timeout_seconds is not None:
            settings_dict["llm_request_timeout_seconds"] = data.llm_request_timeout_seconds
        return SettingsResponse(
            llm_model_name=settings_dict["llm_model_name"],
            llm_temperature=settings_dict["llm_temperature"],
            llm_max_tokens=settings_dict["llm_max_tokens"],
            llm_request_timeout_seconds=settings_dict["llm_request_timeout_seconds"],
        )