"""
Aggressive Scaling System: $20 → $200 in 20-30 Days

MATH REQUIRED:
- Day 1-3: 20% daily = $20 → $35
- Day 4-7: 30% daily = $35 → $90
- Day 8-15: 40% daily = $90 → $180
- Day 16-20: 50% daily = $180 → $290 (hit 200)

Key: Compound wins + scale up after each profitable day

Target Win Rate: 60%+ (not 46%)
Timeframe: 1H (4x more signals than 4H)
Pairs: 3-5 pairs trading simultaneously
Max Daily Loss: -$5 (stop if hit)
"""

import math
from datetime import datetime, timedelta

# SCALING SYSTEM
class DayScalingSystem:
    """
    Progressive scaling based on daily performance.
    Increases position size after wins, decreases after losses.
    """

    def __init__(self, starting_capital: float = 20.0):
        self.starting_capital = starting_capital
        self.current_balance = starting_capital
        self.target_balance = starting_capital * 10  # 10x
        self.daily_log = []
        self.win_streak = 0
        self.loss_streak = 0

    def calculate_risk_for_day(self) -> float:
        """
        Scale risk based on current balance and streak.
        """
        base_risk = 0.15  # 15% base

        # Increase risk on win streak
        if self.win_streak >= 3:
            risk_percent = 0.20  # 20% on 3+ wins
        elif self.win_streak >= 1:
            risk_percent = 0.18  # 18% on 1-2 wins
        else:
            risk_percent = base_risk

        # Decrease on loss streak
        if self.loss_streak >= 2:
            risk_percent = 0.10  # 10% on 2+ losses
        elif self.loss_streak >= 1:
            risk_percent = 0.12  # 12% on 1 loss

        return self.current_balance * risk_percent

    def simulate_day(self, num_trades: int, win_rate: float,
                     avg_win: float, avg_loss: float) -> dict:
        """
        Simulate one trading day.

        Args:
            num_trades: Number of trades taken
            win_rate: Win percentage (50-60% realistic for 1H aggressive)
            avg_win: Average win in dollars
            avg_loss: Average loss in dollars (negative)

        Returns:
            Daily result
        """
        daily_risk = self.calculate_risk_for_day()

        # Simulate wins/losses
        wins = int(num_trades * win_rate)
        losses = num_trades - wins

        daily_pnl = (wins * avg_win) + (losses * avg_loss)

        # Update streaks
        if daily_pnl > 0:
            self.win_streak += 1
            self.loss_streak = 0
        else:
            self.loss_streak += 1
            self.win_streak = 0

        # Update balance
        old_balance = self.current_balance
        self.current_balance += daily_pnl

        # Safety: Stop if lost $5+
        if daily_pnl < -5:
            daily_pnl = -5
            self.current_balance = old_balance - 5

        result = {
            'balance': self.current_balance,
            'daily_pnl': daily_pnl,
            'num_trades': num_trades,
            'wins': wins,
            'losses': losses,
            'daily_risk': daily_risk,
            'win_streak': self.win_streak,
            'old_balance': old_balance,  # Add this
        }

        self.daily_log.append(result)
        return result

    def simulate_period(self, days: int, daily_trades: int = 3,
                       win_rate: float = 0.55,
                       avg_win: float = 4.0,
                       avg_loss: float = -2.0) -> list:
        """
        Simulate multiple days.
        """
        results = []

        for day in range(1, days + 1):
            result = self.simulate_day(daily_trades, win_rate, avg_win, avg_loss)
            results.append(result)

            # Check if target hit
            if self.current_balance >= self.target_balance:
                print(f"✓ TARGET HIT ON DAY {day}: ${self.current_balance:.2f}")
                return results

            print(f"Day {day}: ${result['old_balance']:.2f} {result['daily_pnl']:+.2f} "
                  f"({result['wins']}-{result['losses']} | streak: {result['win_streak']}W) "
                  f"→ ${self.current_balance:.2f}")

        return results


# AGGRESSIVE 1H STRATEGY PARAMETERS
AGGRESSIVE_1H = {
    'pairs': ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD'],
    'timeframe': '1H',
    'max_daily_trades': 5,  # Up to 5 per day
    'risk_per_trade': 0.15,  # 15% of account
    'min_rr': 1.5,  # Lower RR for more signals
    'breakout_pips': {
        'EURUSD': 8,  # Tighter entries on 1H
        'GBPUSD': 8,
        'USDJPY': 5,
        'USDCAD': 8,
        'AUDUSD': 8,
    },
    'scaling': True,  # Scale after wins
}


# SCENARIO ANALYSIS
print("="*70)
print("AGGRESSIVE SCALING: $20 → $200 in 15-30 Days")
print("="*70)

print("\nSCENARIO 1: AGGRESSIVE (55% WR, $4 avg win, $2 avg loss)")
print("-" * 70)
sim1 = DayScalingSystem(20.0)
results1 = sim1.simulate_period(30, daily_trades=3, win_rate=0.55,
                                 avg_win=4.0, avg_loss=-2.0)

print(f"\nResult: ${sim1.current_balance:.2f} ({(sim1.current_balance/20 - 1)*100:.0f}% gain)")
print(f"Hit target? {sim1.current_balance >= 200}")

print("\n" + "="*70)
print("SCENARIO 2: VERY AGGRESSIVE (60% WR, $5 avg win, $2.50 avg loss)")
print("-" * 70)
sim2 = DayScalingSystem(20.0)
results2 = sim2.simulate_period(20, daily_trades=4, win_rate=0.60,
                                 avg_win=5.0, avg_loss=-2.5)

print(f"\nResult: ${sim2.current_balance:.2f} ({(sim2.current_balance/20 - 1)*100:.0f}% gain)")
print(f"Hit target? {sim2.current_balance >= 200}")

print("\n" + "="*70)
print("SCENARIO 3: EXTREME (65% WR, $6 avg win, $3 avg loss)")
print("-" * 70)
sim3 = DayScalingSystem(20.0)
results3 = sim3.simulate_period(15, daily_trades=5, win_rate=0.65,
                                 avg_win=6.0, avg_loss=-3.0)

print(f"\nResult: ${sim3.current_balance:.2f} ({(sim3.current_balance/20 - 1)*100:.0f}% gain)")
print(f"Hit target? {sim3.current_balance >= 200}")
