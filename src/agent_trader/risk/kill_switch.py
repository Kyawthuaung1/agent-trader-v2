from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from ..utils.errors import RiskViolation


class KillSwitch:
    """Persistent fail-safe kill switch backed by a small JSON file."""

    def __init__(self, path: str | Path = "data/processed/kill_switch.json") -> None:
        self.path = Path(path)
        self._memory_engaged = False
        self._memory_reason = ""

    @staticmethod
    def _environment_engaged() -> bool:
        return os.getenv("KILL_SWITCH", "").strip().lower() in {"1", "true"}

    def _file_state(self) -> tuple[bool, str]:
        try:
            with self.path.open("r", encoding="utf-8") as source:
                state = json.load(source)
        except FileNotFoundError:
            return False, ""
        except (OSError, json.JSONDecodeError, UnicodeError):
            return True, "kill switch state file is unreadable or corrupt"

        if not isinstance(state, dict):
            return True, "kill switch state file is corrupt"
        engaged = state.get("engaged")
        reason = state.get("reason")
        timestamp = state.get("time_utc")
        if not isinstance(engaged, bool) or not isinstance(reason, str) or not isinstance(timestamp, str):
            return True, "kill switch state file is corrupt"
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return True, "kill switch state file is corrupt"
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            return True, "kill switch state file is corrupt"
        return engaged, reason or ("unspecified reason" if engaged else "")

    def _status(self) -> tuple[bool, str]:
        if self._environment_engaged():
            return True, "KILL_SWITCH environment override is enabled"
        if self._memory_engaged:
            return True, self._memory_reason or "kill switch could not be persisted"
        return self._file_state()

    def _write_state(self, engaged: bool, reason: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "engaged": engaged,
            "reason": reason,
            "time_utc": datetime.now(timezone.utc).isoformat(),
        }
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.name}.", suffix=".tmp", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(payload, temporary, separators=(",", ":"))
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def engage(self, reason: str) -> None:
        message = str(reason).strip() or "unspecified reason"
        self._memory_engaged = True
        self._memory_reason = message
        try:
            self._write_state(True, message)
        except OSError as exc:
            raise RiskViolation("Kill switch is engaged but its state could not be persisted.") from exc
        self._memory_engaged = False
        self._memory_reason = ""

    def reset(self) -> None:
        try:
            self._write_state(False, "")
        except OSError as exc:
            self._memory_engaged = True
            self._memory_reason = "kill switch reset could not be persisted"
            raise RiskViolation("Kill switch remains engaged because reset could not be persisted.") from exc
        self._memory_engaged = False
        self._memory_reason = ""

    def is_engaged(self) -> bool:
        return self._status()[0]

    def check(self) -> None:
        engaged, reason = self._status()
        if engaged:
            raise RiskViolation(f"Kill switch engaged: {reason}")
