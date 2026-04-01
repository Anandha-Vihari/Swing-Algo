// ADAPTIVE TREND FOLLOWING STRATEGY - MT5 EXPERT ADVISOR
// Ready to migrate to your PC and backtest in MT5 Strategy Tester
// Compile and run directly in MetaTrader 5

#property copyright "Adaptive Trading System"
#property version "1.00"
#property strict
#property description "Adaptive trend-following with multi-condition entry"

// ===== INPUTS =====
input int TREND_STRENGTH = 6;           // Consecutive HH/HL or LL/LH required
input int BREAKOUT_PIPS = 12;           // Minimum breakout distance
input int SL_PIPS = 50;                 // Stop loss distance
input double RR_RATIO = 2.0;            // Risk/Reward ratio
input int RISK_PERCENT = 2;             // Risk % per trade
input bool USE_ADAPTIVE = true;         // Enable adaptive parameters
input int VOLUME_THRESHOLD = 80;        // Volume threshold % of average

// ===== GLOBAL VARIABLES =====
int total_trades = 0;
int winning_trades = 0;
int losing_trades = 0;
double total_pips = 0;

// Adaptive parameters
int adaptive_trend_strength = TREND_STRENGTH;
int adaptive_sl_pips = SL_PIPS;
int adaptation_count = 0;

// Recent performance tracking
struct Trade {
    double pips;
    int result;  // 0=loss, 1=win
};

Trade recent_trades[20];
int recent_trades_count = 0;

// ===== INITIALIZATION =====
int OnInit() {
    Print("=== ADAPTIVE STRATEGY INITIALIZED ===");
    Print("Trend Strength: ", adaptive_trend_strength);
    Print("SL Pips: ", adaptive_sl_pips);
    Print("RR Ratio: ", RR_RATIO);
    return INIT_SUCCEEDED;
}

// ===== MAIN TICK FUNCTION =====
void OnTick() {
    // Only on 4H bar close
    static datetime last_bar_time = 0;

    if (Time[0] == last_bar_time) return;
    last_bar_time = Time[0];

    // Check all open orders first
    CheckOpenPositions();

    // Adapt parameters periodically
    if (USE_ADAPTIVE && Bars % 100 == 0) {
        AdaptParameters();
    }

    // Look for new signals
    if (CountOpenPositions(Symbol()) == 0) {
        CheckForSignal();
    }
}

// ===== SIGNAL GENERATION =====
void CheckForSignal() {
    // ===== CONDITION 1: Trend Detection =====
    int trend = DetectTrend();
    if (trend == 0) return;  // No trend

    // ===== CONDITION 2: Support/Resistance =====
    double res, sup;
    FindSupportResistance(res, sup);
    if (res <= 0 || sup <= 0) return;

    // ===== CONDITION 3: Volume Confirmation =====
    bool volume_ok = CheckVolume(VOLUME_THRESHOLD);
    if (!volume_ok) return;

    // ===== CONDITION 4: Candle Quality =====
    double body_size = MathAbs(Close[0] - Open[0]) / Close[0];
    if (body_size < 0.0003) return;  // Too small body

    // ===== ENTRY LOGIC =====
    if (trend == 1) {  // UPTREND
        if (Close[0] > sup) {
            double entry = Close[0];
            double sl = sup - (adaptive_sl_pips * Point * 10);  // Convert pips to price
            double risk_pips = (entry - sl) / Point / 10;

            if (risk_pips > 15 && risk_pips < 200) {
                double tp = entry + (risk_pips * RR_RATIO * Point * 10);

                // Calculate lot size based on risk
                double risk_amount = AccountBalance() * RISK_PERCENT / 100;
                double lot = CalculateLotSize(risk_pips, risk_amount);

                // BUY ORDER
                OpenOrder(SIGNAL_UP, entry, sl, tp, lot, "TREND_UP");
            }
        }
    }
    else if (trend == -1) {  // DOWNTREND
        if (Close[0] < res) {
            double entry = Close[0];
            double sl = res + (adaptive_sl_pips * Point * 10);
            double risk_pips = (sl - entry) / Point / 10;

            if (risk_pips > 15 && risk_pips < 200) {
                double tp = entry - (risk_pips * RR_RATIO * Point * 10);

                double risk_amount = AccountBalance() * RISK_PERCENT / 100;
                double lot = CalculateLotSize(risk_pips, risk_amount);

                // SELL ORDER
                OpenOrder(SIGNAL_DOWN, entry, sl, tp, lot, "TREND_DOWN");
            }
        }
    }
}

