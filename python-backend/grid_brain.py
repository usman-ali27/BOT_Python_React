# ───────────────────────────────────────────────────────────────────────────
# Periodic grid re-analysis (example function)
# ───────────────────────────────────────────────────────────────────────────
import time
def periodic_grid_reanalysis(interval_minutes=60):
    """Periodically retrain ML model and re-analyze past grids."""
    while True:
        print(f"[ML] Periodic re-analysis running...")
        train_ml_model()
        time.sleep(interval_minutes * 60)
# ───────────────────────────────────────────────────────────────────────────
# Machine Learning Enhancement (scikit-learn)
# ───────────────────────────────────────────────────────────────────────────

import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

MODEL_FILE = BASE_DIR / "grid_brain_model.pkl"

def prepare_ml_data():
    """Prepare features and labels from closed trades for ML training."""
    trades = load_closed_trades()
    if not trades:
        return None, None
    df = pd.DataFrame(trades)
    # Feature engineering: select relevant columns and fill missing
    features = [
        "spacing_used", "tp_multiplier", "sl_multiplier", "max_open_levels",
        "buy_ratio", "direction", "session", "regime", "volatility", "grid_duration", "regime_detected"
    ]
    for col in features:
        if col not in df:
            df[col] = 0
    # Encode categorical features
    df["direction"] = df["direction"].astype(str).map({"BUY": 1, "SELL": -1}).fillna(0)
    df["session"] = df["session"].astype(str).map({"London": 1, "NY": 2, "Asia": 3}).fillna(0)
    df["regime"] = df["regime"].astype(str).map({"RANGING": 0, "TRENDING": 1, "BREAKOUT": 2}).fillna(0)
    df["regime_detected"] = df["regime_detected"].astype(str).map({"RANGING": 0, "TRENDING": 1, "SIDEWAYS": 2}).fillna(0)
    df = df.fillna(0)
    X = df[["spacing_used", "tp_multiplier", "sl_multiplier", "max_open_levels", "buy_ratio", "direction", "session", "regime", "volatility", "grid_duration", "regime_detected"]]
    y = df["profit_usd"]
    return X, y

def train_ml_model():
    """Train and save a RandomForestRegressor to predict profit from grid params."""
    X, y = prepare_ml_data()
    if X is None or len(X) < 10:
        print("[ML] Not enough data to train ML model.")
        return None
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    print(f"[ML] Model trained. Test MSE: {mse:.4f}")
    joblib.dump(model, MODEL_FILE)
    return model

def load_ml_model():
    """Load the trained ML model if available."""
    if MODEL_FILE.exists():
        return joblib.load(MODEL_FILE)
    return None

def ml_recommendation(symbol: str, regime: str, brain: BrainMemory | None = None) -> dict:
    """Use ML model to recommend grid parameters for given symbol/regime."""
    model = load_ml_model()
    if model is None:
        return get_recommendation(symbol, regime, brain)
    # Use last known stats as base features
    rec = get_recommendation(symbol, regime, brain)
    # Build feature vector
    direction = 1  # Assume BUY bias for now
    session = 1    # Assume London for now
    regime_val = {"RANGING": 0, "TRENDING": 1, "BREAKOUT": 2}.get(regime, 0)
    X = [[
        rec["spacing_multiplier"],
        rec["tp_multiplier"],
        rec["sl_multiplier"],
        rec["max_open_levels"],
        rec["buy_ratio"],
        direction,
        session,
        regime_val
    ]]
    # Predict profit for small grid param variations and pick best
    best_params = rec.copy()
    best_profit = -float("inf")
    for spacing in [rec["spacing_multiplier"] * f for f in [0.8, 1.0, 1.2]]:
        for tp in [rec["tp_multiplier"] * f for f in [0.8, 1.0, 1.2]]:
            for sl in [rec["sl_multiplier"] * f for f in [0.8, 1.0, 1.2]]:
                for max_open in [max(2, int(rec["max_open_levels"] * f)) for f in [0.8, 1.0, 1.2]]:
                    test_X = [[spacing, tp, sl, max_open, rec["buy_ratio"], direction, session, regime_val]]
                    pred_profit = model.predict(test_X)[0]
                    if pred_profit > best_profit:
                        best_profit = pred_profit
                        best_params.update({
                            "spacing_multiplier": spacing,
                            "tp_multiplier": tp,
                            "sl_multiplier": sl,
                            "max_open_levels": max_open
                        })
    best_params["ml_predicted_profit"] = best_profit
    best_params["ml_used"] = True
    return best_params
