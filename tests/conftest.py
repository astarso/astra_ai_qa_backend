import os

import pytest
from litestar import Litestar
from litestar.config.cors import CORSConfig
from litestar.di import Provide
from litestar.openapi import OpenAPIConfig
from litestar.testing import AsyncTestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base

_session_holder: dict = {"session": None}

test_db_path = "/tmp/astra_test.db"

for p in [test_db_path, test_db_path + "-wal", test_db_path + "-shm"]:
    if os.path.exists(p):
        os.remove(p)

test_engine = create_async_engine(
    f"sqlite+aiosqlite:///{test_db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
)

test_async_session = async_sessionmaker(
    test_engine,
    expire_on_commit=False,
    autoflush=True,
)


@pytest.fixture(scope="function")
async def async_session():
    async with test_async_session() as session:
        _session_holder["session"] = session
        yield session
    _session_holder["session"] = None


@pytest.fixture(scope="function", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def test_client(async_session):
    import app.config as config_module
    import app.auth.sso as sso_module
    from app.auth import oidc_callback_handler, oidc_login_handler
    from app.controllers import (
        AdminController,
        AnalyticsController,
        DeployController,
        DefectsController,
        ImportController,
        ProjectsController,
        SchedulerController,
        SearchController,
        TestCasesController,
        TestRunsController,
        WebhooksController,
    )
    from app.controllers.metrics import metrics_handler
    from app.main import healthcheck

    original_settings = config_module.settings
    original_guard = sso_module.sso_auth_guard

    test_settings = config_module.Settings(
        debug=True,
        service_name="astra-qa-test",
        database_url=f"sqlite+aiosqlite:///{test_db_path}",
        log_level="WARNING",
    )
    config_module.settings = test_settings
    sso_module.settings = test_settings

    async def _shared_db_session():
        yield _session_holder["session"]

    async def mock_guard(connection, route_handler):
        connection.state.user = sso_module.AuthenticatedUser(
            sub="debug-user",
            email="debug@example.com",
            name="Debug User",
            roles=["admin"],
        )

    sso_module.sso_auth_guard = mock_guard

    app_instance = Litestar(
        route_handlers=[
            healthcheck,
            oidc_login_handler,
            oidc_callback_handler,
            AdminController,
            ProjectsController,
            TestCasesController,
            TestRunsController,
            SchedulerController,
            DeployController,
            ImportController,
            SearchController,
            DefectsController,
            AnalyticsController,
            WebhooksController,
            metrics_handler,
        ],
        dependencies={
            "db_session": Provide(_shared_db_session, sync_to_thread=False),
        },
        cors_config=CORSConfig(
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        openapi_config=OpenAPIConfig(
            title="Astra CI-Test Platform",
            version="1.0.0",
        ),
        guards=[mock_guard],
        debug=True,
    )

    async with AsyncTestClient(app=app_instance) as client:
        yield client

    sso_module.sso_auth_guard = original_guard
    sso_module.settings = original_settings
    config_module.settings = original_settings
    _session_holder["session"] = None
