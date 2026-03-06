#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping

PRODUCTION_ENV_TOKENS = {"prod", "production"}
VALID_REDIS_URL_PREFIXES = ("redis://", "rediss://")
CheckStatus = Literal["pass", "warn", "fail"]
Role = Literal["api", "worker"]


@dataclass
class CheckResult:
    code: str
    status: CheckStatus
    message: str


def _env(env: Mapping[str, str], name: str, default: str = "") -> str:
    legacy = name.replace("GRANTFLOW_", "AIDGRAPH_", 1) if name.startswith("GRANTFLOW_") else name
    return str(env.get(name, env.get(legacy, default)) or "").strip()


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    token = _env(env, name, "")
    if not token:
        return bool(default)
    return token.lower() == "true"


def _is_python_runtime_supported(version_info: tuple[int, int]) -> bool:
    major, minor = version_info
    return major == 3 and 11 <= minor <= 13


def run_preflight(
    env: Mapping[str, str],
    *,
    role: Role,
    allow_non_production: bool,
    version_info: tuple[int, int],
) -> list[CheckResult]:
    checks: list[CheckResult] = []

    runtime_label = f"{version_info[0]}.{version_info[1]}"
    checks.append(
        CheckResult(
            code="PYTHON_RUNTIME_SUPPORTED",
            status="pass" if _is_python_runtime_supported(version_info) else "fail",
            message=f"Python runtime must be 3.11-3.13 (current={runtime_label})",
        )
    )

    environment = _env(env, "GRANTFLOW_ENV", "dev").lower()
    production_mode = environment in PRODUCTION_ENV_TOKENS
    if production_mode:
        checks.append(
            CheckResult(
                code="ENVIRONMENT_PRODUCTION",
                status="pass",
                message=f"Environment is production-like (GRANTFLOW_ENV={environment})",
            )
        )
    elif allow_non_production:
        checks.append(
            CheckResult(
                code="ENVIRONMENT_PRODUCTION",
                status="warn",
                message=(
                    f"Environment is not production-like (GRANTFLOW_ENV={environment or 'unset'}); "
                    "continuing due to --allow-non-production"
                ),
            )
        )
    else:
        checks.append(
            CheckResult(
                code="ENVIRONMENT_PRODUCTION",
                status="fail",
                message=f"GRANTFLOW_ENV must be prod|production (current={environment or 'unset'})",
            )
        )

    job_runner_mode = _env(env, "GRANTFLOW_JOB_RUNNER_MODE", "background_tasks").lower()
    checks.append(
        CheckResult(
            code="JOB_RUNNER_MODE_RECOMMENDED",
            status="pass" if job_runner_mode == "redis_queue" else "fail",
            message=f"GRANTFLOW_JOB_RUNNER_MODE should be redis_queue (current={job_runner_mode})",
        )
    )

    consumer_enabled = _env_bool(env, "GRANTFLOW_JOB_RUNNER_CONSUMER_ENABLED", True)
    if role == "api":
        consumer_ok = not consumer_enabled
        expected = "false"
    else:
        consumer_ok = consumer_enabled
        expected = "true"
    checks.append(
        CheckResult(
            code="RUNNER_ROLE_CONSUMER_ALIGNMENT",
            status="pass" if consumer_ok else "fail",
            message=(
                f"Role '{role}' expects GRANTFLOW_JOB_RUNNER_CONSUMER_ENABLED={expected} "
                f"(current={'true' if consumer_enabled else 'false'})"
            ),
        )
    )

    redis_url = _env(env, "GRANTFLOW_JOB_RUNNER_REDIS_URL", "redis://127.0.0.1:6379/0")
    redis_ok = redis_url.startswith(VALID_REDIS_URL_PREFIXES)
    checks.append(
        CheckResult(
            code="REDIS_URL_CONFIGURED",
            status="pass" if redis_ok else "fail",
            message=(
                "GRANTFLOW_JOB_RUNNER_REDIS_URL must start with redis:// or rediss:// "
                f"(current={redis_url or 'unset'})"
            ),
        )
    )

    job_store = _env(env, "GRANTFLOW_JOB_STORE", "inmem").lower()
    hitl_store = _env(env, "GRANTFLOW_HITL_STORE", "inmem").lower()
    ingest_store = _env(env, "GRANTFLOW_INGEST_STORE", "inmem").lower()
    for code, name, value in (
        ("JOB_STORE_PERSISTENT", "GRANTFLOW_JOB_STORE", job_store),
        ("HITL_STORE_PERSISTENT", "GRANTFLOW_HITL_STORE", hitl_store),
        ("INGEST_STORE_PERSISTENT", "GRANTFLOW_INGEST_STORE", ingest_store),
    ):
        checks.append(
            CheckResult(
                code=code,
                status="pass" if value == "sqlite" else "fail",
                message=f"{name} must be sqlite for production baseline (current={value})",
            )
        )

    aligned = job_store == hitl_store
    checks.append(
        CheckResult(
            code="JOB_HITL_STORE_ALIGNMENT",
            status="pass" if aligned else "fail",
            message=f"JOB/HITL stores must match (job={job_store}, hitl={hitl_store})",
        )
    )

    sqlite_path = _env(env, "GRANTFLOW_SQLITE_PATH", "")
    checks.append(
        CheckResult(
            code="SQLITE_PATH_CONFIGURED",
            status="pass" if bool(sqlite_path) else "fail",
            message=(
                "GRANTFLOW_SQLITE_PATH should be set when sqlite stores are enabled "
                f"(current={'set' if sqlite_path else 'unset'})"
            ),
        )
    )

    if role == "api":
        api_key = _env(env, "GRANTFLOW_API_KEY", _env(env, "API_KEY", ""))
        checks.append(
            CheckResult(
                code="API_KEY_CONFIGURED",
                status="pass" if bool(api_key) else "fail",
                message="GRANTFLOW_API_KEY must be configured for production API nodes",
            )
        )

    require_api_key_guard = _env_bool(env, "GRANTFLOW_REQUIRE_API_KEY_ON_STARTUP", default=production_mode)
    checks.append(
        CheckResult(
            code="STARTUP_API_KEY_GUARD",
            status="pass" if require_api_key_guard else "warn",
            message=(
                "Startup API key guard should remain enabled in production "
                "(GRANTFLOW_REQUIRE_API_KEY_ON_STARTUP=true)"
            ),
        )
    )

    require_persistent_guard = _env_bool(
        env,
        "GRANTFLOW_REQUIRE_PERSISTENT_STORES_ON_STARTUP",
        default=production_mode,
    )
    checks.append(
        CheckResult(
            code="STARTUP_PERSISTENT_STORE_GUARD",
            status="pass" if require_persistent_guard else "warn",
            message=(
                "Startup persistent-store guard should remain enabled in production "
                "(GRANTFLOW_REQUIRE_PERSISTENT_STORES_ON_STARTUP=true)"
            ),
        )
    )

    return checks


