"""Download ativos extras do Infinox — VIX, USDX, USDJPY, CHINA50, GER40, USDCAD"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH_INFINOX = "C:/Program Files/Infinox MetaTrader 5 Terminal/terminal64.exe"
TF           = mt5.TIMEFRAME_M15
DATE_FROM    = datetime(2023, 1, 1)
DATE_TO      = datetime(2026, 4, 25)
DATA_DIR     = "C:/estrategia/data"

EXTRA = {
    'VIX':     'vix',
    'USDX':    'usdx',
    'USDJPY':  'usdjpy',
    'USDCAD':  'usdcad',
    'CHINA50': 'china50',
    'GER40':   'ger40',
}

os.makedirs(DATA_DIR, exist_ok=True)
print("Conectando Infinox...")
mt5.initialize(path=PATH_INFINOX, timeout=15000)

def download(sym, name):
    mt5.symbol_select(sym, True); time.sleep(0.3)
    frames = []
    cur = DATE_TO
    while cur > DATE_FROM:
        d_from = max(cur - relativedelta(months=1), DATE_FROM)
        r = mt5.copy_rates_range(sym, TF, d_from, cur)
        if r is not None and len(r) > 0:
            df = pd.DataFrame(r)[['time','open','high','low','close','tick_volume']]
            df['time'] = pd.to_datetime(df['time'], unit='s')
            frames.append(df)
        cur = d_from
        time.sleep(0.1)

    if not frames:
        print(f"  ERRO {sym}"); return
    df_full = pd.concat(frames).drop_duplicates('time').sort_values('time').reset_index(drop=True)
    df_full = df_full.rename(columns={'tick_volume':'volume'})
    path = f"{DATA_DIR}/infinox_{name}_m15.csv"
    df_full.to_csv(path, index=False)
    print(f"  OK  {sym:<10} {len(df_full):>7,} bars | {df_full['time'].iloc[0].date()} -> {df_full['time'].iloc[-1].date()}")

for sym, name in EXTRA.items():
    download(sym, name)

mt5.shutdown()
print("Pronto.")
