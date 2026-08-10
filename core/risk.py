"""Risk levels and the confirmation policy that maps to them."""
from __future__ import annotations

from enum import Enum


class RiskLevel(Enum):
    SAFE = "safe"
    MEDIUM = "medium"
    HIGH = "high"


# Number of user confirmations required before executing an action.
CONFIRMATION_POLICY: dict[RiskLevel, int] = {
    RiskLevel.SAFE: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
}
