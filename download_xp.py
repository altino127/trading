"""
Download dados B3 da XP em M15 — WIN, WDO, PETR4, DI1
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH_XP   = "C:/Program Files/MetaTrader 5/terminal64.exe"
TF        = mt5.TIMEFRAME_M15
DATE_FROM = datetime(2023, 1, 1)
DATE_TO   = datetime(2026, 4, 25)

SYMBOLS = {
    'WIN$':  'win',
    'WDO$N': 'wdo',
    'PETR4': 'petr4',
    'DI1$N': 'di1',
}

os.makedirs("C:/estrategia/data", exist_ok=True)

print("Conectando ao XP...")
if not mt5.initialize(path=PATH_XP, timeout=15000):
    print(f"ERRO: {mt5.last_error()}"); exit(1)

print(f"Conectado: {mt5.terminal_info().name} | Conta: {mt5.account_info().login}\n")

def download_symbol(sym, name):
    mt5.symbol_select(sym, True)
    time.sleep(0.2)

    all_frames = []
    cur = DATE_TO
    chunks = []
    while cur > DATE_FROM:
        chunk_start = max(cur - relativedelta(months=1), DATE_FROM)
        chunks.append((chunk_start, cur))
        cur = chunk_start

    print(f"  {sym} ({name}): {len(chunks)} chunks...")

    for i, (d_from, d_to) in enumerate(chunks):
        rates = mt5.copy_rates_range(sym, TF, d_from, d_to)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)[['time','open','high','low','close','tick_volume']]
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = df.rename(columns={'tick_volume':'volume'})
            all_frames.append(df)
            print(f"    [{i+1:02d}/{len(chunks)}] {d_from.strftime('%Y-%m')} OK {len(df):5d} bars", end='\r')
        else:
            print(f"    [{i+1:02d}/{len(chunks)}] {d_from.strftime('%Y-%m')} ERRO {mt5.last_error()}", end='\r')
        time.sleep(0.1)

    print()
    if not all_frames:
        print(f"  FALHOU: sem dados para {sym}")
        return None

    df_full = pd.concat(all_frames).drop_duplicates('time').sort_values('time').reset_index(drop=True)
    path = f"C:/estrategia/data/xp_{name}_m15.csv"
    df_full.to_csv(path, index=False)
    print(f"  SALVO: {path} | {len(df_full):,} bars | {df_full['time'].iloc[0].date()} -> {df_full['time'].iloc[-1].date()}")
    return df_full

for sym, name in SYMBOLS.items():
    download_symbol(sym, name)
    print()

mt5.shutdown()
print("Download B3 concluido.")
