#!/usr/bin/env bash
set -euo pipefail
API_BASE="${API_BASE:-http://127.0.0.1:8000}"
API_KEY="${API_KEY:-}"
MANIFEST="${MANIFEST:-docs/rag_seed_corpus/ingest_manifest.jsonl}"
DONOR_IDS="${DONOR_IDS:-}"

if [[ ! -f "$MANIFEST" ]]; then
  echo "Manifest not found: $MANIFEST" >&2
  exit 1
fi

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  donor_id=$(python3 -c 'import sys,json; print(json.loads(sys.argv[1])["donor_id"])' "$line")
  if [[ -n "$DONOR_IDS" ]]; then
    include=$(python3 -c 'import sys; donor=sys.argv[1].strip().lower(); allowed={item.strip().lower() for item in sys.argv[2].split(",") if item.strip()}; print("1" if donor in allowed else "0")' "$donor_id" "$DONOR_IDS")
    if [[ "$include" != "1" ]]; then
      continue
    fi
  fi
  file=$(python3 -c 'import sys,json; print(json.loads(sys.argv[1])["file"])' "$line")
  metadata=$(python3 -c 'import sys,json; print(json.dumps(json.loads(sys.argv[1])["metadata"]))' "$line")
  echo "Uploading $file -> donor_id=$donor_id"
  if [[ -n "$API_KEY" ]]; then
    curl -fsS -X POST "$API_BASE/ingest" -H "X-API-Key: $API_KEY" -F "donor_id=$donor_id" -F "metadata_json=$metadata" -F "file=@$file" >/dev/null
  else
    curl -fsS -X POST "$API_BASE/ingest" -F "donor_id=$donor_id" -F "metadata_json=$metadata" -F "file=@$file" >/dev/null
  fi
  echo "  ok"
done < "$MANIFEST"

echo "Seed corpus ingest completed."
