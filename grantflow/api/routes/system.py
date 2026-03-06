from __future__ import annotations

from fastapi import HTTPException

from grantflow.api.diagnostics_service import _health_diagnostics
from grantflow.api.readiness_service import _build_readiness_payload
from grantflow.api.routers import system_router
from grantflow.core.version import __version__


@system_router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "version": __version__,
        "diagnostics": _health_diagnostics(),
    }


@system_router.get("/ready")
def readiness_check():
    payload = _build_readiness_payload()
    if str(payload.get("status") or "").strip().lower() != "ready":
        raise HTTPException(status_code=503, detail=payload)
    return payload
