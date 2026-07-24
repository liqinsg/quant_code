# 10_svm_usdjpy_v1.3_daily.py
import pandas as pd
import numpy as np
import yfinance as yf
import talib
import mplfinance as mpf
import matplotlib.pyplot as plt
import schedule
import time
from datetime import datetime
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import classification_report


# ----------------------
# ⚙️ GLOBAL CONFIG
# ----------------------
RUN_BACKTEST = True
PLOT_EQUITY_CURVE = True
PLOT_PRICE_WITH_SIGNALS = True

# Risk Settings
RISK_PER_TRADE_PCT = 1.0
REWARD_RATIO = 1.5
SL_MULTIPLIER = 1.0
TP_MULTIPLIER = 1.5
SIGNAL_THRESHOLD = 0.55

# Trading Settings
FOREX_PAIR = "USDJPY=X"       # "EURJPY=X" / "GBPJPY=X"
START_DATE = "2020-01-01"
END_DATE = "2026-07-23"
INITIAL_CAPITAL = 10000

# Schedule Settings
RUN_TIME = "06:30"            # Daily run time (SGT/UTC+8)
RUN_FREQUENCY = "daily"       # Matches D1 training timeframe


# ----------------------
# 1. Feature Engineering
# ----------------------
class FeatureEngineer(BaseEstimator, TransformerMixin):
    def __init__(self, timeperiod=14):
        self.timeperiod = timeperiod

    def fit(self, X, y=None):
        return self

    def transform(self, df):
        df_features = df.copy()
        close = np.asarray(df_features['Close']).ravel()
        high = np.asarray(df_features['High']).ravel()
        low = np.asarray(df_features['Low']).ravel()
        volume = np.asarray(df_features['Volume']).ravel()

        df_features['MA20'] = talib.SMA(close, timeperiod=20)
        df_features['ATR'] = talib.ATR(high, low, close, timeperiod=14)
        df_features['RSI'] = talib.RSI(close, timeperiod=self.timeperiod)
        df_features['CCI'] = talib.CCI(high, low, close, timeperiod=20)

        df_features['PriceChange'] = np.append(np.nan, np.diff(close) / close[:-1])
        df_features['VolChange'] = np.append(np.nan, np.diff(volume) / volume[:-1])

        for lag in [1, 2, 3]:
            df_features[f'RSI_lag{lag}'] = df_features['RSI'].shift(lag)
            df_features[f'VolChange_lag{lag}'] = df_features['VolChange'].shift(lag)

        feature_cols = [
            'MA20', 'ATR', 'RSI', 'CCI', 'PriceChange', 'VolChange',
            'RSI_lag1', 'RSI_lag2', 'RSI_lag3',
            'VolChange_lag1', 'VolChange_lag2', 'VolChange_lag3'
        ]
        return df_features[feature_cols]


# ----------------------
# 2. Data Preparation
# ----------------------
def prepare_forex_dataset(ticker, start, end, max_feature_lookback=20, max_label_lookahead=3, max_lag=3):
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching data for {ticker}...")
    try:
        df = yf.download(ticker, start=start, end=end, progress=False)
        if df.empty:
            print("❌ No data retrieved.")
            return None, None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.sort_index(inplace=True)
        df['Volume'] = df['Volume'].replace(0, 1e-6)
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None, None

    close = np.asarray(df['Close']).ravel()
    future_return = pd.Series(close).pct_change(max_label_lookahead).shift(-max_label_lookahead).values
    df['future_return'] = future_return
    df['label'] = np.where(future_return > 0, 1, 0)

    required_min_len = max_feature_lookback + max_lag + max_label_lookahead
    if len(df) < required_min_len:
        print(f"❌ Not enough data rows. Need at least {required_min_len}, got {len(df)}.")
        return None, None

    temp_sma = talib.SMA(close, timeperiod=max_feature_lookback + max_lag)
    first_valid_idx = pd.Series(temp_sma, index=df.index).first_valid_index()
    if first_valid_idx is None:
        print("❌ Could not determine valid start index.")
        return None, None

    df_clean = df.loc[first_valid_idx:].dropna(subset=['future_return', 'label']).copy()
    if df_clean.empty:
        print("❌ No valid rows after cleaning.")
        return None, None

    y = df_clean['label'].astype(int)
    X_raw = df_clean.drop(columns=['label', 'future_return'])
    print(f"✅ Cleaned shapes: X={X_raw.shape}, y={y.shape}")
    return X_raw, y


