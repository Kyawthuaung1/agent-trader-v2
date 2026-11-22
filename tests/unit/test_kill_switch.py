import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from agent_trader.risk.kill_switch import KillSwitch
from agent_trader.utils.errors import RiskViolation


class TestKillSwitch(unittest.TestCase):
    def test_persist_engage_check_and_reset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "switch.json"
            switch = KillSwitch(path)
            self.assertFalse(switch.is_engaged())
            switch.engage("manual test")
            self.assertTrue(switch.is_engaged())
            state = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(state["engaged"])
            self.assertEqual(state["reason"], "manual test")
            timestamp = datetime.fromisoformat(state["time_utc"])
            self.assertIsNotNone(timestamp.tzinfo)
            with self.assertRaises(RiskViolation):
                KillSwitch(path).check()

            switch.reset()
            self.assertFalse(KillSwitch(path).is_engaged())
            switch.check()

    def test_environment_override_engages_switch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            switch = KillSwitch(Path(directory) / "switch.json")
            with patch.dict(os.environ, {"KILL_SWITCH": " TRUE "}):
                self.assertTrue(switch.is_engaged())
                with self.assertRaises(RiskViolation):
                    switch.check()
            with patch.dict(os.environ, {"KILL_SWITCH": "1"}):
                self.assertTrue(switch.is_engaged())

    def test_corrupt_or_unreadable_json_is_fail_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "switch.json"
            path.write_text("{broken", encoding="utf-8")
            switch = KillSwitch(path)
            self.assertTrue(switch.is_engaged())
            with self.assertRaises(RiskViolation):
                switch.check()

            path.write_text(json.dumps({"engaged": True}), encoding="utf-8")
            self.assertTrue(switch.is_engaged())


if __name__ == "__main__":
    unittest.main()
