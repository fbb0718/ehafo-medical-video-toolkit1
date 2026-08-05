from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from render_fast_question_video import transition_for_state


class FastTransitionTest(unittest.TestCase):
    def test_only_scene_changes_slide(self) -> None:
        self.assertEqual(transition_for_state(7, 0), ("slideleft", 0.30))
        self.assertEqual(transition_for_state(8, 0), ("fade", 0.16))
        self.assertEqual(transition_for_state(9, 0), ("fade", 0.16))
        self.assertEqual(transition_for_state(10, 0), ("slideleft", 0.30))

    def test_focus_reveals_do_not_move_the_page(self) -> None:
        self.assertEqual(transition_for_state(8, 1), ("fade", 0.20))

    def test_outro_uses_a_gentle_fade(self) -> None:
        self.assertEqual(transition_for_state(13, 0), ("fade", 0.52))


if __name__ == "__main__":
    unittest.main()
