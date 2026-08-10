"""Risk-gated confirmation flow (single for MEDIUM, double for HIGH)."""
from __future__ import annotations

from core.io.base import IOChannel
from core.risk import CONFIRMATION_POLICY, RiskLevel
from utils.logger import get_logger
from utils.text import is_affirmative, is_negative

_FIRST_MEDIUM = "Medium-risk action: {action}. Confirm? (yes/no)"
_FIRST_HIGH = "HIGH-RISK action: {action}. Are you sure? (yes/no)"
_SECOND = "Please confirm once more to proceed with: {action}. (yes/no)"


class Confirmer:
    def __init__(self, channel: IOChannel, policy: dict[RiskLevel, int] | None = None) -> None:
        self._ch = channel
        self._policy = policy or CONFIRMATION_POLICY
        self.log = get_logger("jarvis.security.confirm")

    def confirm(self, action: str, level: RiskLevel) -> bool:
        needed = self._policy.get(level, 0)
        for step in range(needed):
            if step == 0:
                template = _FIRST_HIGH if needed == 2 else _FIRST_MEDIUM
            else:
                template = _SECOND
            reply = self._ch.ask(template.format(action=action))
            if is_negative(reply) or not is_affirmative(reply):
                self.log.info("'%s' cancelled at step %d/%d.", action, step + 1, needed)
                return False
        return True
