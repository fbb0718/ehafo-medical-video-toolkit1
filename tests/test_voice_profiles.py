#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from run_question_project import select_voice, validate_voice_resources


class VoiceProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(
            (ROOT / "config" / "project.json").read_text(encoding="utf-8")
        )

    def test_yhn_profile_and_outro_match(self) -> None:
        selected = select_voice(self.config, "yhn")
        profile = validate_voice_resources(selected)
        self.assertEqual(profile["voiceKey"], "yhn")
        self.assertIn("/yhn/", profile["referenceAudio"])
        self.assertIn("yhn固定片尾.wav", selected["sharedOutro"]["audio"])

    def test_mcy_profile_and_outro_match(self) -> None:
        selected = select_voice(self.config, "mcy")
        profile = validate_voice_resources(selected)
        self.assertEqual(profile["voiceKey"], "mcy")
        self.assertIn("/mcy/", profile["referenceAudio"])
        self.assertIn("mcy固定片尾.wav", selected["sharedOutro"]["audio"])

    def test_unknown_voice_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "未知音色"):
            select_voice(self.config, "unknown")

    def test_cross_wired_outro_fails(self) -> None:
        config = copy.deepcopy(self.config)
        config["sharedOutros"]["mcy"]["voice"] = "yhn"
        with self.assertRaisesRegex(ValueError, "固定片尾配置不匹配"):
            select_voice(config, "mcy")

    def test_cross_wired_profile_fails(self) -> None:
        config = copy.deepcopy(self.config)
        config["voiceProfiles"]["mcy"] = config["voiceProfiles"]["yhn"]
        with self.assertRaisesRegex(ValueError, "voiceKey 不匹配"):
            validate_voice_resources(select_voice(config, "mcy"))


if __name__ == "__main__":
    unittest.main()
