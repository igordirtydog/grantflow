from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from grantflow.eval.summary import build_eval_summary_markdown


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        return loaded
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build unified markdown summary for LLM eval workflow outputs.")
    parser.add_argument("--report-json", type=Path, required=True, help="Path to eval report json.")
    parser.add_argument("--comparison-json", type=Path, default=None, help="Optional baseline comparison json.")
    parser.add_argument("--gate-json", type=Path, default=None, help="Optional donor gate json.")
    parser.add_argument("--title", type=str, default="LLM Eval Summary", help="Markdown heading title.")
    parser.add_argument("--out-md", type=Path, default=None, help="Optional output markdown path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report_payload = _load_json(args.report_json)
    if not isinstance(report_payload, dict):
        raise SystemExit("report-json root must be an object")
    comparison_payload = _load_json(args.comparison_json)
    gate_payload = _load_json(args.gate_json)

    markdown = build_eval_summary_markdown(
        report_payload,
        title=str(args.title),
        comparison_payload=comparison_payload,
        gate_payload=gate_payload,
    )
    if args.out_md is not None:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(markdown, encoding="utf-8")
    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
