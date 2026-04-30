"""Deploy trigger service for CD pipeline."""
import logging
import uuid
from uuid import UUID

logger = logging.getLogger(__name__)


class DeployService:
    """Service for triggering deployments to preprod/prod."""

    async def trigger_deploy(
        self, run_id: UUID, environment: str, approve: bool = False
    ) -> dict:
        """
        Trigger deployment for a run.

        Args:
            run_id: The test run ID
            environment: 'preprod' or 'prod'
            approve: Whether to auto-approve deployment

        Returns:
            dict with deployment_id, status, message
        """
        if environment not in ("preprod", "prod"):
            raise ValueError(f"Invalid environment: {environment}. Must be 'preprod' or 'prod'")

        if not approve:
            raise ValueError("Deploy not approved — set approve=true to proceed")

        # TODO: Integrate with actual CI/CD system (GitLab CI, ArgoCD, etc.)
        # For now, just log the intent
        logger.info(
            "Deploy triggered: run_id=%s, environment=%s, approved=%s",
            run_id, environment, approve
        )

        deployment_id = str(uuid.uuid4())

        return {
            "deployment_id": deployment_id,
            "run_id": str(run_id),
            "environment": environment,
            "status": "triggered",
            "message": f"Deployment to {environment} triggered for run {run_id}",
        }