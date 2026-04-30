"""Deploy controller for triggering CD pipeline."""
from uuid import UUID

from litestar import Controller, post
from litestar.di import Provide

from app.services.deploy import DeployService


async def provide_deploy_service() -> DeployService:
    return DeployService()


class DeployController(Controller):
    """Operations for triggering deployments."""

    path = "/api/v1/runs"
    tags = ["Deploy"]
    dependencies = {"deploy_service": Provide(provide_deploy_service)}

    @post("/{run_id:uuid}/deploy")
    async def trigger_deploy(
        self,
        run_id: UUID,
        data: dict,
        deploy_service: DeployService,
    ) -> dict:
        """
        Trigger deployment for a test run to preprod or prod environment.

        Requires approve=true in the request body to proceed.
        """
        environment = data.get("environment", "preprod")
        approve = data.get("approve", False)
        result = await deploy_service.trigger_deploy(run_id, environment, approve)
        return result