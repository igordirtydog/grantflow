from __future__ import annotations

from typing import Optional

from fastapi import HTTPException


def _validated_filter_token(
    value: Optional[str],
    *,
    allowed: set[str],
    detail: str,
) -> Optional[str]:
    token = str(value or "").strip().lower()
    if not token:
        return None
    if token not in allowed:
        raise HTTPException(status_code=400, detail=detail)
    return token
