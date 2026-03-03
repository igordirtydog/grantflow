import threading
import time

from grantflow.core.job_runner import InMemoryJobRunner


def _wait_until(predicate, timeout_s: float = 1.5) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_inmemory_job_runner_executes_tasks():
    runner = InMemoryJobRunner(worker_count=1, queue_maxsize=8)
    observed: list[int] = []

    def _task(value: int) -> None:
        observed.append(value)

    assert runner.submit(_task, 1) is True
    assert _wait_until(lambda: observed == [1])
    diag = runner.diagnostics()
    assert diag["completed_count"] >= 1
    assert diag["failed_count"] == 0
    runner.stop()


def test_inmemory_job_runner_counts_failures_and_keeps_running():
    runner = InMemoryJobRunner(worker_count=1, queue_maxsize=8)
    observed = {"ok": 0}

    def _bad_task() -> None:
        raise RuntimeError("boom")

    def _good_task() -> None:
        observed["ok"] += 1

    assert runner.submit(_bad_task) is True
    assert runner.submit(_good_task) is True
    assert _wait_until(lambda: observed["ok"] == 1)
    diag = runner.diagnostics()
    assert diag["failed_count"] >= 1
    assert diag["completed_count"] >= 1
    runner.stop()


def test_inmemory_job_runner_rejects_submit_when_queue_is_full():
    runner = InMemoryJobRunner(worker_count=1, queue_maxsize=1)
    blocker = threading.Event()
    started = threading.Event()

    def _blocking_task() -> None:
        started.set()
        blocker.wait(timeout=0.5)

    assert runner.submit(_blocking_task) is True
    assert started.wait(timeout=0.5)
    assert runner.submit(_blocking_task) is True
    assert runner.submit(_blocking_task) is False
    blocker.set()
    assert _wait_until(lambda: runner.diagnostics()["completed_count"] >= 2)
    runner.stop()