// ===== TREND DETECTION =====
int DetectTrend() {
    // Check last 50 candles
    int hh = 0, ll = 0;

    // Count consecutive HH (Higher Highs)
    int current_hh = 0, max_hh = 0;
    for (int i = 1; i < 50; i++) {
        if (High[i] > High[i+1]) {
            current_hh++;
            if (current_hh > max_hh) max_hh = current_hh;
        } else {
            current_hh = 0;
        }
    }

    // Count consecutive LL (Lower Lows)
    int current_ll = 0, max_ll = 0;
    for (int i = 1; i < 50; i++) {
        if (Low[i] < Low[i+1]) {
            current_ll++;
            if (current_ll > max_ll) max_ll = current_ll;
        } else {
            current_ll = 0;
        }
    }

    if (max_hh >= adaptive_trend_strength) return 1;    // UPTREND
    if (max_ll >= adaptive_trend_strength) return -1;   // DOWNTREND
    return 0;  // NO TREND
}

// ===== SUPPORT/RESISTANCE DETECTION =====
void FindSupportResistance(double &res, double &sup) {
    // Identify recent pivot points
    double highest = High[ArrayMaximum(High, 30)];
    double lowest = Low[ArrayMinimum(Low, 30)];

    res = highest;
    sup = lowest;
}

// ===== VOLUME CONFIRMATION =====
bool CheckVolume(int threshold) {
    // Average volume of last 5 candles
    double avg_vol = (Volume[1] + Volume[2] + Volume[3] + Volume[4] + Volume[5]) / 5;

    if (Volume[0] >= avg_vol * threshold / 100) {
        return true;
    }
    return false;
}

// ===== LOT SIZE CALCULATION =====
double CalculateLotSize(double risk_pips, double risk_amount) {
    double pip_value = SymbolInfoDouble(Symbol(), SYMBOL_TRADE_TICK_VALUE);

    // lot_size = risk_amount / (risk_pips * pip_value)
    double lot = risk_amount / (risk_pips * pip_value);

    double min_lot = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_MIN);
    double max_lot = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_MAX);

    if (lot < min_lot) lot = min_lot;
    if (lot > max_lot) lot = max_lot;

    return lot;
}

// ===== OPEN ORDER =====
void OpenOrder(int signal_type, double entry, double sl, double tp, double lot, string comment) {
    int ticket;

    if (signal_type == SIGNAL_UP) {
        ticket = OrderSend(Symbol(), OP_BUY, lot, entry, 10, sl, tp, comment);
    } else {
        ticket = OrderSend(Symbol(), OP_SELL, lot, entry, 10, sl, tp, comment);
    }

    if (ticket < 0) {
        Print("Order failed: ", GetLastError());
    } else {
        Print("Order opened: ", ticket);
    }
}

// ===== CHECK OPEN POSITIONS =====
void CheckOpenPositions() {
    for (int i = OrdersTotal() - 1; i >= 0; i--) {
        if (OrderSelect(i, SELECT_BY_POS)) {
            if (OrderSymbol() == Symbol() && OrderMagicNumber() == MAGIC) {
                // Trade still open, MT5 handles TP/SL automatically
            }
        }
    }
}

// ===== COUNT OPEN POSITIONS =====
int CountOpenPositions(string symbol) {
    int count = 0;
    for (int i = 0; i < OrdersTotal(); i++) {
        if (OrderSelect(i, SELECT_BY_POS)) {
            if (OrderSymbol() == symbol) {
                count++;
            }
        }
    }
    return count;
}

// ===== ADAPTIVE PARAMETERS =====
void AdaptParameters() {
    if (recent_trades_count < 5) return;

    // Calculate recent win rate
    int recent_wins = 0;
    for (int i = 0; i < recent_trades_count; i++) {
        if (recent_trades[i].result == 1) recent_wins++;
    }

    double recent_wr = (double)recent_wins / recent_trades_count;

    // Adapt based on performance
    if (recent_wr < 0.40) {
        // Tighten filters
        adaptive_trend_strength = MathMin(8, adaptive_trend_strength + 1);
        adaptive_sl_pips = MathMax(30, adaptive_sl_pips - 5);
        Print("ADAPT: Tightening (WR=", recent_wr * 100, "%)");
    }
    else if (recent_wr > 0.55) {
        // Relax filters
        adaptive_trend_strength = MathMax(5, adaptive_trend_strength - 1);
        adaptive_sl_pips = MathMin(80, adaptive_sl_pips + 5);
        Print("ADAPT: Relaxing (WR=", recent_wr * 100, "%)");
    }

    adaptation_count++;
}

// ===== ON DEINIT =====
void OnDeinit(const int reason) {
    Print("=== STRATEGY STOPPED ===");
    Print("Total Trades: ", total_trades);
    Print("Winning: ", winning_trades, " (", total_trades > 0 ? winning_trades * 100 / total_trades : 0, "%)");
    Print("Total Pips: +", total_pips);
}

// ===== CONSTANTS =====
#define SIGNAL_UP 1
#define SIGNAL_DOWN -1
#define MAGIC 20240401
