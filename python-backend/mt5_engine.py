import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

class MT5Engine:
    def __init__(self):
        self.connected = False
        self.account_info = None

    def connect(self, account_id, password, server):
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            return False

        authorized = mt5.login(int(account_id), password=password, server=server)
        if authorized:
            self.connected = True
            self.account_info = mt5.account_info()._asdict()
            print(f"Connected to MT5: {server}")
            return True
        else:
            print("failed to connect at account #{}, error code: {}".format(account_id, mt5.last_error()))
            return False

    def get_account_status(self):
        if not self.connected:
             return None
        info = mt5.account_info()
        if info is None:
             return None
        return info._asdict()

    def get_positions(self, symbol="XAUUSD"):
        if not self.connected:
            return []
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return []
        return [p._asdict() for p in positions]

    def get_tick(self, symbol="XAUUSD"):
        if not self.connected:
            return None
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return tick._asdict()

mt5_engine = MT5Engine()
