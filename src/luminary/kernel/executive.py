"""Kernel executive — boots VM context, owns scheduler + devices + AI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from luminary.vm.cpu import CPU
from luminary.vm.memory import ErasableMemory, RopeMemory
from luminary.kernel.scheduler import (
    ALARM_EXEC_OVERFLOW,
    AI_PRIORITY_FLOOR,
    Job,
    PriorityScheduler,
)
from luminary.kernel.memory_map import MemoryMap
from luminary.ai.bnn import BinaryNet, pack_weights_to_words


@dataclass
class Executive:
    """Top-level OS executive for a Luminary instance."""

    erasable: ErasableMemory = field(default_factory=ErasableMemory)
    rope: RopeMemory = field(default_factory=RopeMemory)
    mmap: MemoryMap = field(default_factory=MemoryMap)
    scheduler: PriorityScheduler = field(default_factory=PriorityScheduler)
    cpu: Optional[CPU] = None
    net: Optional[BinaryNet] = None
    devices: dict[str, Any] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    control_ticks: int = 0
    ai_inferences: int = 0
    ai_skipped: int = 0

    def boot(self, rope_image: list[int] | None = None) -> None:
        self.mmap.validate()
        if rope_image is not None:
            self.rope.load(rope_image)
        self.cpu = CPU(erasable=self.erasable, rope=self.rope)
        self.cpu.sys_handler = self._syscall
        self.log.append("LUMINARY EXECUTIVE BOOT")
        self.log.append(
            f"rope={self.rope.image_size()}/{self.rope.CAPACITY} "
            f"erasable={self.erasable.CAPACITY} words"
        )

    def attach_net(self, net: BinaryNet, rope_base: int = 0) -> int:
        """Serialize net weights into rope at rope_base; return words used."""
        words = pack_weights_to_words(net)
        # merge into existing rope image
        img = self.rope.as_data_list(self.rope.CAPACITY)
        end = rope_base + len(words)
        if end > self.rope.CAPACITY:
            raise MemoryError(f"net does not fit in rope at {rope_base}")
        for i, w in enumerate(words):
            img[rope_base + i] = w
        # preserve any prior non-zero beyond? we rewrite full image
        used = max(self.rope.image_size(), end)
        self.rope.load(img[: max(used, end)])
        self.net = net
        net.rope_base = rope_base
        net.rope_words = len(words)
        self.log.append(f"AI rope weights @ {rope_base} ({len(words)} words)")
        return len(words)

    def _syscall(self, n: int, cpu: CPU) -> int:
        # 0 = yield, 1 = get cycle, 2 = raise alarm 1202
        if n == 0:
            return 0
        if n == 1:
            return cpu.cycles & 0x7FFF
        if n == 2:
            self.scheduler.force_overload_alarm()
            return ALARM_EXEC_OVERFLOW
        return 0x7FFF

    def schedule_control(self, name: str = "control_loop") -> Job:
        def work(job: Job, ctx: Executive) -> None:
            ctx.control_ticks += 1
            # write tick counter into zero page
            ctx.erasable.write(0x0001, ctx.control_ticks & 0x7FFF)

        return self.scheduler.spawn(
            name, priority=0, work=work, work_units=1, cancellable=False
        )

    def schedule_sensor(self, name: str = "sensor_sample") -> Job:
        def work(job: Job, ctx: Executive) -> None:
            imu = ctx.devices.get("imu")
            if imu is not None:
                sample = imu.sample()
                base = ctx.mmap.device_buf_base
                for i, v in enumerate(sample[:8]):
                    ctx.erasable.write(base + i, int(v) & 0x7FFF)

        return self.scheduler.spawn(
            name, priority=1, work=work, work_units=1, cancellable=False
        )

    def schedule_ai(self, name: str = "ai_infer") -> Job:
        def work(job: Job, ctx: Executive) -> None:
            if ctx.net is None:
                ctx.ai_skipped += 1
                return
            # If we already have overflow alarm and queue is stressed, skip
            if (
                ALARM_EXEC_OVERFLOW in ctx.scheduler.alarms
                and ctx.scheduler.pending() > ctx.scheduler.max_depth // 2
            ):
                ctx.ai_skipped += 1
                return
            base = ctx.mmap.device_buf_base
            features = [ctx.erasable.read(base + i) for i in range(ctx.net.n_in)]
            # quantize to bits: high bit of each feature
            bits = [1 if (f & 0x100) else 0 for f in features]
            # pad/truncate
            bits = (bits + [0] * ctx.net.n_in)[: ctx.net.n_in]
            scores = ctx.net.forward(bits)
            scratch = ctx.mmap.ai_scratch_base
            for i, s in enumerate(scores[: ctx.mmap.ai_scratch_words]):
                ctx.erasable.write(scratch + i, int(s) & 0x7FFF)
            # decision class = argmax
            decision = max(range(len(scores)), key=lambda i: scores[i])
            ctx.erasable.write(scratch + 16, decision)
            ctx.ai_inferences += 1

        return self.scheduler.spawn(
            name,
            priority=AI_PRIORITY_FLOOR,
            work=work,
            work_units=2,
            cancellable=True,
        )

    def flood_ai_jobs(self, n: int) -> None:
        """Stress test: enqueue many AI jobs to force 1202 shed path."""
        for i in range(n):
            self.schedule_ai(name=f"ai_flood_{i}")

    def run(self, steps: int = 100) -> None:
        for _ in range(steps):
            self.schedule_control()
            self.schedule_sensor()
            # AI less often
            if self.control_ticks % 3 == 0:
                self.schedule_ai()
            self.scheduler.run_until_idle(self, max_jobs=64)

    def status(self) -> str:
        alarms = ",".join(str(a) for a in self.scheduler.alarms) or "none"
        return (
            f"ticks={self.control_ticks} ai_ok={self.ai_inferences} "
            f"ai_skip={self.ai_skipped} shed={self.scheduler.shed_count} "
            f"alarms={alarms} rope={self.rope.image_size()}/{self.rope.CAPACITY}"
        )
