import MetaTrader5 as mt5
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH_INFINOX = "C:/Program Files/Infinox MetaTrader 5 Terminal/terminal64.exe"
mt5.initialize(path=PATH_INFINOX, timeout=15000)

all_syms = [s.name for s in mt5.symbols_get()]

searches = {
    "Cobre":       ["COPPER","XCU","HG"],
    "VIX":         ["VIX","VOLX"],
    "China":       ["CHINA","CN50","A50","HK50","HANGSENG","HSI"],
    "DAX":         ["DAX","GER"],
    "FTSE":        ["UK100","FTSE"],
    "CAD":         ["USDCAD","CADUSD","CAD"],
    "JPY":         ["USDJPY","JPYUSD","JPY"],
    "Bitcoin":     ["BTC","BTCUSD","XBTUSD"],
    "Bonds EUA":   ["US02","US10","US30","TNX","TNOTE","TBOND"],
    "Prata":       ["SILVER","XAGUSD","XAG"],
    "Gás Natural": ["NGAS","NATGAS","NG"],
    "Trigo/Soja":  ["WHEAT","SOYBEAN","CORN"],
    "EEM/EM":      ["EEM","MSCI","EM"],
    "Dólar Index": ["USDX","DXY","DOLLAR"],
}

print("Simbolos disponiveis no Infinox por categoria:\n")
for cat, terms in searches.items():
    found = []
    for t in terms:
        found += [s for s in all_syms if t.upper() in s.upper()]
    if found:
        print(f"  {cat:<15}: {found[:8]}")
    else:
        print(f"  {cat:<15}: (nenhum)")

mt5.shutdown()
