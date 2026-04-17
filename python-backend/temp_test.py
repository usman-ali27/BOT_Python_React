import time
import MetaTrader5 as mt5
from mt5_engine import mt5_engine
from trading_daemon import daemon

print("Running Flow Validations...")
if not mt5.initialize():
    print("MT5 Not running locally.")
else:
    mt5_engine.connected = True
    print("MT5 Connected.")
    
    pos = mt5.positions_get(symbol="XAUUSD")
    print(f"Pre-test positions via MT5 Engine: {len(pos) if pos else 0}")
    
    print("Testing grid bypass execution opening 0.01 lot BUY...")
    tick = mt5.symbol_info_tick("XAUUSD")
    if tick:
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": "XAUUSD",
            "volume": 0.01,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "deviation": 20,
            "magic": 777777,
            "comment": "Flow Test Entry",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        print("Trade Open Response:", getattr(res, "retcode", "Unknown") if res else "Fail")
        
        pos = mt5.positions_get(symbol="XAUUSD")
        print(f"Executing Grid positions tracked via Engine: {len(pos) if pos else 0}")
        
        time.sleep(1)
        print("Validating Emergency Close sequence...")
        daemon._close_all_positions()
        
        time.sleep(1)
        pos = mt5.positions_get(symbol="XAUUSD")
        print(f"Positions post-emergency close: {len(pos) if pos else 0}")

    mt5.shutdown()
