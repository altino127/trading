import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH_INFINOX = "C:/Program Files/Infinox MetaTrader 5 Terminal/terminal64.exe"
TF = mt5.TIMEFRAME_M5
DATE_FROM = datetime(2023, 1, 1)
DATE_TO   = datetime(2026, 4, 25)

print("Conectando ao Infinox...")
ok = mt5.initialize(path=PATH_INFINOX, timeout=15000)
print(f"Conectado: {ok} | Erro: {mt5.last_error()}")

if ok:
    ti = mt5.terminal_info()
    ai = mt5.account_info()
    print(f"Terminal: {ti.name if ti else 'N/A'}")
    print(f"Conectado ao broker: {ti.connected if ti else 'N/A'}")
    print(f"Conta: {ai.login if ai else 'N/A'} | Server: {ai.server if ai else 'N/A'}")

    symbols_to_test = ['CL-OIL', 'USDMXN', 'AUDUSD', 'SPX500', 'XAUUSD', 'NAS100']

    for sym in symbols_to_test:
        # Adiciona ao watchlist antes de puxar dados
        selected = mt5.symbol_select(sym, True)
        info = mt5.symbol_info(sym)
        if info is None:
            print(f"  {sym}: simbolo nao encontrado")
            continue

        print(f"\n  {sym}:")
        print(f"    Visivel: {info.visible} | Spread: {info.spread} | Digits: {info.digits}")

        # Tenta puxar ultimos 100 candles primeiro
        rates = mt5.copy_rates_from_pos(sym, TF, 0, 100)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            print(f"    Ultimos 100 candles: OK | ultimo={df['time'].iloc[-1]} | close={df['close'].iloc[-1]}")

            # Agora tenta range completo
            rates_full = mt5.copy_rates_range(sym, TF, DATE_FROM, DATE_TO)
            if rates_full is not None:
                print(f"    Range 2023-2026: {len(rates_full)} candles")
            else:
                print(f"    Range 2023-2026: FALHOU | {mt5.last_error()}")
        else:
            print(f"    Sem dados recentes | erro={mt5.last_error()}")

mt5.shutdown()
