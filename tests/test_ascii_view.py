import unittest

from luminary.mission.ascii_view import VIEW_H, VIEW_W, render_viewport, side_by_side


class TestAsciiView(unittest.TestCase):
    def test_viewport_size(self):
        lines = render_viewport(
            altitude=800,
            max_alt=1400,
            rate=-20,
            fuel=500,
            max_fuel=1100,
            thrust=20,
            tick=5,
            alarm=False,
            phase="1 DESCENT",
            action_name="BRAKE",
            color=False,
        )
        # borders + hud
        self.assertGreaterEqual(len(lines), VIEW_H + 3)
        # each content line has borders
        self.assertTrue(any(line.startswith("╔") for line in lines))
        self.assertTrue(any("*" in line or "." in line or "^" in line for line in lines))

    def test_lander_moves_with_altitude(self):
        high = render_viewport(
            altitude=1400,
            max_alt=1400,
            rate=-10,
            fuel=100,
            max_fuel=100,
            thrust=0,
            tick=0,
            alarm=False,
            phase="A",
            action_name="HOLD",
            color=False,
        )
        low = render_viewport(
            altitude=20,
            max_alt=1400,
            rate=-5,
            fuel=100,
            max_fuel=100,
            thrust=0,
            tick=0,
            alarm=False,
            phase="A",
            action_name="HOLD",
            color=False,
        )
        # lander glyph ^ should appear; low altitude places it further down the buffer
        def first_lander_row(lines):
            for i, ln in enumerate(lines):
                if "/|\\" in ln or " ^ " in ln or "/_|_\\" in ln:
                    return i
            return -1

        self.assertNotEqual(first_lander_row(high), -1)
        self.assertGreaterEqual(first_lander_row(low), first_lander_row(high))

    def test_side_by_side(self):
        rows = side_by_side(["aa", "bb"], ["xxx", "yyy", "zzz"])
        self.assertEqual(len(rows), 3)
        self.assertIn("aa", rows[0])
        self.assertIn("xxx", rows[0])

    def test_display_budget(self):
        # spirit of the era: tiny fixed grid
        self.assertEqual(VIEW_W, 52)
        self.assertEqual(VIEW_H, 16)
        self.assertLessEqual(VIEW_W * VIEW_H, 1024)


if __name__ == "__main__":
    unittest.main()
