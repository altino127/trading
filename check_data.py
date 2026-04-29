import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TF = mt5.TIMEFRAME_M5
DATE_FROM = datetime(2023, 1, 1)
DATE_TO   = datetime(2026, 4, 25)

def check_data(path, label, symbols):
    print(f"\n{'='*60}")
    print(f"TERMINAL: {label}")
    print(f"{'='*60}")

    if not mt5.initialize(path=path, timeout=10000):
        print(f"ERRO: {mt5.last_error()}")
        return {}

    results = {}
    for sym in symbols:
        rates = mt5.copy_rates_range(sym, TF, DATE_FROM, DATE_TO)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            results[sym] = {
                'candles': len(df),
                'inicio': df['time'].iloc[0].strftime('%Y-%m-%d'),
                'fim':    df['time'].iloc[-1].strftime('%Y-%m-%d'),
                'close_atual': df['close'].iloc[-1]
            }
            print(f"  OK  {sym:15s} | {len(df):6d} candles | {df['time'].iloc[0].date()} -> {df['time'].iloc[-1].date()} | close={df['close'].iloc[-1]:.2f}")
        else:
            print(f"  ERRO {sym:14s} | sem dados | erro={mt5.last_error()}")
            results[sym] = None

    mt5.shutdown()
    return results

# XP - B3
xp_symbols = ['WIN$N', 'WIN$', 'WDO$N', 'WDO$', 'PETR4', 'DI1$N', 'DI1$']
check_data(
    path="C:/Program Files/MetaTrader 5/terminal64.exe",
    label="XP - B3",
    symbols=xp_symbols
)

# Infinox - Global
inf_symbols = ['CL-OIL', 'USDMXN', 'AUDUSD', 'SPX500', 'SPX', 'NAS100', 'XAUUSD', 'GOLDft']
check_data(
    path="C:/Program Files/Infinox MetaTrader 5 Terminal/terminal64.exe",
    label="INFINOX - Global",
    symbols=inf_symbols
)
