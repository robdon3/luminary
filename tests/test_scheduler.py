import unittest

from luminary.kernel.scheduler import (
    ALARM_EXEC_OVERFLOW,
    AI_PRIORITY_FLOOR,
    PriorityScheduler,
)


class TestScheduler(unittest.TestCase):
    def test_priority_order(self):
        sch = PriorityScheduler(max_depth=64)
        order = []

        def make(name):
            def work(job, ctx):
                order.append(name)

            return work

        sch.spawn("ai", priority=5, work=make("ai"))
        sch.spawn("ctrl", priority=0, work=make("ctrl"))
        sch.spawn("sense", priority=1, work=make("sense"))
        sch.run_until_idle(None)
        self.assertEqual(order, ["ctrl", "sense", "ai"])

    def test_overload_sheds_ai(self):
        sch = PriorityScheduler(max_depth=8)
        ran_critical = []

        def crit(job, ctx):
            ran_critical.append(job.name)

        def ai(job, ctx):
            pass

        for i in range(3):
            sch.spawn(f"c{i}", priority=0, work=crit, cancellable=False)
        for i in range(20):
            sch.spawn(f"a{i}", priority=AI_PRIORITY_FLOOR, work=ai, cancellable=True)

        self.assertIn(ALARM_EXEC_OVERFLOW, sch.alarms)
        self.assertGreater(sch.shed_count, 0)
        self.assertLessEqual(sch.pending(), sch.max_depth)
        sch.run_until_idle(None)
        self.assertEqual(len(ran_critical), 3)


if __name__ == "__main__":
    unittest.main()
