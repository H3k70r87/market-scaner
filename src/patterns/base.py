"""
Base class for all pattern detectors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class PatternResult:
    """Standardized result returned by every pattern detector."""
    found: bool
    type: str          # 'bullish' | 'bearish' | 'neutral'
    confidence: float  # 0-100
    details: dict = field(default_factory=dict)
    pattern_name: str = ""

    def to_dict(self) -> dict:
        return {
            "found": self.found,
            "type": self.type,
            "confidence": self.confidence,
            "details": self.details,
            "pattern_name": self.pattern_name,
        }


NOT_FOUND = PatternResult(found=False, type="neutral", confidence=0.0, details={})


class BasePattern(ABC):
    """
    Abstract base class for pattern detectors.

    Subclasses must implement:
        - name (property)
        - supported_timeframes (property)
        - detect(df) -> PatternResult
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique pattern identifier, e.g. 'double_top_bottom'."""

    @property
    @abstractmethod
    def supported_timeframes(self) -> list[str]:
        """List of timeframes this detector supports, e.g. ['4h', '1d']."""

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> PatternResult:
        """
        Run pattern detection on a normalized OHLCV DataFrame.

        Args:
            df: DataFrame with columns [open, high, low, close, volume]
                indexed by UTC datetime.

        Returns:
            PatternResult instance.
        """

    def supports_timeframe(self, timeframe: str) -> bool:
        return timeframe in self.supported_timeframes

    def _not_found(self) -> PatternResult:
        return PatternResult(
            found=False,
            type="neutral",
            confidence=0.0,
            details={},
            pattern_name=self.name,
        )

    def _result(
        self,
        signal_type: str,
        confidence: float,
        details: Optional[dict] = None,
    ) -> PatternResult:
        return PatternResult(
            found=True,
            type=signal_type,
            confidence=round(confidence, 1),
            details=details or {},
            pattern_name=self.name,
        )