def _print_results(role: Role, checks: list[CheckResult]) -> None:
    print(f"GrantFlow production preflight ({role})")
    for item in checks:
        print(f"[{item.status}] {item.code}: {item.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production baseline runtime configuration.")
    parser.add_argument(
        "--role",
        choices=("api", "worker"),
        default="api",
        help="Node role profile (api or worker).",
    )
    parser.add_argument(
        "--allow-non-production",
        action="store_true",
        help="Do not fail only because GRANTFLOW_ENV is not prod|production.",
    )
    parser.add_argument(
        "--python-version",
        default="",
        help="Optional python version override in 'major.minor' format for validation.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root (for consistent script contract; currently informational).",
    )
    args = parser.parse_args()

    _ = Path(args.repo_root).resolve()
    if str(args.python_version or "").strip():
        token = str(args.python_version).strip()
        parts = token.split(".", 1)
        if len(parts) != 2:
            raise SystemExit(f"--python-version must be 'major.minor', got: {token}")
        try:
            version_info = (int(parts[0]), int(parts[1]))
        except ValueError as exc:
            raise SystemExit(f"--python-version must be numeric major.minor, got: {token}") from exc
    else:
        version_info = (int(sys.version_info[0]), int(sys.version_info[1]))
    checks = run_preflight(
        os.environ,
        role=str(args.role),
        allow_non_production=bool(args.allow_non_production),
        version_info=version_info,
    )
    _print_results(str(args.role), checks)
    has_failures = any(item.status == "fail" for item in checks)
    has_warnings = any(item.status == "warn" for item in checks)
    if has_failures:
        print("Preflight status: FAILED")
        return 1
    if has_warnings:
        print("Preflight status: PASSED_WITH_WARNINGS")
        return 0
    print("Preflight status: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