# ----------------------
# 3. Core Functions
# ----------------------
def generate_signals(model, X_features, threshold=0.55):
    proba = model.predict_proba(X_features)[:, 1]
    signal = np.zeros(len(proba))
    signal[proba > threshold] = 1
    signal[proba < (1 - threshold)] = -1
    return pd.Series(signal, index=X_features.index, name='signal')


def calculate_risk_levels(entry_price, atr, direction="long"):
    sl_distance = atr * SL_MULTIPLIER
    tp_distance = sl_distance * REWARD_RATIO
    if direction.lower() == "long":
        return {
            "entry": round(entry_price, 4),
            "stop_loss": round(entry_price - sl_distance, 4),
            "take_profit": round(entry_price + tp_distance, 4),
            "risk_pips": round(sl_distance * 100, 2)
        }
    else:
        return {
            "entry": round(entry_price, 4),
            "stop_loss": round(entry_price + sl_distance, 4),
            "take_profit": round(entry_price - tp_distance, 4),
            "risk_pips": round(sl_distance * 100, 2)
        }


def calculate_position_size(capital, risk_pct, entry, sl):
    risk_amt = capital * (risk_pct / 100)
    risk_per_unit = abs(entry - sl)
    return round(risk_amt / risk_per_unit, 2) if risk_per_unit != 0 else 0


