import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH_INFINOX = "C:/Program Files/Infinox MetaTrader 5 Terminal/terminal64.exe"
TF = mt5.TIMEFRAME_M5
SYM = 'AUDUSD'

print("Conectando...")
mt5.initialize(path=PATH_INFINOX, timeout=15000)
mt5.symbol_select(SYM, True)

# Testa copy_rates_from_pos com counts crescentes
for count in [10, 100, 500, 1000, 5000, 10000, 50000]:
    r = mt5.copy_rates_from_pos(SYM, TF, 0, count)
    if r is not None:
        print(f"  from_pos count={count:6d} -> OK, retornou {len(r)} candles, mais antigo: {pd.to_datetime(r[0]['time'], unit='s')}")
    else:
        print(f"  from_pos count={count:6d} -> FALHOU | {mt5.last_error()}")

# Testa copy_rates_from (data inicio + count) com data sem timezone
print()
for start in [datetime(2026, 4, 1), datetime(2025, 1, 1), datetime(2024, 1, 1), datetime(2023, 1, 1)]:
    r = mt5.copy_rates_from(SYM, TF, start, 5000)
    if r is not None:
        print(f"  from date={start.date()} -> OK, {len(r)} candles")
    else:
        print(f"  from date={start.date()} -> FALHOU | {mt5.last_error()}")

# Verifica server timezone
ti = mt5.terminal_info()
print(f"\nServer time offset: UTC+{ti.trade_server_timezone if hasattr(ti,'trade_server_timezone') else 'N/A'}")
print(f"Broker: {mt5.account_info().server}")

mt5.shutdown()