"""
Grid Brain — AI Learning Module for Grid Trading.

Learns from every closed grid trade to improve:
  1. Optimal ATR spacing multiplier (per symbol / per regime)
  2. Direction confidence calibration (was the AI bias correct?)
  3. Best performing sessions and timeframes for grid mode

Storage: grid_brain_memory.json  (structured summary)
Source:  grid_audit_log.jsonl    (raw trade events from grid_engine)

The brain is consulted by grid_engine.activate_grid() to override the
default spacing_multiplier with a learned value.

Design:
  - No external ML library required — uses pure statistical learning
    (exponential moving average over outcome metric).
  - Incorporates simple reinforcement: spacing that produced positive
    avg_profit_per_lot gets a nudge toward that value.
  - Direction accuracy: tracks how often the AI bias matched the
    winning trade direction → adjusts confidence scaling.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

BASE_DIR = Path(__file__).parent
BRAIN_FILE = BASE_DIR / "grid_brain_memory.json"
AUDIT_FILE = BASE_DIR / "grid_audit_log.jsonl"

# Learning rate (EMA alpha): lower = slower but more stable adaptation
LEARNING_RATE = 0.15
MIN_SAMPLES = 5   # need at least this many trades before adapting


# ───────────────────────────────────────────────────────────────────────────
# Data structures
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class RegimeStats:
    """Learned statistics for a specific symbol+regime combination."""
    symbol: str = "XAUUSD"
    regime: str = "RANGING"
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    avg_profit_usd: float = 0.0
    avg_profit_pips: float = 0.0
    learned_spacing_mult: float = 1.0   # ATR multiplier that works best
    spacing_ema: float = 1.0            # EMA of spacing used on wins
    direction_accuracy: float = 50.0   # % of time AI bias direction was right
    best_session: str = "London"
    learned_tp_mult: float = 1.5
    learned_sl_mult: float = 2.5
    learned_max_open_levels: int = 6
    learned_buy_ratio: float = 0.5
    updated_at: str = ""


@dataclass
class BrainMemory:
    """Full brain state stored to disk."""
    regime_stats: dict[str, RegimeStats] = field(default_factory=dict)
    global_trades: int = 0
    global_wins: int = 0
    global_losses: int = 0
    global_avg_profit: float = 0.0
    last_trained_at: str = ""
    version: int = 1


# ───────────────────────────────────────────────────────────────────────────
# Persistence
# ───────────────────────────────────────────────────────────────────────────

def load_brain() -> BrainMemory:
    """Load brain memory from disk, or return blank brain."""
    if not BRAIN_FILE.exists():
        return BrainMemory()
    try:
        raw = json.loads(BRAIN_FILE.read_text(encoding="utf-8"))
        stats_raw = raw.get("regime_stats", {})
        stats = {k: RegimeStats(**v) for k, v in stats_raw.items()}
        return BrainMemory(
            regime_stats=stats,
            global_trades=raw.get("global_trades", 0),
            global_wins=raw.get("global_wins", 0),
            global_losses=raw.get("global_losses", 0),
            global_avg_profit=raw.get("global_avg_profit", 0.0),
            last_trained_at=raw.get("last_trained_at", ""),
            version=raw.get("version", 1),
        )
    except Exception:
        return BrainMemory()


def save_brain(brain: BrainMemory) -> None:
    """Persist brain memory to disk."""
    brain.last_trained_at = _now()
    raw = {
        "regime_stats": {k: asdict(v) for k, v in brain.regime_stats.items()},
        "global_trades": brain.global_trades,
        "global_wins": brain.global_wins,
        "global_losses": brain.global_losses,
        "global_avg_profit": brain.global_avg_profit,
        "last_trained_at": brain.last_trained_at,
        "version": brain.version,
    }
    BRAIN_FILE.write_text(json.dumps(raw, indent=2), encoding="utf-8")


# ───────────────────────────────────────────────────────────────────────────
# Audit log reader
# ───────────────────────────────────────────────────────────────────────────

def load_closed_trades() -> list[dict]:
    """Load all LEVEL_CLOSED events from the grid audit log."""
    if not AUDIT_FILE.exists():
        return []
    trades = []
    try:
        for ln in AUDIT_FILE.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                entry = json.loads(ln)
                if entry.get("event") == "LEVEL_CLOSED":
                    entry = enrich_trade_with_market_context(entry)
                    trades.append(entry)
            except Exception:
                pass
    except Exception:
        pass
    return trades

# ───────────────────────────────────────────────────────────────────────────
# Market context enrichment for each trade
# ───────────────────────────────────────────────────────────────────────────
import numpy as np
def enrich_trade_with_market_context(trade: dict) -> dict:
    """
    Add volatility, regime, and loss reason to trade dict.
    Assumes trade contains 'open_time', 'close_time', 'symbol', 'profit_usd', 'sl_hit', 'tp_hit', etc.
    """
    open_price = trade.get("open_price", 0)
    close_price = trade.get("close_price", 0)
    profit = trade.get("profit_usd", 0)
    # Volatility: abs(open-close) or placeholder
    trade["volatility"] = abs(open_price - close_price)
    # Regime detection (simple):
    if abs(open_price - close_price) > 5:
        trade["regime_detected"] = "TRENDING"
    elif abs(open_price - close_price) < 2:
        trade["regime_detected"] = "SIDEWAYS"
    else:
        trade["regime_detected"] = "RANGING"
    # Loss reason
    if profit < 0:
        if trade.get("sl_hit", False):
            trade["loss_reason"] = "SL_HIT"
        elif trade.get("volatility", 0) > 5:
            trade["loss_reason"] = "VOLATILITY_SPIKE"
        elif trade["regime_detected"] == "TRENDING":
            trade["loss_reason"] = "TREND_REVERSAL"
        else:
            trade["loss_reason"] = "OTHER"
    else:
        trade["loss_reason"] = "NONE"
    # Time features (optional)
    trade["grid_duration"] = trade.get("close_time", 0) - trade.get("open_time", 0)
    return trade


# ───────────────────────────────────────────────────────────────────────────
# Core training
# ───────────────────────────────────────────────────────────────────────────

def train(brain: BrainMemory | None = None) -> BrainMemory:
    """
    Re-train the brain from all available audit log trades.

    Call this:
      - On page load (cheap — just reads JSONL and aggregates)
      - After each grid close event

    Returns updated BrainMemory (also saved to disk).
    """
    if brain is None:
        brain = BrainMemory()

    trades = load_closed_trades()
    if not trades:
        return brain

    # Aggregate by (symbol, regime) key
    buckets: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        key = f"{t.get('symbol', 'XAUUSD')}|{t.get('regime', 'RANGING')}"
        buckets[key].append(t)

    brain.global_trades = len(trades)
    wins = [t for t in trades if t.get("profit_usd", 0) > 0]
    brain.global_wins = len(wins)
    brain.global_losses = brain.global_trades - brain.global_wins
    if trades:
        brain.global_avg_profit = round(
            sum(t.get("profit_usd", 0) for t in trades) / len(trades), 4
        )

    for key, bucket in buckets.items():
        symbol, regime = key.split("|", 1)
        stats = brain.regime_stats.get(key) or RegimeStats(symbol=symbol, regime=regime)

        bucket_wins = [t for t in bucket if t.get("profit_usd", 0) > 0]
        bucket_losses = [t for t in bucket if t.get("profit_usd", 0) <= 0]

        stats.total_trades = len(bucket)
        stats.wins = len(bucket_wins)
        stats.losses = len(bucket_losses)
        stats.avg_profit_usd = round(
            sum(t.get("profit_usd", 0) for t in bucket) / len(bucket), 4
        )
        stats.avg_profit_pips = round(
            sum(t.get("profit_pips", 0) for t in bucket) / len(bucket), 2
        )

        # Learn spacing multiplier: use EMA of spacing on winning trades
        if len(bucket_wins) >= MIN_SAMPLES:
            win_spacings = [t.get("spacing_used", 1.0) for t in bucket_wins
                            if t.get("spacing_used", 0) > 0]
            if win_spacings:
                # mean spacing on wins → target multiplier (normalize by ATR)
                # We store raw spacing EMA since ATR context varies; caller
                # uses this as a reference to bias the multiplier.
                new_ema = win_spacings[-1]
                for s in win_spacings[1:]:
                    new_ema = (1 - LEARNING_RATE) * new_ema + LEARNING_RATE * s
                stats.spacing_ema = round(new_ema, 6)

                # heuristic: if avg profit is positive, slightly increase mult;
                # if negative, decrease mult to tighten grid
                if stats.avg_profit_usd > 0:
                    stats.learned_spacing_mult = round(
                        min(3.0, stats.learned_spacing_mult * (1 + LEARNING_RATE * 0.2)), 3
                    )
                else:
                    stats.learned_spacing_mult = round(
                        max(0.3, stats.learned_spacing_mult * (1 - LEARNING_RATE * 0.2)), 3
                    )

            win_tp = [float(t.get("tp_multiplier", 0)) for t in bucket_wins if t.get("tp_multiplier", 0) > 0]
            win_sl = [float(t.get("sl_multiplier", 0)) for t in bucket_wins if t.get("sl_multiplier", 0) > 0]
            win_max_open = [int(t.get("max_open_levels", 0)) for t in bucket_wins if t.get("max_open_levels", 0) > 0]
            buy_wins = sum(1 for t in bucket_wins if str(t.get("direction", "")).upper() == "BUY")

            if win_tp:
                stats.learned_tp_mult = round(sum(win_tp) / len(win_tp), 3)
            if win_sl:
                stats.learned_sl_mult = round(sum(win_sl) / len(win_sl), 3)
            if win_max_open:
                stats.learned_max_open_levels = int(round(sum(win_max_open) / len(win_max_open)))
            if bucket_wins:
                stats.learned_buy_ratio = round(buy_wins / len(bucket_wins), 3)

        # Direction accuracy: compare AI bias with actual profitable direction
        if len(bucket) >= MIN_SAMPLES:
            correct = 0
            for t in bucket:
                ai_bias = t.get("bias", "NEUTRAL")
                trade_dir = t.get("direction", "BUY")
                profitable = t.get("profit_usd", 0) > 0
                # Correct if: AI was BULLISH and BUY was profitable, or
                #             AI was BEARISH and SELL was profitable
                ai_matched_dir = (
                    (ai_bias == "BULLISH" and trade_dir == "BUY") or
                    (ai_bias == "BEARISH" and trade_dir == "SELL")
                )
                if ai_matched_dir and profitable:
                    correct += 1
                elif not ai_matched_dir and not profitable:
                    correct += 1    # correctly avoided bad direction
            stats.direction_accuracy = round(correct / len(bucket) * 100, 1)

        # Best session
        sessions = [t.get("session", "London") for t in bucket_wins] if bucket_wins else []
        if sessions:
            from collections import Counter
            stats.best_session = Counter(sessions).most_common(1)[0][0]

        stats.updated_at = _now()
        brain.regime_stats[key] = stats

    save_brain(brain)
    return brain


# ───────────────────────────────────────────────────────────────────────────
# Recommendation API  (called by grid_engine / UI)
# ───────────────────────────────────────────────────────────────────────────

def get_recommendation(
    symbol: str,
    regime: str,
    brain: BrainMemory | None = None,
) -> dict[str, Any]:
    """
    Return the brain's learned recommendation for a symbol+regime.

    Returns dict with:
      - spacing_multiplier: float (use this for ATR * mult)
      - direction_accuracy: float (0-100, how well AI bias performed)
      - avg_profit_usd:     float
      - win_rate:           float (0-100)
      - total_trades:       int
      - has_data:           bool (False if not enough samples yet)
    """
    if brain is None:
        brain = load_brain()

    key = f"{symbol}|{regime}"
    stats = brain.regime_stats.get(key)

    if stats is None or stats.total_trades < MIN_SAMPLES:
        return {
            "spacing_multiplier": 1.0,
            "direction_accuracy": 50.0,
            "avg_profit_usd": 0.0,
            "win_rate": 0.0,
            "tp_multiplier": 1.5,
            "sl_multiplier": 2.5,
            "max_open_levels": 6,
            "buy_ratio": 0.5,
            "total_trades": stats.total_trades if stats else 0,
            "has_data": False,
            "message": f"Not enough data yet ({stats.total_trades if stats else 0}/{MIN_SAMPLES} trades needed)",
        }

    win_rate = round(stats.wins / stats.total_trades * 100, 1) if stats.total_trades else 0.0
    return {
        "spacing_multiplier": stats.learned_spacing_mult,
        "direction_accuracy": stats.direction_accuracy,
        "avg_profit_usd": stats.avg_profit_usd,
        "win_rate": win_rate,
        "tp_multiplier": stats.learned_tp_mult,
        "sl_multiplier": stats.learned_sl_mult,
        "max_open_levels": stats.learned_max_open_levels,
        "buy_ratio": stats.learned_buy_ratio,
        "total_trades": stats.total_trades,
        "best_session": stats.best_session,
        "has_data": True,
        "message": f"Learned from {stats.total_trades} trades — win rate {win_rate}%",
    }


def get_global_stats(brain: BrainMemory | None = None) -> dict[str, Any]:
    """Return global performance summary across all symbols/regimes."""
    if brain is None:
        brain = load_brain()
    win_rate = 0.0
    if brain.global_trades > 0:
        win_rate = round(brain.global_wins / brain.global_trades * 100, 1)
    return {
        "total_trades": brain.global_trades,
        "wins": brain.global_wins,
        "losses": brain.global_losses,
        "win_rate": win_rate,
        "avg_profit_usd": brain.global_avg_profit,
        "last_trained_at": brain.last_trained_at,
        "regimes_tracked": len(brain.regime_stats),
    }


def regime_stats_dataframe(brain: BrainMemory | None = None) -> pd.DataFrame:
    """Return a DataFrame of all learned regime stats for display."""
    if brain is None:
        brain = load_brain()
    if not brain.regime_stats:
        return pd.DataFrame()

    rows = []
    for stats in brain.regime_stats.values():
        win_rate = round(stats.wins / stats.total_trades * 100, 1) if stats.total_trades else 0.0
        rows.append({
            "Symbol": stats.symbol,
            "Regime": stats.regime,
            "Trades": stats.total_trades,
            "Win %": win_rate,
            "Avg P&L ($)": stats.avg_profit_usd,
            "Avg Pips": stats.avg_profit_pips,
            "Learned Mult": stats.learned_spacing_mult,
            "Learned TP": stats.learned_tp_mult,
            "Learned SL": stats.learned_sl_mult,
            "Learned MaxOpen": stats.learned_max_open_levels,
            "Learned BuyRatio": stats.learned_buy_ratio,
            "Dir Accuracy %": stats.direction_accuracy,
            "Best Session": stats.best_session,
            "Updated": stats.updated_at[:16] if stats.updated_at else "-",
        })
    return pd.DataFrame(rows)


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
