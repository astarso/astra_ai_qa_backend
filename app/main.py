from litestar import Litestar, WebSocket, get, websocket
from litestar.config.cors import CORSConfig
from litestar.di import Provide
from litestar.logging import LoggingConfig
from litestar.openapi import OpenAPIConfig

from app.auth import oidc_callback_handler, oidc_login_handler, sso_auth_guard
from app.config import settings
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
    TestSuitesController,
    WebhooksController,
)
from app.controllers.metrics import metrics_handler
from app.db import plugin as sqlalchemy_plugin, provide_db_session
from app.services.ws_manager import ws_manager

logging_config = LoggingConfig(
    root={
        "level": settings.log_level,
        "handlers": ["queue_listener"],
    },
    formatters={
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    log_exceptions="always",
    disable_stack_trace={404, ValueError},
)


@get("/api/v1/health", exclude_from_auth=True)
async def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@websocket(path="/api/v1/ws/runs/{run_id:str}", exclude_from_auth=True)
async def run_status_ws(socket: WebSocket, run_id: str) -> None:
    await socket.accept()
    queue = ws_manager.subscribe(run_id)
    try:
        while True:
            message = await queue.get()
            await socket.send_text(message)
    except Exception:
        pass
    finally:
        ws_manager.unsubscribe(run_id, queue)


def create_app() -> Litestar:
    return Litestar(
route_handlers=[
            healthcheck,
            run_status_ws,
            oidc_login_handler,
            oidc_callback_handler,
            AdminController,
            ProjectsController,
            TestSuitesController,
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
            "db_session": Provide(provide_db_session),
        },
        plugins=[sqlalchemy_plugin],
        cors_config=CORSConfig(
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        openapi_config=OpenAPIConfig(
            title="Astra CI-Test Platform",
            version="1.0.0",
            description="API платформы непрерывного тестирования и верификации ПО",
        ),
        logging_config=logging_config,
        guards=[sso_auth_guard],
        debug=settings.debug,
    )


app = create_app()
