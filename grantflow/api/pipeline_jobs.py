from __future__ import annotations

from typing import Any, Callable, Dict, Literal

from fastapi import BackgroundTasks, HTTPException

from grantflow.api import app as api_app_module
from grantflow.swarm.hitl import HITLStatus

HITLStartAt = Literal["start", "architect", "mel", "critic"]


def _dispatch_pipeline_task(background_tasks: BackgroundTasks, fn: Callable[..., None], *args: Any) -> str:
    if api_app_module._uses_queue_runner():
        accepted = api_app_module.JOB_RUNNER.submit(fn, *args)
        if not accepted:
            raise HTTPException(status_code=503, detail="Job queue is full. Retry shortly.")
        return api_app_module._job_runner_mode()
    background_tasks.add_task(fn, *args)
    return "background_tasks"


def _record_hitl_feedback_in_state(state: dict, checkpoint: Dict[str, Any]) -> None:
    feedback = checkpoint.get("feedback")
    if not feedback:
        return
    history = list(state.get("hitl_feedback_history") or [])
    history.append(
        {
            "checkpoint_id": checkpoint.get("id"),
            "stage": checkpoint.get("stage"),
            "status": getattr(checkpoint.get("status"), "value", checkpoint.get("status")),
            "feedback": feedback,
        }
    )
    state["hitl_feedback_history"] = history
    state["hitl_feedback"] = feedback


def _checkpoint_status_token(checkpoint: Dict[str, Any]) -> str:
    raw = checkpoint.get("status")
    return str(getattr(raw, "value", raw) or "").strip().lower()


def _run_pipeline_to_completion(job_id: str, initial_state: dict) -> None:
    try:
        if api_app_module._job_is_canceled(job_id):
            return
        api_app_module.normalize_state_contract(initial_state)
        _clear_hitl_runtime_state(initial_state, clear_pending=True)
        initial_state["hitl_enabled"] = False
        initial_state["_start_at"] = "start"
        api_app_module._set_job(job_id, {"status": "running", "state": initial_state, "hitl_enabled": False})
        if api_app_module._job_is_canceled(job_id):
            return
        final_state = api_app_module.grantflow_graph.invoke(initial_state)
        for key in api_app_module.RUNTIME_PIPELINE_STATE_KEYS:
            final_state.pop(key, None)
        final_state["hitl_pending"] = False
        api_app_module.normalize_state_contract(final_state)
        api_app_module._attach_export_contract_gate(final_state)
        runtime_grounded_gate = api_app_module._evaluate_runtime_grounded_quality_gate_from_state(final_state)
        final_state["grounded_quality_gate"] = runtime_grounded_gate
        if api_app_module._job_is_canceled(job_id):
            return
        runtime_grounded_block_reason = api_app_module._runtime_grounded_quality_gate_block_reason(final_state)
        if runtime_grounded_block_reason:
            api_app_module._append_runtime_grounded_quality_gate_finding(final_state, runtime_grounded_gate)
            api_app_module._record_job_event(
                job_id,
                "runtime_grounded_quality_gate_blocked",
                mode=str(runtime_grounded_gate.get("mode") or "strict"),
                summary=str(runtime_grounded_gate.get("summary") or ""),
                reasons=list(runtime_grounded_gate.get("reasons") or []),
            )
            api_app_module._set_job(
                job_id,
                {
                    "status": "error",
                    "error": runtime_grounded_block_reason,
                    "state": final_state,
                    "hitl_enabled": False,
                },
            )
            return
        grounding_block_reason = api_app_module._grounding_gate_block_reason(final_state)
        if grounding_block_reason:
            api_app_module._set_job(
                job_id,
                {
                    "status": "error",
                    "error": grounding_block_reason,
                    "state": final_state,
                    "hitl_enabled": False,
                },
            )
            return
        mel_grounding_block_reason = api_app_module._mel_grounding_policy_block_reason(final_state)
        if mel_grounding_block_reason:
            api_app_module._set_job(
                job_id,
                {
                    "status": "error",
                    "error": mel_grounding_block_reason,
                    "state": final_state,
                    "hitl_enabled": False,
                },
            )
            return
        api_app_module._set_job(job_id, {"status": "done", "state": final_state, "hitl_enabled": False})
    except Exception as exc:
        api_app_module._set_job(job_id, {"status": "error", "error": str(exc), "hitl_enabled": False})


def _run_pipeline_to_completion_by_job_id(job_id: str) -> None:
    job = api_app_module._get_job(job_id)
    if not isinstance(job, dict):
        return
    status = str(job.get("status") or "").strip().lower()
    if status in api_app_module.TERMINAL_JOB_STATUSES:
        return
    if status == "pending_hitl":
        return
    if status not in {"accepted", "running"}:
        return
    state = job.get("state")
    if not isinstance(state, dict):
        api_app_module._set_job(job_id, {"status": "error", "error": "Job state is missing or invalid", "hitl_enabled": False})
        return
    _run_pipeline_to_completion(job_id, state)


