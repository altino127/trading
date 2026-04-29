import MetaTrader5 as mt5
import sys

def check_terminal(path, label, search_terms):
    print(f"\n{'='*60}")
    print(f"TERMINAL: {label}")
    print(f"{'='*60}")

    if not mt5.initialize(path=path, timeout=10000):
        print(f"ERRO ao conectar: {mt5.last_error()}")
        return

    info = mt5.terminal_info()
    print(f"Conectado: {info.name} | Conta: {mt5.account_info().login if mt5.account_info() else 'N/A'}")

    all_symbols = mt5.symbols_get()
    if not all_symbols:
        print("Nenhum símbolo encontrado")
        mt5.shutdown()
        return

    symbol_names = [s.name for s in all_symbols]
    print(f"Total de símbolos: {len(symbol_names)}")

    print(f"\nSímbolos encontrados para {label}:")
    for term in search_terms:
        matches = [s for s in symbol_names if term.upper() in s.upper()]
        if matches:
            print(f"  [{term}] -> {matches[:10]}")
        else:
            print(f"  [{term}] -> NAO ENCONTRADO")

    mt5.shutdown()

# Terminal XP (B3)
check_terminal(
    path="C:/Program Files/MetaTrader 5/terminal64.exe",
    label="XP - B3",
    search_terms=["WIN", "WDO", "PETR", "DI1", "IND", "DOL", "IBOV"]
)

# Terminal Infinox (Global)
check_terminal(
    path="C:/Program Files/Infinox MetaTrader 5 Terminal/terminal64.exe",
    label="INFINOX - Global",
    search_terms=["BRENT", "OIL", "DXY", "MXN", "AUD", "US10", "TNX", "SPX", "NAS", "GOLD", "XAU"]
)
