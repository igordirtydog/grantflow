# LLM Smoke (Economy) — 2026-03-03

Model profile: `openai/gpt-4o-mini` via OpenRouter (`--force-llm --force-architect-rag --skip-expectations`).
Goal: quick budget-safe validation of grounded LLM path on 3 donors.

| Donor | Case | Q | Critic | Flaws | Citations | Fallback NS | Low Conf | Traceability Gap | Key Claim Coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| usaid | usaid_ai_civil_service_kazakhstan | 9.25 | 9.25 | 0 | 18 | 0 | 0 | 0 | 1.0 |
| worldbank | worldbank_public_sector_performance_uzbekistan | 9.25 | 9.25 | 0 | 14 | 0 | 0 | 0 | 1.0 |
| eu | eu_digital_governance_services_moldova | 9.25 | 9.25 | 0 | 13 | 0 | 0 | 0 | 1.0 |

## Outcome
- All 3 smoke cases passed.
- Zero fallback / low-confidence / traceability-gap citations in this smoke batch.
- Use full suite only when budget allows; this smoke profile is intended for fast sanity checks.

## Artifacts
- `llm-smoke-economy.json` / `llm-smoke-economy.txt` (USAID)
- `llm-smoke-economy-wb.json` / `llm-smoke-economy-wb.txt` (World Bank)
- `llm-smoke-economy-eu.json` / `llm-smoke-economy-eu.txt` (EU)