def get_live_trade_plan(ticker, model, fe, capital=10000, threshold=0.55):
    try:
        data = yf.download(ticker, period="60d", interval="1d", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        data = data[["Open", "High", "Low", "Close", "Volume"]].copy()
        data["Volume"] = data["Volume"].replace(0, 1e-6)

        features = fe.transform(data).dropna()
        if features.empty:
            return "❌ Not enough data to calculate features"

        latest = features.tail(1)
        prob_up = model.predict_proba(latest)[0, 1]
        entry = float(data["Close"].iloc[-1])
        atr = float(latest["ATR"].iloc[0])

        if prob_up > threshold:
            risk = calculate_risk_levels(entry, atr, "long")
            dir_text = "📈 BUY / LONG"
        elif prob_up < (1 - threshold):
            risk = calculate_risk_levels(entry, atr, "short")
            dir_text = "📉 SELL / SHORT"
        else:
            return f"""
--- {ticker} TRADE PLAN ({datetime.now().strftime('%Y-%m-%d')}) ---
Probability Up: {prob_up:.1%}
Action: ⏸️ HOLD / NO TRADE
Reason: Probability within neutral range
"""

        size = calculate_position_size(capital, RISK_PER_TRADE_PCT, risk["entry"], risk["stop_loss"])
        return f"""
📊 {ticker} TRADE PLAN ({datetime.now().strftime('%Y-%m-%d')})
--------------------------------
Probability Up: {prob_up:.1%}
Direction: {dir_text}
Entry Price: {risk['entry']}
Stop-Loss: {risk['stop_loss']} ({risk['risk_pips']} pips risk)
Take-Profit: {risk['take_profit']}
Risk/Reward Ratio: 1 : {REWARD_RATIO}
Capital: ${capital:,.2f}
Risk per Trade: {RISK_PER_TRADE_PCT}% = ${(capital * RISK_PER_TRADE_PCT / 100):.2f}
Position Size: {size} units
Potential Profit: ${(size * abs(risk['take_profit'] - risk['entry'])):.2f}
"""
    except Exception as e:
        return f"❌ Error generating trade plan: {str(e)}"


# ----------------------
# 4. Plot Functions
# ----------------------
def plot_with_signals(df, signals, title="Price & Signals", rsi_period=14):
    common_idx = df.index.intersection(signals.index)
    if common_idx.empty:
        print("⚠️ No overlapping data to plot")
        return
    df_plot = df.loc[common_idx].copy()
    signals_aligned = signals.loc[common_idx]

    close = np.asarray(df_plot['Close']).ravel()
    df_plot['RSI'] = talib.RSI(close, timeperiod=rsi_period)

    buy = pd.Series(np.nan, index=df_plot.index)
    sell = pd.Series(np.nan, index=df_plot.index)
    buy.loc[signals_aligned[signals_aligned == 1].index] = df_plot.loc[signals_aligned == 1, 'Close']
    sell.loc[signals_aligned[signals_aligned == -1].index] = df_plot.loc[signals_aligned == -1, 'Close']

    addplots = [
        mpf.make_addplot(buy, type='scatter', marker='^', color='g', markersize=10, panel=0),
        mpf.make_addplot(sell, type='scatter', marker='v', color='r', markersize=10, panel=0),
        mpf.make_addplot(df_plot['RSI'], panel=2, color='purple', ylabel='RSI')
    ]
    plot_type = 'candle' if len(df_plot) < 800 else 'line'

    try:
        mpf.plot(
            df_plot,
            type=plot_type,
            volume=True,
            addplot=addplots,
            title=title,
            style='yahoo',
            figsize=(12, 9),
            panel_ratios=(3, 1, 1),
            warn_too_much_data=2000
        )
    except Exception as e:
        print(f"⚠️ Plot error: {e}")


def plot_equity_curve(data, title="Strategy Equity Curve"):
    try:
        plt.figure(figsize=(12, 5))
        plt.plot(data['equity'], label='Strategy Equity', color='blue', linewidth=2)
        plt.title(title, fontsize=14)
        plt.xlabel('Date')
        plt.ylabel('Capital ($)')
        plt.grid(alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print(f"⚠️ Equity plot error: {e}")


# ----------------------
# 5. Backtest Engine
# ----------------------
def backtest(df_price, signals, initial_capital=10000, fee_pct=0.0002):
    data = df_price.copy()
    data['signal'] = signals
    data['position'] = data['signal'].shift(1).fillna(0)
    data['returns'] = data['Close'].pct_change().fillna(0)
    data['trade'] = data['position'].diff().abs()
    data['net_returns'] = data['position'] * data['returns'] - data['trade'] * fee_pct
    data['equity'] = initial_capital * (1 + data['net_returns']).cumprod()
    data['equity'].iloc[0] = initial_capital

    total_return = (data['equity'].iloc[-1] / initial_capital) - 1
    buy_hold_return = (data['Close'].iloc[-1] / data['Close'].iloc[0]) - 1
    drawdown = (data['equity'] / data['equity'].cummax()) - 1
    max_drawdown = drawdown.min()
    num_trades = int(data['trade'].sum())
    win_rate = (data['net_returns'][data['net_returns'] != 0] > 0).mean() if num_trades > 0 else 0

    metrics = {
        'Initial Capital': f"${initial_capital:,.2f}",
        'Final Equity': f"${data['equity'].iloc[-1]:,.2f}",
        'Total_strategy_return': f"{total_return:.2%}",
        'buy_hold_return': f"{buy_hold_return:.2%}",
        'max_drawdown': f"{max_drawdown:.2%}",
        'num_trades': num_trades,
        'win_rate': f"{win_rate:.2%}"
    }
    return data, metrics


# ----------------------
# 6. Daily Job Function
# ----------------------
def run_daily_job():
    print(f"\n=========================================")
    print(f"⏰ Running Daily Strategy @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"=========================================")

    X_raw, y = prepare_forex_dataset(FOREX_PAIR, START_DATE, END_DATE)
    # ✅ Fixed check for DataFrame/None
    if X_raw is None or y is None or X_raw.empty or y.empty:
        print("❌ Could not proceed: invalid or empty dataset")
        return

    best_score = -np.inf
    best_params = {}
    model = Pipeline([
        ('scaler', StandardScaler()),
        ('svm', SVC(probability=True, class_weight='balanced', random_state=42))
    ])
    param_grid = {'svm__C': [0.1, 1, 10], 'svm__kernel': ['linear', 'rbf']}
    tscv = TimeSeriesSplit(n_splits=5)

    for tp in [10, 14, 20]:
        fe = FeatureEngineer(timeperiod=tp)
        Xf = fe.transform(X_raw)
        comb = pd.concat([Xf, y], axis=1).dropna()
        if comb.empty:
            continue
        Xc, yc = comb.drop(columns=['label']), comb['label']
        grid = GridSearchCV(model, param_grid, cv=tscv, scoring='f1', n_jobs=-1, verbose=0)
        grid.fit(Xc, yc)
        print(f"TP={tp} | Best F1={grid.best_score_:.4f} | Params={grid.best_params_}")
        if grid.best_score_ > best_score:
            best_score = grid.best_score_
            best_params = {**grid.best_params_, 'rsi_timeperiod': tp}

    if not best_params:
        print("❌ No valid model parameters found")
        return

    best_tp = best_params['rsi_timeperiod']
    svm_args = {k.replace('svm__', ''): v for k, v in best_params.items() if k.startswith('svm__')}
    fe_final = FeatureEngineer(timeperiod=best_tp)
    X_final = fe_final.transform(X_raw)
    data_final = pd.concat([X_final, y], axis=1).dropna()
    if data_final.empty:
        print("❌ No valid final data")
        return

    Xm, ym = data_final.drop(columns=['label']), data_final['label']
    final_model = Pipeline([
        ('scaler', StandardScaler()),
        ('svm', SVC(probability=True, class_weight='balanced', random_state=42, **svm_args))
    ])
    final_model.fit(Xm, ym)

    print("\n--- Classification Report ---")
    print(classification_report(ym, final_model.predict(Xm)))

    signals = generate_signals(final_model, Xm, threshold=SIGNAL_THRESHOLD)

    if PLOT_PRICE_WITH_SIGNALS:
        plot_with_signals(X_raw, signals, f"{FOREX_PAIR} Signals", best_tp)

    if RUN_BACKTEST:
        bt_df, metrics = backtest(X_raw.loc[Xm.index], signals, INITIAL_CAPITAL)
        print("\n=== BACKTEST RESULTS ===")
        for k, v in metrics.items():
            print(f"{k}: {v}")
        if PLOT_EQUITY_CURVE:
            plot_equity_curve(bt_df, f"{FOREX_PAIR} Strategy Equity")

    trade_plan = get_live_trade_plan(FOREX_PAIR, final_model, fe_final, capital=INITIAL_CAPITAL, threshold=SIGNAL_THRESHOLD)
    print(trade_plan)

    # Save to log
    try:
        with open("forex_signals.log", "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now()}]\n{trade_plan}\n")
    except Exception as e:
        print(f"⚠️ Could not write to log: {e}")


# ----------------------
# 7. Scheduler Setup
# ----------------------
def start_scheduler():
    print(f"\n✅ Scheduler started. Will run every day at {RUN_TIME} SGT.")
    print("Press Ctrl+C to stop.\n")
    schedule.every().day.at(RUN_TIME).do(run_daily_job)
    while True:
        schedule.run_pending()
        time.sleep(60)


# ----------------------
# Run Once or Start Scheduler
# ----------------------
if __name__ == "__main__":
    run_daily_job()
    # start_scheduler()