def _run_hitl_pipeline(job_id: str, state: dict, start_at: HITLStartAt) -> None:
    try:
        if api_app_module._job_is_canceled(job_id):
            return
        api_app_module.normalize_state_contract(state)
        _clear_hitl_runtime_state(state, clear_pending=True)
        state["hitl_enabled"] = True
        state["_start_at"] = start_at
        api_app_module._set_job(
            job_id,
            {
                "status": "running",
                "state": state,
                "hitl_enabled": True,
                "resume_from": start_at,
            },
        )
        if api_app_module._job_is_canceled(job_id):
            return
        final_state = api_app_module.grantflow_graph.invoke(state)
        if api_app_module._job_is_canceled(job_id):
            return
        api_app_module.normalize_state_contract(final_state)
        checkpoint_stage = str(final_state.get("hitl_checkpoint_stage") or "").strip().lower()
        checkpoint_resume = str(final_state.get("hitl_resume_from") or "").strip().lower()
        if bool(final_state.get("hitl_pending")) and checkpoint_stage in {"toc", "logframe"}:
            stage_literal: Literal["toc", "logframe"] = "toc" if checkpoint_stage == "toc" else "logframe"
            resume_literal: HITLStartAt
            if checkpoint_resume == "start":
                resume_literal = "start"
            elif checkpoint_resume == "architect":
                resume_literal = "architect"
            elif checkpoint_resume == "mel":
                resume_literal = "mel"
            elif checkpoint_resume == "critic":
                resume_literal = "critic"
            else:
                resume_literal = "mel" if stage_literal == "toc" else "critic"
            api_app_module._pause_for_hitl(job_id, final_state, stage=stage_literal, resume_from=resume_literal)
            return
        if bool(final_state.get("hitl_pending")):
            api_app_module._set_job(
                job_id,
                {
                    "status": "error",
                    "error": "HITL pending state returned without a valid checkpoint stage",
                    "state": final_state,
                    "hitl_enabled": True,
                },
            )
            return
        for key in api_app_module.RUNTIME_PIPELINE_STATE_KEYS:
            final_state.pop(key, None)
        final_state["hitl_pending"] = False
        api_app_module._attach_export_contract_gate(final_state)
        runtime_grounded_gate = api_app_module._evaluate_runtime_grounded_quality_gate_from_state(final_state)
        final_state["grounded_quality_gate"] = runtime_grounded_gate
        runtime_grounded_block_reason = api_app_module._runtime_grounded_quality_gate_block_reason(final_state)
        if runtime_grounded_block_reason:
            api_app_module._append_runtime_grounded_quality_gate_finding(final_state, runtime_grounded_gate)
            api_app_module._record_job_event(
                job_id,
                "runtime_grounded_quality_gate_blocked",
                mode=str(runtime_grounded_gate.get("mode") or "strict"),
                summary=str(runtime_grounded_gate.get("summary") or ""),
                reasons=list(runtime_grounded_gate.get("reasons") or []),
            )
            api_app_module._set_job(
                job_id,
                {
                    "status": "error",
                    "error": runtime_grounded_block_reason,
                    "state": final_state,
                    "hitl_enabled": True,
                },
            )
            return
        grounding_block_reason = api_app_module._grounding_gate_block_reason(final_state)
        if grounding_block_reason:
            api_app_module._set_job(
                job_id,
                {
                    "status": "error",
                    "error": grounding_block_reason,
                    "state": final_state,
                    "hitl_enabled": True,
                },
            )
            return
        mel_grounding_block_reason = api_app_module._mel_grounding_policy_block_reason(final_state)
        if mel_grounding_block_reason:
            api_app_module._set_job(
                job_id,
                {
                    "status": "error",
                    "error": mel_grounding_block_reason,
                    "state": final_state,
                    "hitl_enabled": True,
                },
            )
            return
        api_app_module._set_job(job_id, {"status": "done", "state": final_state, "hitl_enabled": True})
        return
    except Exception as exc:
        api_app_module._set_job(job_id, {"status": "error", "error": str(exc), "hitl_enabled": True, "state": state})


def _run_hitl_pipeline_by_job_id(job_id: str, start_at: HITLStartAt) -> None:
    job = api_app_module._get_job(job_id)
    if not isinstance(job, dict):
        return
    status = str(job.get("status") or "").strip().lower()
    if status in api_app_module.TERMINAL_JOB_STATUSES:
        return
    if status == "pending_hitl":
        return
    if status not in {"accepted", "running"}:
        return
    state = job.get("state")
    if not isinstance(state, dict):
        api_app_module._set_job(job_id, {"status": "error", "error": "Job state is missing or invalid", "hitl_enabled": True})
        return
    _run_hitl_pipeline(job_id, state, start_at)


def _resume_target_from_checkpoint(checkpoint: Dict[str, Any], default_resume_from: str | None) -> HITLStartAt:
    stage = str(checkpoint.get("stage") or "").strip().lower()
    status = _checkpoint_status_token(checkpoint)

    if status == HITLStatus.APPROVED.value:
        if stage == "toc":
            return "mel"
        if stage == "logframe":
            return "critic"

    if status == HITLStatus.REJECTED.value:
        if stage == "toc":
            return "architect"
        if stage == "logframe":
            return "mel"

    if status in {HITLStatus.APPROVED.value, HITLStatus.REJECTED.value} and default_resume_from in {
        "start",
        "architect",
        "mel",
        "critic",
    }:
        return default_resume_from  # type: ignore[return-value]

    raise ValueError("Checkpoint must be approved or rejected before resume")


def _clear_hitl_runtime_state(state: dict, *, clear_pending: bool) -> None:
    for key in api_app_module.RUNTIME_PIPELINE_STATE_KEYS:
        state.pop(key, None)
    if clear_pending:
        state["hitl_pending"] = False
