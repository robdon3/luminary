"""Priority preemptive job queue with 1202-class executive overflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import itertools


# Program alarm mnemonic (nod to Apollo 1201/1202)
ALARM_EXEC_OVERFLOW = 1202

# Default: priorities 0–2 critical, 3–4 normal, 5–7 AI/telemetry (shed first)
AI_PRIORITY_FLOOR = 5
MAX_QUEUE_DEPTH = 32  # fits spirit of tiny erasable TCB space
DEFAULT_WORK_SLICE = 50  # cycles of "work" credit per job run


WorkFn = Callable[["Job", Any], None]


@dataclass(order=True)
class Job:
    priority: int
    job_id: int = field(compare=True)
    name: str = field(compare=False, default="")
    work: Optional[WorkFn] = field(compare=False, default=None)
    deadline_cycle: Optional[int] = field(compare=False, default=None)
    cancellable: bool = field(compare=False, default=True)
    # remaining abstract work units (not full ISA cycles unless linked)
    work_units: int = field(compare=False, default=1)
    meta: dict = field(compare=False, default_factory=dict)

    def is_ai(self) -> bool:
        return self.priority >= AI_PRIORITY_FLOOR


class PriorityScheduler:
    """
    Multi-level priority scheduler.

    Lower priority number = more urgent (0 = highest).
    On overload: cancel cancellable jobs with priority >= AI_PRIORITY_FLOOR,
    then raise ALARM_EXEC_OVERFLOW.
    """

    def __init__(
        self,
        max_depth: int = MAX_QUEUE_DEPTH,
        ai_floor: int = AI_PRIORITY_FLOOR,
    ) -> None:
        self.max_depth = max_depth
        self.ai_floor = ai_floor
        self._seq = itertools.count(1)
        self._ready: list[Job] = []
        self.alarms: list[int] = []
        self.shed_count = 0
        self.completed = 0
        self.current_cycle = 0

    def _sort(self) -> None:
        # priority asc, then job_id asc (FIFO within level)
        self._ready.sort(key=lambda j: (j.priority, j.job_id))

    def pending(self) -> int:
        return len(self._ready)

    def spawn(
        self,
        name: str,
        priority: int,
        work: WorkFn,
        *,
        work_units: int = 1,
        deadline_cycle: Optional[int] = None,
        cancellable: bool = True,
        meta: Optional[dict] = None,
    ) -> Job:
        job = Job(
            priority=priority,
            job_id=next(self._seq),
            name=name,
            work=work,
            deadline_cycle=deadline_cycle,
            cancellable=cancellable,
            work_units=work_units,
            meta=meta or {},
        )
        self._ready.append(job)
        self._sort()
        self._check_overload()
        return job

    def _check_overload(self) -> None:
        if len(self._ready) <= self.max_depth:
            return
        # Shed AI / low-priority cancellable jobs first
        victims = [
            j
            for j in self._ready
            if j.cancellable and j.priority >= self.ai_floor
        ]
        # shed lowest urgency first (highest priority number)
        victims.sort(key=lambda j: (-j.priority, -j.job_id))
        while len(self._ready) > self.max_depth and victims:
            v = victims.pop(0)
            if v in self._ready:
                self._ready.remove(v)
                self.shed_count += 1
        if len(self._ready) > self.max_depth:
            # still overloaded — shed any cancellable
            cancellable = [j for j in self._ready if j.cancellable]
            cancellable.sort(key=lambda j: (-j.priority, -j.job_id))
            while len(self._ready) > self.max_depth and cancellable:
                v = cancellable.pop(0)
                if v in self._ready:
                    self._ready.remove(v)
                    self.shed_count += 1
        if ALARM_EXEC_OVERFLOW not in self.alarms:
            self.alarms.append(ALARM_EXEC_OVERFLOW)

    def pop_next(self) -> Optional[Job]:
        if not self._ready:
            return None
        # already sorted
        return self._ready.pop(0)

    def run_until_idle(
        self,
        ctx: Any,
        *,
        max_jobs: int = 10_000,
        cycle_step: int = DEFAULT_WORK_SLICE,
    ) -> int:
        """Execute ready jobs in priority order. Returns jobs completed."""
        ran = 0
        while self._ready and ran < max_jobs:
            job = self.pop_next()
            if job is None:
                break
            if job.deadline_cycle is not None and self.current_cycle > job.deadline_cycle:
                # missed deadline — count as shed
                self.shed_count += 1
                if job.is_ai():
                    ran += 1
                    continue
                # critical missed deadline still runs once (degraded)
            if job.work:
                job.work(job, ctx)
            self.current_cycle += cycle_step * max(1, job.work_units)
            self.completed += 1
            ran += 1
        return ran

    def force_overload_alarm(self) -> None:
        if ALARM_EXEC_OVERFLOW not in self.alarms:
            self.alarms.append(ALARM_EXEC_OVERFLOW)
