"""
Aggressive position sizing for small accounts ($20).
Target: $2-5/day through higher risk-per-trade.

Risk Management:
- Account: $20
- Risk per trade: $2-3 (10-15% of account)
- Target profit: $2-5/day
- Strategy: 2:1 RR = Risk $2 → Win $4
"""

ACCOUNT_SIZE = 20.0  # Starting capital
DAILY_TARGET = 3.50  # Target $2-5 per day (middle: $3.50)

# Position Sizing
RISK_PER_TRADE = 2.50  # Risk $2.50 per trade (12.5% of $20)
RISK_PERCENT = RISK_PER_TRADE / ACCOUNT_SIZE  # 12.5%

# If 46.2% win rate with 2:1 RR:
# Win $5 × 46.2% = +$2.31
# Lose $2.50 × 53.8% = -$1.35
# Expected value per trade = +$0.96 (not great, but possible)

# Better approach: Only trade high-probability setups
PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY']
MAX_DAILY_TRADES = 3  # Max 3 trades per day to limit variance
TARGET_WIN_RATE = 50.0  # Aim for 50%+ to hit daily target

# Risk/Reward
MIN_RR = 2.0  # Require 2:1 minimum
MAX_RR = 3.0  # Cap at 3:1

# Entry thresholds (stricter for better quality)
BREAKOUT_PIPS = {
    'EURUSD': 15,   # Tighter entries
    'GBPUSD': 15,
    'USDJPY': 10,
}

def calculate_position_size(account_balance: float, risk_amount: float, entry_price: float,
                            stop_loss: float, pip_value: float = 0.0001) -> float:
    """
    Calculate position size based on risk amount and S/L distance.

    Args:
        account_balance: Current account balance
        risk_amount: Amount willing to risk (e.g., $2.50)
        entry_price: Entry price
        stop_loss: Stop loss price
        pip_value: Pip value for the pair (0.0001 for most forex)

    Returns:
        Position size in micro-lots (0.01 lots)
    """
    risk_pips = abs(entry_price - stop_loss) / pip_value

    if risk_pips <= 0:
        return 0

    # Micro-lot: 1 pip = $0.10
    # Mini-lot: 1 pip = $1.00
    # Standard lot: 1 pip = $10.00

    pips_cost_per_micro = 0.10  # $0.10 per pip per micro-lot
    micro_lots_needed = risk_amount / (risk_pips * pips_cost_per_micro)

    # Round to nearest 0.01 (1 micro-lot)
    return round(micro_lots_needed, 2)


# Daily tracking
class DailySession:
    def __init__(self, session_date: str):
        self.date = session_date
        self.trades = []
        self.starting_balance = ACCOUNT_SIZE
        self.current_balance = ACCOUNT_SIZE
        self.daily_profit = 0.0
        self.trades_taken = 0
        self.wins = 0
        self.losses = 0

    def add_trade(self, pair: str, direction: str, entry: float, sl: float,
                  tp: float, exit_price: float, profit: float):
        """Record a trade."""
        self.trades.append({
            'pair': pair,
            'direction': direction,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'exit': exit_price,
            'profit': profit,
            'status': 'WIN' if profit > 0 else 'LOSS'
        })

        self.current_balance += profit
        self.daily_profit += profit
        self.trades_taken += 1

        if profit > 0:
            self.wins += 1
        else:
            self.losses += 1

    def print_summary(self):
        """Print daily summary."""
        wr = (self.wins / self.trades_taken * 100) if self.trades_taken > 0 else 0
        print(f"\n{'='*60}")
        print(f"Daily Session: {self.date}")
        print(f"{'='*60}")
        print(f"Starting Balance: ${self.starting_balance:.2f}")
        print(f"Current Balance:  ${self.current_balance:.2f}")
        print(f"Daily P&L:        ${self.daily_profit:+.2f}")
        print(f"\nTrades: {self.trades_taken} ({self.wins}W/{self.losses}L, {wr:.1f}% WR)")
        print(f"Daily Target Hit: {self.daily_profit >= DAILY_TARGET}")
        print(f"{'='*60}\n")

if __name__ == "__main__":
    # Test position sizing
    print("Position Sizing Examples ($2.50 risk per trade):\n")

    test_cases = [
        ("EURUSD", 1.1600, 1.1550, 0.0001),  # 50 pips risk
        ("GBPUSD", 1.3400, 1.3340, 0.0001),  # 60 pips risk
        ("USDJPY", 151.50, 151.20, 0.01),    # 30 pips risk (JPY)
    ]

    for pair, entry, sl, pip_val in test_cases:
        lots = calculate_position_size(ACCOUNT_SIZE, RISK_PER_TRADE, entry, sl, pip_val)
        risk_pips = abs(entry - sl) / pip_val
        # Micro-lot: $0.10 per pip. So risk = micro_lots × pips × $0.10
        potential_loss = lots * risk_pips * 0.10
        print(f"{pair}: {lots:.3f} micro-lots | Risk: ${potential_loss:.2f} | Pips at risk: {risk_pips:.0f}")
