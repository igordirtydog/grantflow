#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _copy_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _slugify(value: str) -> str:
    token = "".join(ch if ch.isalnum() else "-" for ch in value.strip().lower())
    while "--" in token:
        token = token.replace("--", "-")
    return token.strip("-") or "archive"


def _build_manifest(
    *,
    archive_name: str,
    pilot_pack_dir: Path,
    executive_pack_dir: Path,
    oem_pack_dir: Path,
    include_oem: bool,
    total_cases: int,
    done_cases: int,
) -> dict[str, Any]:
    return {
        "archive_name": archive_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "pilot_pack_dir": str(pilot_pack_dir),
            "executive_pack_dir": str(executive_pack_dir),
            "oem_pack_dir": str(oem_pack_dir) if include_oem else None,
        },
        "included": {
            "pilot_pack": pilot_pack_dir.exists(),
            "executive_pack": executive_pack_dir.exists(),
            "oem_pack": include_oem and oem_pack_dir.exists(),
        },
        "summary": {
            "total_cases": total_cases,
            "done_cases": done_cases,
        },
    }


def _build_readme(
    *,
    archive_name: str,
    total_cases: int,
    done_cases: int,
    include_oem: bool,
) -> str:
    lines: list[str] = []
    lines.append("# GrantFlow Pilot Archive")
    lines.append("")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Archive name: `{archive_name}`")
    lines.append("")
    lines.append("## Included Folders")
    lines.append("- `pilot-pack/`: full pilot evidence bundle")
    lines.append("- `executive-pack/`: short buyer-facing packet")
    if include_oem:
        lines.append("- `oem-pack/`: technical partner / diligence packet")
    lines.append("")
    lines.append("## Snapshot")
    lines.append(f"- Cases in pilot pack: `{total_cases}`")
    lines.append(f"- Terminal done cases: `{done_cases}/{total_cases}`")
    lines.append("")
    lines.append("## Suggested Share Order")
    lines.append("1. Start with `executive-pack/README.md`")
    lines.append("2. Review `executive-pack/buyer-brief.md` and `executive-pack/pilot-scorecard.md`")
    lines.append("3. Open `pilot-pack/README.md` for full evidence")
    if include_oem:
        lines.append("4. Use `oem-pack/README.md` for technical diligence")
    lines.append("")
    lines.append("## Notes")
    lines.append("- This archive is for pilot review and diligence, not final donor submission.")
    lines.append("- Human compliance review remains mandatory.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package GrantFlow pilot, executive, and OEM bundles into a sendable zip archive."
    )
    parser.add_argument("--pilot-pack-dir", default="build/pilot-pack")
    parser.add_argument("--executive-pack-dir", default="build/executive-pack")
    parser.add_argument("--oem-pack-dir", default="build/oem-pack")
    parser.add_argument("--output-dir", default="build/pilot-archive")
    parser.add_argument("--archive-name", default="")
    parser.add_argument("--include-oem", action="store_true")
    args = parser.parse_args()

    pilot_pack_dir = Path(str(args.pilot_pack_dir)).resolve()
    executive_pack_dir = Path(str(args.executive_pack_dir)).resolve()
    oem_pack_dir = Path(str(args.oem_pack_dir)).resolve()
    output_dir = Path(str(args.output_dir)).resolve()

    benchmark_path = pilot_pack_dir / "live-runs" / "benchmark-results.json"
    if not benchmark_path.exists():
        raise SystemExit(f"Missing pilot benchmark results: {benchmark_path}")
    rows = _read_json(benchmark_path)
    if not isinstance(rows, list) or not rows:
        raise SystemExit("pilot pack live-runs/benchmark-results.json must contain a non-empty list")

    if not executive_pack_dir.exists():
        raise SystemExit(f"Missing executive pack directory: {executive_pack_dir}. Run make executive-pack first.")
    if bool(args.include_oem) and not oem_pack_dir.exists():
        raise SystemExit(f"Missing oem pack directory: {oem_pack_dir}. Run make oem-pack first.")

    archive_name = str(args.archive_name).strip() or _slugify(pilot_pack_dir.name)
    staging_dir = output_dir / archive_name
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    _copy_tree(pilot_pack_dir, staging_dir / "pilot-pack")
    _copy_tree(executive_pack_dir, staging_dir / "executive-pack")
    if bool(args.include_oem):
        _copy_tree(oem_pack_dir, staging_dir / "oem-pack")

    done_cases = sum(1 for row in rows if str(row.get("status") or "").strip().lower() == "done")
    manifest = _build_manifest(
        archive_name=archive_name,
        pilot_pack_dir=pilot_pack_dir,
        executive_pack_dir=executive_pack_dir,
        oem_pack_dir=oem_pack_dir,
        include_oem=bool(args.include_oem),
        total_cases=len(rows),
        done_cases=done_cases,
    )
    (staging_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (staging_dir / "README.md").write_text(
        _build_readme(
            archive_name=archive_name,
            total_cases=len(rows),
            done_cases=done_cases,
            include_oem=bool(args.include_oem),
        ),
        encoding="utf-8",
    )

    zip_base = output_dir / archive_name
    zip_path = Path(shutil.make_archive(str(zip_base), "zip", root_dir=output_dir, base_dir=archive_name))
    _copy_if_exists(zip_path, output_dir / f"{archive_name}-latest.zip")
    print(f"pilot archive saved to {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
