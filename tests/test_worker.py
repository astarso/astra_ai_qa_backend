import os
import pytest
import tempfile
from worker.run_shard import parse_junit_xml


@pytest.mark.asyncio
async def test_parse_junit_xml_with_failures():
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="suite" tests="3" failures="1" errors="0">
  <testcase name="test_pass" classname="tests.Sample" time="0.1"/>
  <testcase name="test_fail" classname="tests.Sample" time="0.2">
    <failure message="AssertionError: expected True">Traceback...</failure>
  </testcase>
  <testcase name="test_skip" classname="tests.Sample" time="0.0">
    <skipped message="Not ready"/>
  </testcase>
</testsuite>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(xml_content)
        f.flush()
        results = parse_junit_xml(f.name, "test-run-id")

    os.unlink(f.name)
    assert len(results) == 3
    assert results[0]["status"] == "passed"
    assert results[1]["status"] == "failed"
    assert results[2]["status"] == "skipped"
    assert results[0]["duration_ms"] == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_parse_junit_xml_missing_file():
    results = parse_junit_xml("/tmp/nonexistent_file_12345.xml", "test-run-id")
    assert results == []