#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    import tomllib
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"tomllib is required (Python 3.11+): {exc}")


PIN_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[^\s;]+$")


def _check(condition: bool, ok_message: str, fail_message: str, errors: list[str]) -> None:
    if condition:
        print(f"[ok] {ok_message}")
    else:
        errors.append(fail_message)
        print(f"[fail] {fail_message}")


def _canonical_non_comment_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def _check_pinned_deps(
    deps: list[str],
    *,
    group_name: str,
    errors: list[str],
) -> None:
    _check(bool(deps), f"{group_name} dependencies present", f"{group_name} dependencies are empty", errors)
    for dep in deps:
        ok = bool(PIN_PATTERN.match(dep))
        _check(
            ok,
            f"{group_name} dependency is pinned: {dep}",
            f"{group_name} dependency must be pinned with == : {dep}",
            errors,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dependency packaging contract.")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root path (default: auto-detected).",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    pyproject_path = repo_root / "pyproject.toml"
    root_requirements_path = repo_root / "requirements.txt"
    root_requirements_dev_path = repo_root / "requirements-dev.txt"
    grantflow_requirements_path = repo_root / "grantflow" / "requirements.txt"

    errors: list[str] = []

    _check(pyproject_path.exists(), "pyproject.toml present", "pyproject.toml missing", errors)
    if not pyproject_path.exists():
        print("\nDependency guard failed.")
        return 1

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject.get("project") if isinstance(pyproject, dict) else {}
    project = project if isinstance(project, dict) else {}

    runtime_deps_raw = project.get("dependencies")
    runtime_deps = runtime_deps_raw if isinstance(runtime_deps_raw, list) else []
    runtime_deps = [str(item).strip() for item in runtime_deps if str(item).strip()]
    _check_pinned_deps(runtime_deps, group_name="runtime", errors=errors)

    optional_raw = project.get("optional-dependencies")
    optional = optional_raw if isinstance(optional_raw, dict) else {}
    dev_deps_raw = optional.get("dev") if isinstance(optional, dict) else None
    dev_deps = dev_deps_raw if isinstance(dev_deps_raw, list) else []
    dev_deps = [str(item).strip() for item in dev_deps if str(item).strip()]
    _check_pinned_deps(dev_deps, group_name="dev", errors=errors)

    root_requirements = _canonical_non_comment_lines(root_requirements_path)
    root_requirements_dev = _canonical_non_comment_lines(root_requirements_dev_path)
    grantflow_requirements = _canonical_non_comment_lines(grantflow_requirements_path)

    _check(
        root_requirements == ["-e ."],
        "requirements.txt is canonical shim (-e .)",
        "requirements.txt must contain only: -e .",
        errors,
    )
    _check(
        root_requirements_dev == [".[dev]"],
        "requirements-dev.txt is canonical shim (.[dev])",
        "requirements-dev.txt must contain only: .[dev]",
        errors,
    )
    _check(
        grantflow_requirements == ["-e .."],
        "grantflow/requirements.txt is canonical shim (-e ..)",
        "grantflow/requirements.txt must contain only: -e ..",
        errors,
    )

    if errors:
        print("\nDependency guard failed with the following issue(s):")
        for idx, error in enumerate(errors, start=1):
            print(f"{idx}. {error}")
        return 1

    print("\nDependency guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
