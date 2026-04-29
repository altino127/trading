import yfinance as yf
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ativos globais que precisamos - tickers Yahoo Finance
# Para correlacao com WIN/WDO - usaremos 1h (melhor custo-beneficio: historia longa + intraday)
TICKERS = {
    'AUDUSD=X':  'audusd',
    'USDMXN=X':  'usdmxn',
    'BZ=F':      'brent',
    'CL=F':      'wti_oil',
    '^GSPC':     'spx500',
    'ES=F':      'spx_futures',
    '^TNX':      'us10y',
    'GC=F':      'gold',
    'DX=F':      'dxy',
}

print("Verificando disponibilidade de dados no Yahoo Finance...")
print(f"{'Ticker':<15} {'Nome':<15} {'Intervalo':<10} {'Inicio':<12} {'Fim':<12} {'Candles'}")
print("-" * 75)

for ticker, name in TICKERS.items():
    try:
        # Tenta 1h primeiro (60 dias de limite no yfinance para 1h)
        df_1h = yf.download(ticker, start='2024-01-01', end='2026-04-25',
                            interval='1h', progress=False, auto_adjust=True)

        # Tenta 1d para historico completo
        df_1d = yf.download(ticker, start='2023-01-01', end='2026-04-25',
                            interval='1d', progress=False, auto_adjust=True)

        if len(df_1d) > 0:
            inicio = str(df_1d.index[0].date())
            fim    = str(df_1d.index[-1].date())
            print(f"  {ticker:<13} {name:<15} 1d={len(df_1d):<6} 1h={len(df_1h):<6} {inicio} -> {fim}")
        else:
            print(f"  {ticker:<13} {name:<15} SEM DADOS")
    except Exception as e:
        print(f"  {ticker:<13} ERRO: {e}")
