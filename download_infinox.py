"""
Download historico completo do Infinox MT5 — chunks mensais retroativos
Estrategia: pede mes a mes de 2026 ate 2023, forcando o terminal a buscar do servidor
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import time
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH_INFINOX = "C:/Program Files/Infinox MetaTrader 5 Terminal/terminal64.exe"
TF_MAP = {
    'M5':  mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1':  mt5.TIMEFRAME_H1,
}
# Timeframe principal — M15 tem melhor custo/beneficio para correlacoes intraday
TF_NAME = 'M15'
TF = TF_MAP[TF_NAME]

SYMBOLS = {
    'CL-OIL':  'oil',
    'USDMXN':  'usdmxn',
    'AUDUSD':  'audusd',
    'SPX500':  'spx500',
    'XAUUSD':  'gold',
    'NAS100':  'nas100',
    'EURUSD':  'eurusd',
}

os.makedirs("C:/estrategia/data", exist_ok=True)

print("Conectando ao Infinox...")
if not mt5.initialize(path=PATH_INFINOX, timeout=20000):
    print(f"ERRO: {mt5.last_error()}")
    exit(1)

info = mt5.terminal_info()
print(f"Terminal: {info.name} | Build: {info.build}")
print(f"Broker: {mt5.account_info().server}\n")

def download_symbol(sym, name):
    mt5.symbol_select(sym, True)
    time.sleep(0.3)

    all_frames = []
    date_end = datetime(2026, 4, 25)
    date_start = datetime(2023, 1, 1)

    # Gera lista de meses de forma retroativa (do mais recente para o mais antigo)
    chunks = []
    cur = date_end
    while cur > date_start:
        chunk_start = max(cur - relativedelta(months=1), date_start)
        chunks.append((chunk_start, cur))
        cur = chunk_start

    print(f"  {sym} ({name}): {len(chunks)} chunks mensais para baixar...")

    ok_count    = 0
    fail_count  = 0
    total_bars  = 0

    for i, (d_from, d_to) in enumerate(chunks):
        rates = mt5.copy_rates_range(sym, TF, d_from, d_to)

        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)[['time','open','high','low','close','tick_volume']]
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = df.rename(columns={'tick_volume':'volume'})
            all_frames.append(df)
            ok_count   += 1
            total_bars += len(df)
            print(f"    [{i+1:02d}/{len(chunks)}] {d_from.strftime('%Y-%m')} OK  | {len(df):5d} bars", end='\r')
        else:
            fail_count += 1
            err = mt5.last_error()
            print(f"    [{i+1:02d}/{len(chunks)}] {d_from.strftime('%Y-%m')} ERRO {err}   ", end='\r')

        time.sleep(0.15)  # respira entre requests

    print()  # newline apos o progresso

    if all_frames:
        df_full = pd.concat(all_frames).drop_duplicates('time').sort_values('time').reset_index(drop=True)
        path = f"C:/estrategia/data/infinox_{name}_{TF_NAME.lower()}.csv"
        df_full.to_csv(path, index=False)
        inicio = df_full['time'].iloc[0]
        fim    = df_full['time'].iloc[-1]
        print(f"  SALVO: {path}")
        print(f"  Total: {len(df_full):,} bars | {inicio.date()} -> {fim.date()} | Chunks OK:{ok_count} ERRO:{fail_count}")
        return df_full
    else:
        print(f"  FALHOU: nenhum dado obtido para {sym}")
        return None

print("="*60)
print("INICIANDO DOWNLOAD — pode levar alguns minutos")
print("="*60)

results = {}
for sym, name in SYMBOLS.items():
    df = download_symbol(sym, name)
    results[name] = df
    print()

print("="*60)
print("RESUMO FINAL")
print("="*60)
ok = [(n, df) for n, df in results.items() if df is not None]
fail = [n for n, df in results.items() if df is None]
for name, df in ok:
    print(f"  OK   {name:<10} {len(df):>8,} bars | {df['time'].iloc[0].date()} -> {df['time'].iloc[-1].date()}")
for name in fail:
    print(f"  ERRO {name}")

mt5.shutdown()
print("\nPronto.")
