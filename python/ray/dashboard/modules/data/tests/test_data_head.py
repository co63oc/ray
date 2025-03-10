import os
import sys

import pytest
import requests

import ray
from ray.job_submission import JobSubmissionClient

# For local testing on a Macbook, set `export TEST_ON_DARWIN=1`.
TEST_ON_DARWIN = os.environ.get("TEST_ON_DARWIN", "0") == "1"

DATA_HEAD_URLS = {"GET": "http://localhost:8265/api/data/datasets/{job_id}"}

DATA_SCHEMA = [
    "state",
    "progress",
    "total",
    "total_rows",
    "ray_data_output_rows",
    "ray_data_spilled_bytes",
    "ray_data_current_bytes",
    "ray_data_cpu_usage_cores",
    "ray_data_gpu_usage_cores",
]

RESPONSE_SCHEMA = [
    "dataset",
    "job_id",
    "start_time",
    "end_time",
    "operators",
] + DATA_SCHEMA

OPERATOR_SCHEMA = [
    "name",
    "operator",
] + DATA_SCHEMA


@pytest.mark.skipif(
    sys.platform == "darwin" and not TEST_ON_DARWIN, reason="Flaky on OSX."
)
def test_get_datasets():
    ray.init()
    ds = ray.data.range(100, override_num_blocks=20).map_batches(lambda x: x)
    ds._set_name("data_head_test")
    ds.materialize()

    client = JobSubmissionClient()
    jobs = client.list_jobs()
    assert len(jobs) == 1, jobs
    job_id = jobs[0].job_id

    data = requests.get(DATA_HEAD_URLS["GET"].format(job_id=job_id)).json()

    assert len(data["datasets"]) == 1
    assert sorted(data["datasets"][0].keys()) == sorted(RESPONSE_SCHEMA)

    dataset = data["datasets"][0]
    assert dataset["dataset"].startswith("data_head_test")
    assert dataset["job_id"] == job_id
    assert dataset["state"] == "FINISHED"
    assert dataset["end_time"] is not None

    operators = dataset["operators"]
    assert len(operators) == 2
    op0 = operators[0]
    op1 = operators[1]
    assert sorted(op0.keys()) == sorted(OPERATOR_SCHEMA)
    assert sorted(op1.keys()) == sorted(OPERATOR_SCHEMA)
    assert {
        "operator": "Input0",
        "name": "Input",
        "state": "FINISHED",
        "progress": 20,
        "total": 20,
    }.items() <= op0.items()
    assert {
        "operator": "ReadRange->MapBatches(<lambda>)1",
        "name": "ReadRange->MapBatches(<lambda>)",
        "state": "FINISHED",
        "progress": 20,
        "total": 20,
    }.items() <= op1.items()

    ds.map_batches(lambda x: x).materialize()
    data = requests.get(DATA_HEAD_URLS["GET"].format(job_id=job_id)).json()

    assert len(data["datasets"]) == 2
    dataset = data["datasets"][1]
    assert dataset["dataset"].startswith("data_head_test")
    assert dataset["job_id"] == job_id
    assert dataset["state"] == "FINISHED"
    assert dataset["end_time"] is not None


if __name__ == "__main__":
    sys.exit(pytest.main(["-vv", __file__]))
