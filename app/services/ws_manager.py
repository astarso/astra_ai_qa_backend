"""WebSocket connection manager for real-time test run updates."""
import asyncio
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConnectionManager:
    """Manages WebSocket connections for test run updates."""
    _connections: dict[str, list[asyncio.Queue]] = field(default_factory=dict)

    def subscribe(self, run_id: str) -> asyncio.Queue:
        """Subscribe to updates for a specific run. Returns a queue to consume messages from."""
        queue = asyncio.Queue()
        if run_id not in self._connections:
            self._connections[run_id] = []
        self._connections[run_id].append(queue)
        logger.info("Client subscribed to run %s (total: %d)", run_id, len(self._connections[run_id]))
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from updates for a specific run."""
        if run_id in self._connections:
            try:
                self._connections[run_id].remove(queue)
            except ValueError:
                pass
            if not self._connections[run_id]:
                del self._connections[run_id]
        logger.info("Client unsubscribed from run %s", run_id)

    async def broadcast(self, run_id: str, message: dict) -> None:
        """Broadcast a message to all subscribers of a specific run."""
        if run_id not in self._connections:
            return
        dead_queues = []
        for queue in self._connections[run_id]:
            try:
                queue.put_nowait(json.dumps(message))
            except asyncio.QueueFull:
                dead_queues.append(queue)
        for q in dead_queues:
            self.unsubscribe(run_id, q)

    def get_stats(self) -> dict:
        """Get connection statistics."""
        return {
            "active_runs": len(self._connections),
            "total_connections": sum(len(qs) for qs in self._connections.values()),
        }


# Singleton instance
ws_manager = ConnectionManager()


# NOTE: To integrate with orchestration, call ws_manager.broadcast(run_id, message)
# from app/services/orchestration.py in the _recompute_run_status method when
# run status changes (pending -> running -> passed/failed).
# Example:
#   await ws_manager.broadcast(run_id, {"status": new_status, "run_id": run_id})
