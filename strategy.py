"""
Pure Structure-Based Trading Strategy - Mark II
Focus on clear swing invalidation with tight entries.
- Identify swing highs/lows (real structure)
- Enter only on close invalidation + momentum
- Tight SL at swing (not arbitrary distance)
- Better quality signals with lower frequency
"""

import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from config import BotConfig
from data_handler import OHLCV

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    BULLISH = 1
    BEARISH = -1
    SIDEWAYS = 0


@dataclass
class SignalContext:
    pair: str
    direction: TrendDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: any
    risk_reward: float
    confirmation: str


class StrategyEngine:
    """Swing structure-based strategy - Mark II."""

    def __init__(self, config: BotConfig):
        self.config = config

    def analyze(self, pair: str, candles: List[OHLCV]) -> Optional[SignalContext]:
        """
        Balanced swing breakout strategy.
        - Moderate trend validation (6+ HH/HL or LH/LL in last 20)
        - Breakouts with momentum confirmation
        - Realistic risk/reward with tight stops
        """
        if len(candles) < 50:
            return None

        current = candles[-1]
        recent_20 = candles[-21:-1]

        # Trend check: count consecutive HH/HL vs LH/LL
        highs = [c.high for c in recent_20]
        lows = [c.low for c in recent_20]

        hh_count = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll_count = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])

        # More relaxed thresholds for better signal frequency
        bullish_trend = hh_count >= 6
        bearish_trend = ll_count >= 6

        # Trade the trend
        if not (bullish_trend or bearish_trend):
            return None

        upper_swing, lower_swing = self._identify_swings(candles)
        if not upper_swing or not lower_swing:
            return None

        # Breakout requirement
        breakout_thresh = 8 if "JPY" in pair else 12

        # Bullish
        if bullish_trend and current.close > upper_swing['high']:
            breakout_pips = (current.close - upper_swing['high']) / 0.0001
            if breakout_pips >= breakout_thresh:
                return self._create_bullish_signal(pair, current, upper_swing, lower_swing, candles)

        # Bearish
        if bearish_trend and current.close < lower_swing['low']:
            breakout_pips = (lower_swing['low'] - current.close) / 0.0001
            if breakout_pips >= breakout_thresh:
                return self._create_bearish_signal(pair, current, lower_swing, upper_swing, candles)

        return None

    def _identify_swings(self, candles: List[OHLCV]) -> Tuple[Optional[dict], Optional[dict]]:
        """
        Identify most recent pivot highs and lows (last 40 candles).
        Uses simple local extrema detection.
        """
        recent = candles[-40:]

        upper_swings = []
        lower_swings = []

        # Find pivot points
        for i in range(1, len(recent) - 1):
            # Pivot high
            if recent[i].high > recent[i-1].high and recent[i].high > recent[i+1].high:
                upper_swings.append({'idx': i, 'high': recent[i].high})

            # Pivot low
            if recent[i].low < recent[i-1].low and recent[i].low < recent[i+1].low:
                lower_swings.append({'idx': i, 'low': recent[i].low})

        # Return most recent swings only
        upper = upper_swings[-1] if upper_swings else None
        lower = lower_swings[-1] if lower_swings else None

        return upper, lower

    def _create_bullish_signal(self, pair: str, current: OHLCV, upper_swing: dict,
                               lower_swing: dict, all_candles: List[OHLCV]) -> Optional[SignalContext]:
        """Create LONG signal on upper swing breakout."""
        # SL: just below lower swing (clear invalidation level)
        sl = lower_swing['low'] - (50 * 0.0001)

        # Risk in pips
        risk_pips = (current.close - sl) / 0.0001

        # TP: 2:1 reward
        tp = current.close + (risk_pips * 2.0 * 0.0001)

        # RR check
        rr = (tp - current.close) / (current.close - sl)

        if rr < 1.8 or rr > 3.0 or risk_pips > 300:  # Cap max risk at 300 pips
            return None

        return SignalContext(
            pair=pair,
            direction=TrendDirection.BULLISH,
            entry_price=current.close,
            stop_loss=sl,
            take_profit=tp,
            timestamp=current.time,
            risk_reward=rr,
            confirmation=f"SWING_BREAK({risk_pips:.0f}p)"
        )

    def _create_bearish_signal(self, pair: str, current: OHLCV, lower_swing: dict,
                               upper_swing: dict, all_candles: List[OHLCV]) -> Optional[SignalContext]:
        """Create SHORT signal on lower swing breakout."""
        # SL: just above upper swing
        sl = upper_swing['high'] + (50 * 0.0001)

        # Risk in pips
        risk_pips = (sl - current.close) / 0.0001

        # TP: 2:1 reward
        tp = current.close - (risk_pips * 2.0 * 0.0001)

        # RR check
        rr = (current.close - tp) / (sl - current.close)

        if rr < 1.8 or rr > 3.0 or risk_pips > 300:
            return None

        return SignalContext(
            pair=pair,
            direction=TrendDirection.BEARISH,
            entry_price=current.close,
            stop_loss=sl,
            take_profit=tp,
            timestamp=current.time,
            risk_reward=rr,
            confirmation=f"SWING_BREAK({risk_pips:.0f}p)"
        )
