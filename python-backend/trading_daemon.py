import time
import sys
import os
import threading
import MetaTrader5 as mt5
import pandas as pd
from mt5_engine import mt5_engine
from prop_firm_rules import compute_prop_risk_snapshot, get_profile, trading_day_key

# Sentiment analysis
from sentiment import gold_sentiment

# Ensure project root is in sys.path for grid_engine import
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from grid_engine import (
    GridConfig,
    load_grid_state,
    save_grid_state,
    activate_grid,
    check_levels_hit,
    mark_level_open,
    mark_level_closed,
    place_grid_order_mt5,
    get_open_levels,
    basket_floating_pnl_usd,
    should_close_basket,
    deactivate_grid
)

class TradingDaemon:
    def log_open_levels_stats(self):
        """Log stats for all currently open grid levels for live AI feedback and analytics."""
        from grid_engine import get_open_levels, save_grid_state
        import datetime
        open_levels = get_open_levels(self.grid_state)
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        for lv in open_levels:
            # Log unrealized PnL and duration
            unrealized_pnl = 0.0
            if lv.entry_price > 0:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick:
                    if lv.direction == "BUY":
                        unrealized_pnl = (tick.ask - lv.entry_price) * lv.lot * 100.0
                    else:
                        unrealized_pnl = (lv.entry_price - tick.bid) * lv.lot * 100.0
            duration = 0.0
            if lv.opened_at:
                try:
                    opened_dt = datetime.datetime.fromisoformat(lv.opened_at.replace('Z', '+00:00'))
                    duration = (datetime.datetime.now(datetime.timezone.utc) - opened_dt).total_seconds() / 60
                except Exception:
                    pass
            # Append to audit log as LIVE_LEVEL
            from grid_engine import append_grid_audit
            append_grid_audit({
                "event": "LIVE_LEVEL",
                "level_id": lv.level_id,
                "symbol": self.symbol,
                "direction": lv.direction,
                "entry_price": lv.entry_price,
                "lot": lv.lot,
                "unrealized_pnl": unrealized_pnl,
                "duration_min": duration,
                "opened_at": lv.opened_at,
                "timestamp": now,
            })

    def _should_pause_grid(self, df):
        """Return True if volatility or trend is too high for safe grid trading."""
        if len(df) < 20:
            return False
        recent = df.tail(20)
        volatility = recent['Close'].std()
        trend_strength = abs(recent['Close'].iloc[-1] - recent['Close'].mean())
        if volatility > 10 or trend_strength > 10:
            print(f"[GRID FILTER] High volatility ({volatility:.2f}) or trend ({trend_strength:.2f}) detected. Pausing grid.")
            return True
        return False
    def __init__(self, symbol="XAUUSD", initial_balance=10000.0):
        self.is_running = False
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.daily_start_equity = initial_balance
        self.daily_start_balance = initial_balance
        self.prop_profile = get_profile("shared_10k_2step")
        self.prop_day_key = trading_day_key(self.prop_profile)
        self.prop_risk_status = None
        self.last_backtest_result = None
        
        # Grid settings
        self.lot_size = 0.01
        self.grid_state = load_grid_state()

    def set_prop_profile(self, profile_key: str):
        self.prop_profile = get_profile(profile_key)
        self.prop_day_key = trading_day_key(self.prop_profile)
        self.initial_balance = self.prop_profile.account_size
        self.daily_start_balance = self.initial_balance
        self.daily_start_equity = self.initial_balance
        return self.prop_profile
        
    def start(self):
        if not mt5_engine.connected:
            print("Cannot start daemon. MT5 not connected.")
            return False
            
        print("Running XAUUSD backtest intelligence matrix...")
        from backtest_engine import backtest_engine
        results = backtest_engine.run_backtest(profile_key=self.prop_profile.key)
        self.last_backtest_result = results

        if "error" in results:
            print(f"[REJECTED] Backtest error: {results['error']}. Refusing entry.")
            return False

        if not results.get("passed_backtest_gate", False):
            print("[REJECTED] Backtest gate failed. Refusing entry.")
            return False

        account_status = mt5_engine.get_account_status()
        if account_status:
            balance = float(account_status.get("balance", self.initial_balance))
            equity = float(account_status.get("equity", balance))
            self.initial_balance = self.prop_profile.account_size
            self.daily_start_balance = balance
            self.daily_start_equity = equity
            self.prop_day_key = trading_day_key(self.prop_profile)
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.start()
        # Start scheduled grid re-analysis every 5 minutes automatically
        self.schedule_grid_reanalysis(interval_minutes=5)
        print(
            "Trading Daemon started successfully. "
            f"Win rate {results.get('win_rate_pct', 0):.1f}% | "
            f"PF {results.get('profit_factor', 0):.2f}"
        )
        return True

    def stop(self):
        self.is_running = False
        if hasattr(self, 'thread') and self.thread != threading.current_thread():
            self.thread.join()
        print("Trading Daemon stopped.")

    def update_daily_equity(self):
        status = mt5_engine.get_account_status()
        if status:
            current_day_key = trading_day_key(self.prop_profile)
            if current_day_key != self.prop_day_key:
                self.prop_day_key = current_day_key
                self.daily_start_balance = float(status['balance'])
                self.daily_start_equity = float(status['equity'])

    def check_prop_firm_rules(self, balance, equity):
        snapshot = compute_prop_risk_snapshot(
            self.prop_profile,
            balance=float(balance),
            equity=float(equity),
            day_start_balance=float(self.daily_start_balance),
            day_start_equity=float(self.daily_start_equity),
        )
        self.prop_risk_status = snapshot

        if snapshot.breached:
            print(f"[EMERGENCY] {snapshot.breach_reason}")
            self.stop()
            self._close_all_positions()
            return False

        if snapshot.soft_breached:
            print(f"[RISK WARNING] {snapshot.soft_reason}")

        return True

    def _close_all_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return
            
        for pos in positions:
            tick = mt5.symbol_info_tick(self.symbol)
            action = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": action,
                "price": price,
                "deviation": 20,
                "magic": 123456,
                "comment": "Emergency Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            mt5.order_send(request)

    def _modify_position_sl(self, ticket, sl_price):
        pos = mt5.positions_get(ticket=ticket)
        if pos and len(pos) > 0:
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": self.symbol,
                "sl": float(sl_price),
                "tp": float(pos[0].tp),
            }
            mt5.order_send(request)

    def _run_loop(self):
        self.update_daily_equity()
        while self.is_running:
            try:
                account_status = mt5_engine.get_account_status()
                if not account_status:
                    time.sleep(1)
                    continue
                    
                balance = float(account_status['balance'])
                equity = float(account_status['equity'])

                if not self.check_prop_firm_rules(balance, equity):
                    break
                    
                self._process_advanced_grid()
                # Log open level stats for live AI feedback
                self.log_open_levels_stats()
                time.sleep(1)
            except Exception as e:
                print(f"[THREAD CRASH] Grid loop error: {e}")
                time.sleep(2)

    def _process_advanced_grid(self):
        from grid_brain import get_recommendation, load_brain, train
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return

        # Sentiment analysis filter
        try:
            sentiment = gold_sentiment()
            print(f"[SENTIMENT] Gold news sentiment score: {sentiment:.2f}")
            # If sentiment is strongly negative or positive, pause grid for safety
            if sentiment < -0.3:
                print("[SENTIMENT] Strong negative sentiment detected. Pausing grid activation.")
                return
            if sentiment > 0.3:
                print("[SENTIMENT] Strong positive sentiment detected. Pausing grid activation.")
                return
        except Exception as e:
            print(f"[SENTIMENT] Sentiment analysis failed: {e}")

        # Load live OHLCV for Grid AI structure analysis
        rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M15, 0, 100)
        if rates is None or len(rates) == 0:
            return

        df = pd.DataFrame(rates)
        df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)

        current_price = tick.ask  # Proxy execution standard

        # --- Grid Expiry/Deactivation Logic ---
        import datetime
        if self.grid_state.active:
            # If all levels are pending and grid is older than 15 minutes, deactivate
            pending_levels = [lv for lv in self.grid_state.levels if lv.status == "PENDING"]
            open_levels = [lv for lv in self.grid_state.levels if lv.status == "OPEN"]
            if len(pending_levels) == len(self.grid_state.levels) and len(pending_levels) > 0:
                try:
                    created_dt = datetime.datetime.fromisoformat(self.grid_state.created_at.replace('Z', '+00:00'))
                    age_minutes = (datetime.datetime.now(datetime.timezone.utc) - created_dt).total_seconds() / 60
                    if age_minutes > 15:
                        print(f"[GRID ENGINE] Grid expired (all pending, age {age_minutes:.1f} min). Deactivating.")
                        self.grid_state = deactivate_grid(self.grid_state)
                        save_grid_state(self.grid_state)
                        train()
                        return
                except Exception:
                    pass
            # If grid is older than 1 hour, deactivate regardless
            try:
                created_dt = datetime.datetime.fromisoformat(self.grid_state.created_at.replace('Z', '+00:00'))
                age_minutes = (datetime.datetime.now(datetime.timezone.utc) - created_dt).total_seconds() / 60
                if age_minutes > 60:
                    print(f"[GRID ENGINE] Grid forcibly expired (age {age_minutes:.1f} min). Deactivating.")
                    self.grid_state = deactivate_grid(self.grid_state)
                    save_grid_state(self.grid_state)
                    train()
                    return
            except Exception:
                pass

        # 1. Basket Profit Trailing & SL Guards
        if self.grid_state.active:
            pnl = basket_floating_pnl_usd(self.grid_state, current_price)
            should_close, reason = should_close_basket(self.grid_state, pnl)
            if should_close:
                print(f"[GRID ENGINE] Closing Basket: {reason}")
                self._close_all_positions()  # Use hard broker purge
                self.grid_state = deactivate_grid(self.grid_state)
                save_grid_state(self.grid_state)
                # Train the AI brain after grid deactivation (basket close)
                train()
                # Let it reactivate fresh next cycle
                return

            # Individual 30 pips ($3.00) Trailing SL
            open_levels = [lv for lv in self.grid_state.levels if lv.status == "OPEN"]
            for lv in open_levels:
                if not lv.ticket:
                    continue
                if lv.direction == "BUY":
                    profit_dist = current_price - lv.entry_price
                    if profit_dist >= 3.0:
                        new_sl = round(current_price - 3.0, 2)
                        if lv.sl_price < new_sl:
                            lv.sl_price = new_sl
                            print(f"[GRID ENGINE] Trailing SL for BUY {lv.level_id} updated to {new_sl}")
                            self._modify_position_sl(lv.ticket, new_sl)
                elif lv.direction == "SELL":
                    profit_dist = lv.entry_price - current_price
                    if profit_dist >= 3.0:
                        new_sl = round(current_price + 3.0, 2)
                        if lv.sl_price == 0.0 or lv.sl_price > new_sl:
                            lv.sl_price = new_sl
                            print(f"[GRID ENGINE] Trailing SL for SELL {lv.level_id} updated to {new_sl}")
                            self._modify_position_sl(lv.ticket, new_sl)

        # 1.5 Stale Grid / Escaped Market Check
        if self.grid_state.active:
            open_levels = [lv for lv in self.grid_state.levels if lv.status == "OPEN"]
            if len(open_levels) == 0:
                dist = abs(current_price - self.grid_state.anchor_price)
                if dist > (self.grid_state.regime.recommended_spacing * 3):
                    print(f"[GRID ENGINE] Market broke structure (moved ${dist:.2f}). Dismantling stale grid.")
                    self.grid_state = deactivate_grid(self.grid_state)
                    save_grid_state(self.grid_state)
                    train()
                    return

                from datetime import datetime, timezone
                try:
                    created_dt = datetime.fromisoformat(self.grid_state.created_at.replace('Z', '+00:00'))
                    if (datetime.now(timezone.utc) - created_dt).total_seconds() >= 600:
                        print(f"[GRID ENGINE] 10-minute AI cadence hit. Re-Evaluating Market Sentiment...")
                        self.grid_state = deactivate_grid(self.grid_state)
                        save_grid_state(self.grid_state)
                        train()
                        return
                except Exception:
                    pass

        # 2. Level Activation Triggers
        if self.grid_state.active:
            triggered = check_levels_hit(self.grid_state, current_price)
            if triggered:
                for lv in triggered:
                    print(f"[GRID ENGINE] Firing Grid Level {lv.level_id} @ {lv.price}")
                    res = place_grid_order_mt5(lv, self.symbol)
                    if res["success"]:
                        mark_level_open(self.grid_state, lv.level_id, res["ticket"], res["price"])
                    else:
                        print(f"Failed to fill {lv.level_id}:", res['message'])
                        if "Invalid volume" not in res['message']:
                            lv.status = "CANCELLED"  # avoid endless spam on hard error
                save_grid_state(self.grid_state)

        # 3. Dynamic Bias Grid Generation (AI Brain integration)
        if not self.grid_state.active:
            print("[GRID ENGINE] Analyzing Regimes & Computing New Layout...")
            if self._should_pause_grid(df):
                print("[GRID ENGINE] Grid activation paused due to market conditions.")
                return
            from grid_brain import ml_recommendation, train_ml_model
            brain = load_brain()
            train_ml_model()
            regime = "RANGING"
            if hasattr(self.grid_state, 'regime') and hasattr(self.grid_state.regime, 'regime'):
                regime = getattr(self.grid_state.regime, 'regime', 'RANGING')
            rec = ml_recommendation(self.symbol, regime, brain)
            cfg = GridConfig(
                symbol=self.symbol,
                base_lot=self.lot_size,
                spacing_multiplier=rec.get("spacing_multiplier", 1.0),
                tp_multiplier=rec.get("tp_multiplier", 1.5),
                sl_multiplier=rec.get("sl_multiplier", 2.5),
                max_open_levels=rec.get("max_open_levels", 6),
                levels_buy=4,  # You can further tune these using rec["buy_ratio"]
                levels_sell=4,
            )
            self.grid_state = activate_grid(current_price, df, cfg)
            save_grid_state(self.grid_state)
            print(f"[GRID ENGINE] New Layout Built. Bias: {self.grid_state.regime.direction_bias}. Levels: {len(self.grid_state.levels)}")

    def schedule_grid_reanalysis(self, interval_minutes=5):
        """Periodically re-analyze grid and market conditions."""
        import threading, time
        def loop():
            while True:
                print("[GRID ENGINE] Scheduled grid re-analysis...")
                self._process_advanced_grid()
                time.sleep(interval_minutes * 60)
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _close_basket_safely(self):
        # Override local logic with engine closing
        pass


daemon = TradingDaemon()
