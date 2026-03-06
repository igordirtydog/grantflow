#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _build_section(title: str, items: list[tuple[str, str, str]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.append("- No artifacts found.")
        lines.append("")
        return lines
    for label, path, detail in items:
        if detail:
            lines.append(f"- `{label}`: `{path}` — {detail}")
        else:
            lines.append(f"- `{label}`: `{path}`")
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a single diligence index for generated GrantFlow demo/pilot/commercial artifacts."
    )
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--output", default="build/diligence-index.md")
    args = parser.parse_args()

    build_dir = Path(str(args.build_dir)).resolve()
    output_path = Path(str(args.output)).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pilot_pack_dirs = sorted(path for path in build_dir.glob("pilot-pack*") if path.is_dir())
    executive_pack_dirs = sorted(path for path in build_dir.glob("executive-pack*") if path.is_dir())
    oem_pack_dirs = sorted(path for path in build_dir.glob("oem-pack*") if path.is_dir())
    case_study_dirs = sorted(path for path in build_dir.glob("case-study-pack*") if path.is_dir())
    archive_dirs = sorted(path for path in build_dir.glob("pilot-archive*") if path.is_dir())
    zip_files = sorted(path for path in build_dir.glob("pilot-archive*/*.zip") if path.is_file())

    pilot_items: list[tuple[str, str, str]] = []
    for path in pilot_pack_dirs:
        benchmark_path = path / "live-runs" / "benchmark-results.json"
        detail = ""
        if benchmark_path.exists():
            rows = _read_json(benchmark_path)
            if isinstance(rows, list):
                detail = f"cases={len(rows)}"
        pilot_items.append((path.name, _safe_rel(path, build_dir), detail))

    executive_items = [(path.name, _safe_rel(path, build_dir), "") for path in executive_pack_dirs]
    oem_items = [(path.name, _safe_rel(path, build_dir), "") for path in oem_pack_dirs]
    case_items = []
    for root in case_study_dirs:
        children = sorted(path for path in root.iterdir() if path.is_dir())
        if not children:
            case_items.append((root.name, _safe_rel(root, build_dir), "no case subfolders"))
            continue
        for child in children:
            case_items.append((child.name, _safe_rel(child, build_dir), f"source={root.name}"))

    archive_items = [(path.name, _safe_rel(path, build_dir), "staging folder") for path in archive_dirs]
    archive_items.extend((path.name, _safe_rel(path, build_dir), "zip archive") for path in zip_files)

    lines: list[str] = []
    lines.append("# GrantFlow Diligence Index")
    lines.append("")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Build root: `{build_dir}`")
    lines.append("")
    lines.append("## Open Order")
    lines.append("")
    lines.append("1. Review the latest executive pack.")
    lines.append("2. Review the latest pilot scorecard and buyer brief.")
    lines.append("3. Open a representative case-study pack.")
    lines.append("4. Use the OEM pack for technical diligence.")
    lines.append("5. Use the pilot archive zip for external sharing.")
    lines.append("")
    lines.extend(_build_section("Pilot Packs", pilot_items))
    lines.extend(_build_section("Executive Packs", executive_items))
    lines.extend(_build_section("Case Study Packs", case_items))
    lines.extend(_build_section("OEM Packs", oem_items))
    lines.extend(_build_section("Pilot Archives", archive_items))
    lines.append("## Notes")
    lines.append("")
    lines.append("- This index only lists locally generated artifacts under `build/`.")
    lines.append("- It does not create or refresh packs; run the corresponding `make` targets first if needed.")
    lines.append("- Human compliance review remains mandatory before any real submission use.")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"diligence index saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
