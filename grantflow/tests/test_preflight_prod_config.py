from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "preflight_prod_config.py"


def _run_preflight(*args: str, env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {"PATH": str(Path(sys.executable).parent)}
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=str(_repo_root()),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_preflight_prod_config_passes_recommended_api_profile():
    completed = _run_preflight(
        "--role",
        "api",
        "--python-version",
        "3.11",
        env_overrides={
            "GRANTFLOW_ENV": "production",
            "GRANTFLOW_JOB_RUNNER_MODE": "redis_queue",
            "GRANTFLOW_JOB_RUNNER_CONSUMER_ENABLED": "false",
            "GRANTFLOW_JOB_RUNNER_REDIS_URL": "redis://127.0.0.1:6379/0",
            "GRANTFLOW_JOB_STORE": "sqlite",
            "GRANTFLOW_HITL_STORE": "sqlite",
            "GRANTFLOW_INGEST_STORE": "sqlite",
            "GRANTFLOW_SQLITE_PATH": "./.data/grantflow_state.db",
            "GRANTFLOW_API_KEY": "test-secret",
            "GRANTFLOW_REQUIRE_API_KEY_ON_STARTUP": "true",
            "GRANTFLOW_REQUIRE_PERSISTENT_STORES_ON_STARTUP": "true",
        },
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Preflight status: PASSED" in completed.stdout


def test_preflight_prod_config_fails_when_env_is_not_production():
    completed = _run_preflight(
        "--role",
        "api",
        "--python-version",
        "3.11",
        env_overrides={
            "GRANTFLOW_ENV": "dev",
            "GRANTFLOW_JOB_RUNNER_MODE": "redis_queue",
            "GRANTFLOW_JOB_RUNNER_CONSUMER_ENABLED": "false",
            "GRANTFLOW_JOB_RUNNER_REDIS_URL": "redis://127.0.0.1:6379/0",
            "GRANTFLOW_JOB_STORE": "sqlite",
            "GRANTFLOW_HITL_STORE": "sqlite",
            "GRANTFLOW_INGEST_STORE": "sqlite",
            "GRANTFLOW_SQLITE_PATH": "./.data/grantflow_state.db",
            "GRANTFLOW_API_KEY": "test-secret",
        },
    )
    assert completed.returncode == 1
    assert "ENVIRONMENT_PRODUCTION" in completed.stdout
    assert "Preflight status: FAILED" in completed.stdout


def test_preflight_prod_config_fails_when_persistent_stores_are_not_sqlite():
    completed = _run_preflight(
        "--role",
        "api",
        "--python-version",
        "3.11",
        env_overrides={
            "GRANTFLOW_ENV": "production",
            "GRANTFLOW_JOB_RUNNER_MODE": "redis_queue",
            "GRANTFLOW_JOB_RUNNER_CONSUMER_ENABLED": "false",
            "GRANTFLOW_JOB_RUNNER_REDIS_URL": "redis://127.0.0.1:6379/0",
            "GRANTFLOW_JOB_STORE": "inmem",
            "GRANTFLOW_HITL_STORE": "inmem",
            "GRANTFLOW_INGEST_STORE": "inmem",
            "GRANTFLOW_SQLITE_PATH": "./.data/grantflow_state.db",
            "GRANTFLOW_API_KEY": "test-secret",
        },
    )
    assert completed.returncode == 1
    assert "JOB_STORE_PERSISTENT" in completed.stdout
    assert "HITL_STORE_PERSISTENT" in completed.stdout
    assert "INGEST_STORE_PERSISTENT" in completed.stdout


def test_preflight_prod_config_passes_worker_profile():
    completed = _run_preflight(
        "--role",
        "worker",
        "--python-version",
        "3.11",
        env_overrides={
            "GRANTFLOW_ENV": "production",
            "GRANTFLOW_JOB_RUNNER_MODE": "redis_queue",
            "GRANTFLOW_JOB_RUNNER_CONSUMER_ENABLED": "true",
            "GRANTFLOW_JOB_RUNNER_REDIS_URL": "redis://127.0.0.1:6379/0",
            "GRANTFLOW_JOB_STORE": "sqlite",
            "GRANTFLOW_HITL_STORE": "sqlite",
            "GRANTFLOW_INGEST_STORE": "sqlite",
            "GRANTFLOW_SQLITE_PATH": "./.data/grantflow_state.db",
            "GRANTFLOW_REQUIRE_API_KEY_ON_STARTUP": "true",
            "GRANTFLOW_REQUIRE_PERSISTENT_STORES_ON_STARTUP": "true",
        },
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Preflight status: PASSED" in completed.stdout
