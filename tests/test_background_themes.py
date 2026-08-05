from __future__ import annotations

import sys
import unittest
import inspect
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import render_fast_question_video as fast_renderer
from build_question_compositions import theme_css


class BackgroundThemeTest(unittest.TestCase):
    def tearDown(self) -> None:
        fast_renderer.set_theme("white")

    def test_white_theme_keeps_existing_defaults(self) -> None:
        self.assertEqual(theme_css("white"), "")
        fast_renderer.set_theme("white")
        self.assertEqual(fast_renderer.BG, "#F4F6F8")
        self.assertEqual(fast_renderer.INK, "#15202B")

    def test_green_theme_matches_approved_preview(self) -> None:
        css = theme_css("green")
        self.assertIn("background:#003A46", css)
        self.assertIn("color:#F7FAFA", css)
        self.assertIn("right:24px;top:auto;bottom:278px", css)
        self.assertIn("#B42318", Path(ROOT / "DESIGN.md").read_text(encoding="utf-8"))

        fast_renderer.set_theme("green")
        self.assertEqual(fast_renderer.BG, "#003A46")
        self.assertEqual(fast_renderer.PAPER, "#00343D")
        self.assertEqual(fast_renderer.INK, "#F7FAFA")
        self.assertEqual(fast_renderer.BLUE, "#F4D04F")
        self.assertEqual(fast_renderer.HIGHLIGHT, "#243136")
        self.assertIsNone(
            inspect.signature(fast_renderer.draw_marked_text).parameters["fill"].default
        )

    def test_unknown_theme_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            theme_css("purple")
        with self.assertRaises(ValueError):
            fast_renderer.set_theme("purple")


if __name__ == "__main__":
    unittest.main()
