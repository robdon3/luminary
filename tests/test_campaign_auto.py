import unittest

from luminary.mission.campaign import Campaign


class TestCampaignAuto(unittest.TestCase):
    def test_auto_reaches_moon_or_fails_cleanly(self):
        """Autopilot should complete without hanging; prefer success."""
        c = Campaign(delay=0.0, color=False, auto=True)
        # run with capped ticks via monkeypatch-style loop
        c.boot_computer()
        while not c.dead and not c.won and c.phase != "TOUCHDOWN" and c.tick < 800:
            c._auto_pilot()
            c.computer_tick(ai=True)
            c.step_physics()
            c.tick += 1
        self.assertTrue(
            c.won or c.dead or c.phase == "TOUCHDOWN",
            f"stuck in phase={c.phase} tick={c.tick}",
        )
        # autopilot tuned for success
        self.assertTrue(
            c.won or (c.phase == "TOUCHDOWN" and not c.crashed),
            f"auto failed: {c.message} phase={c.phase} alt={c.alt} fuel={c.fuel}",
        )


if __name__ == "__main__":
    unittest.main()
