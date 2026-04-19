from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import yfinance as yf

from grid_backtest import BacktestConfig, run_grid_backtest
from grid_engine import GridConfig
from prop_firm_rules import (
    compute_prop_risk_snapshot,
    evaluate_phase_targets,
    get_profile,
)


class BacktestEngine:
    def __init__(self, profile_key: str = "shared_10k_2step"):
        self.profile_key = profile_key

    def run_backtest(
        self,
        ticker: str = "GC=F",
        period: str = "6mo",
        interval: str = "1h",
        profile_key: str | None = None,
    ) -> dict:
        try:
            profile = get_profile(profile_key or self.profile_key)
            data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
            data = self._prepare_price_data(data)
            if data.empty:
                return {"error": "Failed to download usable market data."}
            return self._run_deterministic_backtest(data, profile_key=profile.key, source=f"{ticker} {period} {interval}")
        except Exception as exc:
            return {"error": str(exc)}

    def run_backtest_from_csv(self, csv_path: str, profile_key: str | None = None) -> dict:
        try:
            profile = get_profile(profile_key or self.profile_key)
            data = pd.read_csv(csv_path, skiprows=[1, 2])
            data = self._prepare_price_data(data)
            if data.empty:
                return {"error": "CSV missing usable OHLC columns."}
            return self._run_deterministic_backtest(data, profile_key=profile.key, source=csv_path)
        except Exception as exc:
            return {"error": str(exc)}

    def _run_deterministic_backtest(self, data: pd.DataFrame, *, profile_key: str, source: str) -> dict:
        profile = get_profile(profile_key)
        grid_cfg = self._build_conservative_grid_config(profile.account_size)
        bt_cfg = BacktestConfig(spread_points=0.25, slippage_points=0.12, rebalance_bars=24)

        result = run_grid_backtest(data, grid_cfg, bt_cfg)
        summary = result["summary"]
        equity_curve = result["equity_curve"].copy()
        monthly = result["monthly"].copy()

        if equity_curve.empty:
            return {
                "error": "Not enough data to backtest.",
                "source": source,
            }

        equity_curve["balance"] = profile.account_size + equity_curve["equity"]
        equity_curve["time"] = pd.to_datetime(equity_curve["time"], utc=True, errors="coerce")
        equity_curve = equity_curve.dropna(subset=["time"]).reset_index(drop=True)
        equity_curve["date"] = equity_curve["time"].dt.strftime("%Y-%m-%d")

        final_balance = float(equity_curve["balance"].iloc[-1])
        final_equity = final_balance
        trading_days = int(equity_curve["date"].nunique())
        prop_status = self._evaluate_prop_limits(equity_curve, profile.key)
        phase_status = evaluate_phase_targets(profile, balance=final_balance, trading_days=trading_days)

        history = [
            {
                "time": row["time"].isoformat(),
                "balance": round(float(row["balance"]), 2),
                "equity": round(float(row["balance"]), 2),
            }
            for _, row in equity_curve.iterrows()
        ]
        path = [{"time": item["time"], "price": item["equity"]} for item in history]

        monthly_rows = []
        if not monthly.empty:
            for _, row in monthly.iterrows():
                monthly_rows.append(
                    {
                        "month": str(row["month"]),
                        "end_equity": round(float(profile.account_size + row["end_equity"]), 2),
                        "min_equity": round(float(profile.account_size + row["min_equity"]), 2),
                        "max_equity": round(float(profile.account_size + row["max_equity"]), 2),
                        "month_pnl": round(float(row["month_pnl"]), 2),
                    }
                )

        return {
            "source": source,
            "profile": asdict(profile),
            "config": {
                "grid": asdict(grid_cfg),
                "backtest": asdict(bt_cfg),
            },
            "final_balance": round(final_balance, 2),
            "final_equity": round(final_equity, 2),
            "net_profit": round(final_balance - profile.account_size, 2),
            "total_return_pct": round((final_balance - profile.account_size) / profile.account_size * 100.0, 2),
            "max_drawdown_pct": round(summary["max_dd"] / profile.account_size * 100.0, 2),
            "profit_factor": summary["profit_factor"],
            "trades_taken": summary["trades"],
            "wins": summary["wins"],
            "losses": summary["losses"],
            "accuracy": round(summary["win_rate"] / 100.0, 4),
            "win_rate_pct": summary["win_rate"],
            "trading_days": trading_days,
            "history": history,
            "path": path,
            "monthly": monthly_rows,
            "prop_status": prop_status,
            "phase_status": phase_status,
            "passed_backtest_gate": (
                not prop_status["breached"]
                and summary["trades"] >= 12
                and summary["win_rate"] >= 45.0
                and summary["profit_factor"] >= 1.2
                and summary["max_dd"] <= profile.account_size * 0.05
            ),
        }

    def _evaluate_prop_limits(self, equity_curve: pd.DataFrame, profile_key: str) -> dict:
        profile = get_profile(profile_key)
        daily_snapshots = []
        breached = False
        breach_reason = ""

        for date, day_df in equity_curve.groupby("date"):
            day_start_balance = float(day_df["balance"].iloc[0])
            day_start_equity = day_start_balance
            day_low_equity = float(day_df["balance"].min())
            day_end_equity = float(day_df["balance"].iloc[-1])

            snapshot = compute_prop_risk_snapshot(
                profile,
                balance=day_end_equity,
                equity=day_low_equity,
                day_start_balance=day_start_balance,
                day_start_equity=day_start_equity,
            )
            daily_snapshots.append(
                {
                    "date": date,
                    "daily_loss_used": snapshot.daily_loss_used,
                    "daily_loss_limit": snapshot.daily_loss_limit,
                    "daily_buffer": snapshot.daily_buffer,
                    "breached": snapshot.breached,
                    "breach_reason": snapshot.breach_reason,
                }
            )
            if snapshot.breached and not breached:
                breached = True
                breach_reason = snapshot.breach_reason

        final_balance = float(equity_curve["balance"].iloc[-1])
        global_snapshot = compute_prop_risk_snapshot(
            profile,
            balance=final_balance,
            equity=float(equity_curve["balance"].min()),
            day_start_balance=float(equity_curve["balance"].iloc[0]),
            day_start_equity=float(equity_curve["balance"].iloc[0]),
        )
        if global_snapshot.breached and not breached:
            breached = True
            breach_reason = global_snapshot.breach_reason

        return {
            "profile": profile.key,
            "breached": breached,
            "breach_reason": breach_reason,
            "daily": daily_snapshots,
            "global": asdict(global_snapshot),
        }

    def _build_conservative_grid_config(self, account_size: float) -> GridConfig:
        return GridConfig(
            symbol="XAUUSD",
            timeframe="1h",
            base_lot=0.01 if account_size <= 10_000 else 0.02,
            levels_buy=3,
            levels_sell=3,
            spacing_multiplier=1.15,
            tp_multiplier=1.4,
            sl_multiplier=2.2,
            max_open_levels=3,
            ai_direction_enabled=True,
            ai_spacing_enabled=True,
            lot_scale_with_direction=False,
            auto_profile_switch=True,
            profile_name="Prop Safe",
            basket_take_profit_usd=18.0,
            basket_stop_loss_usd=-35.0,
            basket_close_on_profit=True,
            basket_close_on_loss=True,
            basket_trailing_tp=True,
            basket_trailing_step_usd=6.0,
            session_pause_enabled=True,
            session_pause_list="Asian",
            max_daily_loss_usd=180.0,
            max_drawdown_pct=4.5,
            min_equity_usd=account_size * 0.92,
        )

    def _prepare_price_data(self, data: pd.DataFrame) -> pd.DataFrame:
        if data is None or data.empty:
            return pd.DataFrame()

        work = data.copy()
        if isinstance(work.columns, pd.MultiIndex):
            work.columns = [str(col[0]) for col in work.columns]

        if "Price" in work.columns and "Datetime" not in work.columns:
            parsed_price = pd.to_datetime(work["Price"], utc=True, errors="coerce")
            if parsed_price.notna().sum() >= max(3, len(work) // 2):
                work["Datetime"] = parsed_price
                work = work.drop(columns=["Price"])

        rename_map = {}
        for col in work.columns:
            lower = str(col).strip().lower()
            if lower == "datetime":
                rename_map[col] = "Datetime"
            elif lower == "open":
                rename_map[col] = "Open"
            elif lower == "high":
                rename_map[col] = "High"
            elif lower == "low":
                rename_map[col] = "Low"
            elif lower == "close":
                rename_map[col] = "Close"
            elif lower == "price" and "Close" not in work.columns:
                rename_map[col] = "Close"
        work = work.rename(columns=rename_map)

        if "Datetime" in work.columns:
            work["Datetime"] = pd.to_datetime(work["Datetime"], utc=True, errors="coerce")
            work = work.set_index("Datetime")
        else:
            work.index = pd.to_datetime(work.index, utc=True, errors="coerce")

        required = ["Open", "High", "Low", "Close"]
        if not set(required).issubset(work.columns):
            return pd.DataFrame()

        for col in required:
            work[col] = pd.to_numeric(work[col], errors="coerce")

        work = work[required].dropna().sort_index()
        work = work[~work.index.isna()]
        return work


backtest_engine = BacktestEngine()
