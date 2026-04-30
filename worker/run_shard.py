"""Standalone worker process that connects to RabbitMQ and executes test shards.

Usage: python -m worker.run_shard
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import aio_pika
import httpx

logger = logging.getLogger(__name__)

# Config (from env or defaults)
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
QUEUE_NAME = os.environ.get("TASKIQ_QUEUE_NAME", "taskiq")
API_BASE_URL = os.environ.get("ASTRA_API_URL", "http://localhost:8000/api/v1")


async def process_shard(message: aio_pika.abc.AbstractIncomingMessage):
    """Process a single shard message from RabbitMQ."""
    async with message.process():
        try:
            body = json.loads(message.body.decode())
            logger.info(f"Received shard: {body}")

            # Extract shard info
            run_id = body.get("run_id", "")
            shard_index = body.get("shard_index", 0)
            test_case_ids = body.get("test_case_ids", [])

            if not run_id or not test_case_ids:
                logger.warning("Invalid shard message, skipping")
                return

            # Run pytest with junitxml output
            report_file = f"/tmp/shard_{run_id}_{shard_index}.xml"
            test_ids_str = " ".join(test_case_ids)

            result = await asyncio.to_thread(
                subprocess.run,
                ["python", "-m", "pytest", "-v", f"--junitxml={report_file}", test_ids_str],
                capture_output=True,
                text=True,
                timeout=300,
            )

            # Parse JUnit XML results
            results = parse_junit_xml(report_file, run_id)

            # Submit results back to API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{API_BASE_URL}/runs/{run_id}/results",
                    json={"results": results},
                )
                logger.info(f"Submitted {len(results)} results: {response.status_code}")

            # Cleanup report file
            Path(report_file).unlink(missing_ok=True)

        except subprocess.TimeoutExpired:
            logger.error(f"Shard {shard_index} timed out")
        except Exception as e:
            logger.error(f"Error processing shard: {e}")


def parse_junit_xml(filepath: str, run_id: str) -> list[dict]:
    """Parse JUnit XML and return result dicts."""
    results = []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        for testcase in root.iter("testcase"):
            name = testcase.get("name", "unknown")
            classname = testcase.get("classname", "")
            duration = float(testcase.get("time", 0)) * 1000  # ms

            failure = testcase.find("failure")
            error = testcase.find("error")

            if failure is not None:
                status = "failed"
                error_msg = failure.get("message", failure.text or "")
            elif error is not None:
                status = "failed"
                error_msg = error.get("message", error.text or "")
            elif testcase.find("skipped") is not None:
                status = "skipped"
                error_msg = ""
            else:
                status = "passed"
                error_msg = ""

            results.append({
                "test_case_id": name,  # In real usage, map to actual UUIDs
                "status": status,
                "duration_ms": duration,
                "error_message": error_msg,
            })
    except (ET.ParseError, FileNotFoundError) as e:
        logger.warning(f"Failed to parse JUnit XML: {e}")

    return results


async def main():
    """Main worker loop — connect to RabbitMQ and consume messages."""
    logger.info(f"Connecting to RabbitMQ at {RABBITMQ_URL}")

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(QUEUE_NAME, durable=True)

        logger.info(f"Worker started, listening on queue '{QUEUE_NAME}'")
        await queue.consume(process_shard)

        # Keep running
        await asyncio.Future()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())