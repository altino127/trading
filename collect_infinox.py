import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
import time
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH_INFINOX = "C:/Program Files/Infinox MetaTrader 5 Terminal/terminal64.exe"
TF = mt5.TIMEFRAME_M5

SYMBOLS = {
    'CL-OIL':  'brent_oil',
    'USDMXN':  'usdmxn',
    'AUDUSD':  'audusd',
    'SPX500':  'spx500',
    'XAUUSD':  'gold',
    'NAS100':  'nas100',
}

# Usa datas UTC-aware para evitar ambiguidade
DATE_FROM = datetime(2023, 1, 1, tzinfo=timezone.utc)
DATE_TO   = datetime(2026, 4, 25, tzinfo=timezone.utc)

print("Conectando ao Infinox...")
if not mt5.initialize(path=PATH_INFINOX, timeout=15000):
    print(f"Falha: {mt5.last_error()}")
    exit(1)

print("Conectado com sucesso.\n")
all_data = {}

for sym, name in SYMBOLS.items():
    mt5.symbol_select(sym, True)
    time.sleep(0.5)

    # Estrategia 1: copy_rates_range com UTC
    rates = mt5.copy_rates_range(sym, TF, DATE_FROM, DATE_TO)

    if rates is None or len(rates) == 0:
        # Estrategia 2: copy_rates_from_pos com contagem grande
        print(f"  {sym}: range falhou, tentando from_pos...")
        rates = mt5.copy_rates_from_pos(sym, TF, 0, 200000)

    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
        df = df.rename(columns={'tick_volume': 'volume'})

        # Filtra pelo periodo desejado
        df = df[df['time'] >= pd.Timestamp('2023-01-01', tz='UTC')]
        df = df[df['time'] <= pd.Timestamp('2026-04-25', tz='UTC')]

        all_data[name] = df
        print(f"  OK  {sym:12s} | {len(df):6d} candles | {df['time'].iloc[0].date()} -> {df['time'].iloc[-1].date()}")
    else:
        print(f"  ERRO {sym:11s} | {mt5.last_error()}")

mt5.shutdown()

# Salva CSVs
import os
os.makedirs("C:/estrategia/data", exist_ok=True)

for name, df in all_data.items():
    path = f"C:/estrategia/data/infinox_{name}.csv"
    df.to_csv(path, index=False)
    print(f"Salvo: {path}")

print(f"\nTotal de simbolos coletados: {len(all_data)}/{len(SYMBOLS)}")
