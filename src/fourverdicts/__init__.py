"""fourverdicts: four verdicts for governing agentic AI. A reference edition by Advaita AI."""

from fourverdicts.engine import GovernanceEngine, GovernanceOutcome
from fourverdicts.policy import BasePolicy, EnforcementMode, FailMode
from fourverdicts.types import (
    ExecutionPhase,
    GovernanceAction,
    GovernanceContext,
    PolicyResult,
    STRICTNESS,
)

__all__ = [
    "GovernanceEngine",
    "GovernanceOutcome",
    "BasePolicy",
    "EnforcementMode",
    "ExecutionPhase",
    "FailMode",
    "GovernanceAction",
    "GovernanceContext",
    "PolicyResult",
    "STRICTNESS",
]
__version__ = "0.1.0"
