from sentiment import gold_sentiment
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mt5_engine import mt5_engine
from ai_agent import ai_engine
from backtest_engine import backtest_engine
from trading_daemon import daemon
from prop_firm_rules import list_profiles


app = FastAPI(title="AlphaGold Python Backend")
@app.get("/sentiment/gold")
def get_gold_sentiment():
    try:
        score = gold_sentiment()
        return {"sentiment": score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sentiment error: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MT5Credentials(BaseModel):
    accountID: str
    password: str
    server: str

@app.post("/mt5/connect")
async def connect_mt5(creds: MT5Credentials):
    success = mt5_engine.connect(creds.accountID, creds.password, creds.server)
    if success:
        account_status = mt5_engine.get_account_status()
        return {
            "status": "connected",
            "account": creds.accountID,
            "server": creds.server,
            "balance": account_status.get("balance", 0) if account_status else 0,
            "equity": account_status.get("equity", 0) if account_status else 0,
            "currency": account_status.get("currency", "USD") if account_status else "USD",
            "bot_ready": True,
        }
    else:
         raise HTTPException(status_code=400, detail="MT5 Connection Failed. Check credentials.")

@app.get("/mt5/status")
def get_mt5_status():
    if not mt5_engine.connected:
        raise HTTPException(status_code=400, detail="Not connected")
    return {
        "account": mt5_engine.get_account_status(),
        "positions": mt5_engine.get_positions(),
        "tick": mt5_engine.get_tick(),
        "bot_active": daemon.is_running,
        "prop_profile": daemon.prop_profile.key,
        "prop_risk": daemon.prop_risk_status.__dict__ if daemon.prop_risk_status else None,
        "last_backtest": daemon.last_backtest_result,
        "grid_levels": [
            {
                "id": lv.level_id,
                "type": lv.direction,
                "price": lv.price,
                "status": lv.status,
                "lot": lv.lot
            } for lv in getattr(daemon.grid_state, 'levels', []) if lv.status == "PENDING"
        ]
    }

@app.post("/bot/start")
def start_bot():
    if not mt5_engine.connected:
        raise HTTPException(status_code=400, detail="MT5 not connected")
    success = daemon.start()
    if not success:
         raise HTTPException(status_code=400, detail="Live start rejected by the deterministic backtest gate.")
    return {"status": "started"}

@app.post("/bot/config")
def update_bot_config(config: dict):
    if "propProfile" in config:
        daemon.set_prop_profile(config["propProfile"])
    if daemon.grid_state and daemon.grid_state.config:
        cfg = daemon.grid_state.config
        if "gridSpacing" in config:
            # We treat gridSpacing as spacing_multiplier override simply mapping 1:1 or we set it later. 
            pass # Currently spacing is ATR driven but respects $10 floor.
        if "basket_take_profit_usd" in config:
            cfg.basket_take_profit_usd = config["basket_take_profit_usd"]
        if "basket_stop_loss_usd" in config:
            cfg.basket_stop_loss_usd = config["basket_stop_loss_usd"]
        if "max_open_levels" in config:
            cfg.max_open_levels = config["max_open_levels"]
    return {"status": "config_updated", "prop_profile": daemon.prop_profile.key}

@app.post("/bot/stop")
def stop_bot():
    daemon.stop()
    return {"status": "stopped"}

@app.get("/ai/insight")
def get_ai_insight():
    insight = ai_engine.analyze_news_sentiment("GC=F")
    return insight

@app.get("/backtest/run")
def run_backtest_simulation():
    res = backtest_engine.run_backtest()
    if "error" in res:
        raise HTTPException(status_code=500, detail=res["error"])
    return res

@app.get("/backtest/gold4mo")
def run_gold4mo_backtest():
    res = backtest_engine.run_backtest_from_csv("python-backend/gold_4mo_1h.csv")
    if "error" in res:
        raise HTTPException(status_code=500, detail=res["error"])
    return res

@app.get("/prop/profiles")
def get_prop_profiles():
    return {"profiles": list_profiles(), "active_profile": daemon.prop_profile.key}

@app.get("/health")
def health_check():
    return {"status": "ok", "backend": "python-fastapi"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
