from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


TaskCallable = Callable[..., None]


@dataclass
class JobRunnerTask:
    fn: TaskCallable
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class InMemoryJobRunner:
    def __init__(self, worker_count: int = 2, queue_maxsize: int = 200) -> None:
        self.worker_count = max(1, int(worker_count))
        self.queue_maxsize = max(1, int(queue_maxsize))
        self._queue: queue.Queue[Optional[JobRunnerTask]] = queue.Queue(maxsize=self.queue_maxsize)
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._started = False
        self._submitted = 0
        self._completed = 0
        self._failed = 0

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._threads = []
            for idx in range(self.worker_count):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"grantflow-job-runner-{idx + 1}",
                    daemon=True,
                )
                worker.start()
                self._threads.append(worker)

    def stop(self, timeout_seconds: float = 2.0) -> None:
        with self._lock:
            if not self._started:
                return
            threads = list(self._threads)
            self._started = False
        for _ in threads:
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                # Worker threads will eventually drain real tasks and then consume sentinels.
                break
        for worker in threads:
            worker.join(timeout=max(0.0, float(timeout_seconds)))
        with self._lock:
            self._threads = []
            # Reset queue to drop stale sentinels/tasks between restarts.
            self._queue = queue.Queue(maxsize=self.queue_maxsize)

    def submit(self, fn: TaskCallable, *args: Any, **kwargs: Any) -> bool:
        if not callable(fn):
            raise TypeError("Job runner task must be callable")
        self.start()
        task = JobRunnerTask(fn=fn, args=tuple(args), kwargs=dict(kwargs))
        try:
            self._queue.put_nowait(task)
        except queue.Full:
            return False
        with self._lock:
            self._submitted += 1
        return True

    def is_running(self) -> bool:
        with self._lock:
            return self._started

    def diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            submitted = int(self._submitted)
            completed = int(self._completed)
            failed = int(self._failed)
            running = bool(self._started)
            active_workers = sum(1 for t in self._threads if t.is_alive())
        return {
            "running": running,
            "worker_count": self.worker_count,
            "active_workers": active_workers,
            "queue_maxsize": self.queue_maxsize,
            "queue_size": self._queue.qsize(),
            "submitted_count": submitted,
            "completed_count": completed,
            "failed_count": failed,
        }

    def _worker_loop(self) -> None:
        while True:
            task = self._queue.get()
            if task is None:
                self._queue.task_done()
                break
            try:
                task.fn(*task.args, **task.kwargs)
            except Exception:
                with self._lock:
                    self._failed += 1
            else:
                with self._lock:
                    self._completed += 1
            finally:
                self._queue.task_done()
