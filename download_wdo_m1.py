"""Download WDO M1 — 2023 a 2026 em chunks mensais"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH_XP   = "C:/Program Files/MetaTrader 5/terminal64.exe"
TF        = mt5.TIMEFRAME_M1
DATE_FROM = datetime(2023, 1, 1)
DATE_TO   = datetime(2026, 4, 25)
DATA_DIR  = "C:/estrategia/data"
os.makedirs(DATA_DIR, exist_ok=True)

print("Conectando MT5 (XP)...")
if not mt5.initialize(path=PATH_XP, timeout=15000):
    print(f"ERRO: {mt5.last_error()}"); exit(1)

mt5.symbol_select('WDO$', True)
time.sleep(0.3)

# Verifica se o simbolo existe
info = mt5.symbol_info('WDO$')
if info is None:
    print("Simbolo WDO$ nao encontrado. Tentando WDOFUT...")
    mt5.symbol_select('WDOFUT', True)
    SIMBOLO = 'WDOFUT'
else:
    SIMBOLO = 'WDO$'

print(f"Simbolo: {SIMBOLO}")

frames = []
cur    = DATE_TO
chunks = []
while cur > DATE_FROM:
    d_from = max(cur - relativedelta(months=1), DATE_FROM)
    chunks.append((d_from, cur))
    cur = d_from

print(f"Total de chunks: {len(chunks)} meses\n")
total_bars = 0

for i, (d_from, d_to) in enumerate(chunks):
    rates = mt5.copy_rates_range(SIMBOLO, TF, d_from, d_to)
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)[['time','open','high','low','close','tick_volume']]
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.rename(columns={'tick_volume':'volume'})
        frames.append(df)
        total_bars += len(df)
        print(f"  [{i+1:02d}/{len(chunks)}] {d_from.strftime('%Y-%m')}  {len(df):6,} bars  total={total_bars:,}", end='\r')
    else:
        print(f"  [{i+1:02d}/{len(chunks)}] {d_from.strftime('%Y-%m')}  ERRO {mt5.last_error()}", end='\r')
    time.sleep(0.08)

print()
mt5.shutdown()

if not frames:
    print("Nenhum dado coletado."); exit(1)

df_full = pd.concat(frames).drop_duplicates('time').sort_values('time').reset_index(drop=True)

# Converte para BRT (UTC-3)
df_full['time'] = df_full['time'] + pd.Timedelta(hours=-3)

path = f"{DATA_DIR}/xp_wdo_m1.csv"
df_full.to_csv(path, index=False)
print(f"\nSalvo: {path}")
print(f"Total: {len(df_full):,} candles M1")
print(f"Periodo: {df_full['time'].iloc[0]} -> {df_full['time'].iloc[-1]}")
print(f"Horas disponiveis: {sorted(df_full['time'].dt.hour.unique().tolist())}")
