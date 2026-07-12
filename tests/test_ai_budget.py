import unittest

from luminary import ROM_WORDS
from luminary.ai.bnn import BinaryNet, demo_descent_net, pack_weights_to_words
from luminary.kernel.executive import Executive
from luminary.kernel.memory_map import MemoryMap


class TestAIBudget(unittest.TestCase):
    def test_demo_net_fits_rope(self):
        net = demo_descent_net()
        words = pack_weights_to_words(net)
        self.assertEqual(len(words), net.estimate_rope_words())
        self.assertLess(len(words), 100)
        self.assertLess(len(words), ROM_WORDS)

    def test_forward_deterministic(self):
        net = BinaryNet.random(8, 16, 4, seed=1969)
        x = [1, 0, 1, 1, 0, 0, 1, 0]
        a = net.forward(x)
        b = net.forward(x)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 4)

    def test_executive_ai_and_map(self):
        mmap = MemoryMap()
        mmap.validate()
        self.assertEqual(mmap.total_reserved(), 2048)

        exe = Executive()
        exe.boot()
        net = demo_descent_net()
        n = exe.attach_net(net, rope_base=0)
        self.assertGreater(n, 0)
        self.assertLessEqual(exe.rope.image_size(), ROM_WORDS)

        from luminary.devices.imu import SyntheticIMU

        exe.devices["imu"] = SyntheticIMU()
        exe.schedule_sensor()
        exe.schedule_ai()
        exe.scheduler.run_until_idle(exe)
        self.assertGreaterEqual(exe.ai_inferences, 1)


if __name__ == "__main__":
    unittest.main()
