"""
Multi-Factor Z-Score Model para WIN e WDO
Fontes: XP MT5 (B3) + Yahoo Finance (global)
"""

import MetaTrader5 as mt5
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.linear_model import LinearRegression
import warnings
import sys
import os
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH_XP = "C:/Program Files/MetaTrader 5/terminal64.exe"
DATE_FROM = datetime(2023, 1, 1)
DATE_TO   = datetime(2026, 4, 25)
ROLL_WIN  = 40   # janela rolling da regressao (dias)
Z_ENTRY   = 2.0  # Z-score para entrar
Z_STOP    = 3.5  # Z-score para stop (correlacao quebrou)

os.makedirs("C:/estrategia/data",    exist_ok=True)
os.makedirs("C:/estrategia/results", exist_ok=True)

# ─────────────────────────────────────────────
# 1. COLETA MT5 (XP) — dados diarios
# ─────────────────────────────────────────────
def collect_mt5_daily(symbols_map):
    print("\n[1/4] Coletando dados da XP (MT5)...")
    if not mt5.initialize(path=PATH_XP, timeout=15000):
        raise RuntimeError(f"MT5 falhou: {mt5.last_error()}")

    frames = {}
    for sym, name in symbols_map.items():
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_D1, DATE_FROM, DATE_TO)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
            df['time'] = pd.to_datetime(df['time'], unit='s').dt.date
            df = df.set_index('time')
            df.index = pd.DatetimeIndex(df.index)
            frames[name] = df['close']
            print(f"   OK  {sym:<10} {len(df):4d} dias | {df.index[0].date()} -> {df.index[-1].date()}")
        else:
            print(f"   ERRO {sym:<10} {mt5.last_error()}")

    mt5.shutdown()
    return pd.DataFrame(frames)

# ─────────────────────────────────────────────
# 2. COLETA YAHOO FINANCE — dados globais diarios
# ─────────────────────────────────────────────
def collect_yfinance():
    print("\n[2/4] Coletando dados globais (Yahoo Finance)...")
    tickers = {
        'BZ=F':      'brent',
        'CL=F':      'wti',
        '^GSPC':     'spx',
        '^TNX':      'us10y',
        'GC=F':      'gold',
        'AUDUSD=X':  'audusd',
        'USDMXN=X':  'usdmxn',
        'EURUSD=X':  'eurusd',
    }

    frames = {}
    for ticker, name in tickers.items():
        df = yf.download(ticker, start='2023-01-01', end='2026-04-26',
                         interval='1d', progress=False, auto_adjust=True)
        if len(df) > 0:
            close = df['Close'].squeeze()
            close.index = pd.DatetimeIndex(close.index.date)
            frames[name] = close
            print(f"   OK  {ticker:<12} {len(df):4d} dias | {df.index[0].date()} -> {df.index[-1].date()}")
        else:
            print(f"   ERRO {ticker}")

    return pd.DataFrame(frames)

# ─────────────────────────────────────────────
# 3. SINCRONIZACAO E LOG-RETURNS
# ─────────────────────────────────────────────
def build_returns(df_b3, df_global):
    print("\n[3/4] Sincronizando e calculando retornos...")
    df = df_b3.join(df_global, how='inner')
    df = df.dropna(how='all')

    print(f"   Periodo comum: {df.index[0].date()} -> {df.index[-1].date()} | {len(df)} dias")

    # Log-returns exceto US10Y (ja eh taxa, usamos diferenca)
    ret = pd.DataFrame(index=df.index)
    for col in df.columns:
        if col == 'us10y' or col.startswith('di'):
            ret[col] = df[col].diff()              # diferenca em pontos base
        else:
            ret[col] = np.log(df[col]).diff()      # log-retorno

    ret = ret.dropna()
    print(f"   Colunas: {list(ret.columns)}")
    print(f"   Linhas com retornos: {len(ret)}")
    return df, ret

# ─────────────────────────────────────────────
# 4. MODELO DE FATOR — Rolling OLS + Z-Score
# ─────────────────────────────────────────────
def run_factor_model(ret, target, features):
    print(f"\n[4/4] Rodando modelo para {target.upper()}...")

    sub = ret[[target] + features].dropna()
    n   = len(sub)
    results = []

    for i in range(ROLL_WIN, n):
        window = sub.iloc[i - ROLL_WIN:i]
        X = window[features].values
        y = window[target].values

        model = LinearRegression().fit(X, y)
        y_hat = model.predict(sub[features].iloc[[i]].values)[0]
        resid = sub[target].iloc[i] - y_hat
        results.append({
            'date':   sub.index[i],
            'actual': sub[target].iloc[i],
            'fair':   y_hat,
            'resid':  resid,
            'r2':     model.score(X, y),
        })

    df_res = pd.DataFrame(results).set_index('date')

    # Z-score dos residuos (rolling std)
    df_res['z_score'] = (
        df_res['resid'] - df_res['resid'].rolling(ROLL_WIN).mean()
    ) / df_res['resid'].rolling(ROLL_WIN).std()

    df_res['z_score'] = df_res['z_score'].fillna(0)
    return df_res

# ─────────────────────────────────────────────
# 5. BACKTEST DO SINAL Z-SCORE
# ─────────────────────────────────────────────
def backtest_zscore(df_res, ret_target, label):
    trades = []
    position = 0  # +1 long, -1 short, 0 flat
    entry_z  = None

    for date, row in df_res.iterrows():
        z = row['z_score']

        if position == 0:
            if z <= -Z_ENTRY:
                position = 1    # compra: ativo barato
                entry_z  = z
                entry_date = date
            elif z >= Z_ENTRY:
                position = -1   # vende: ativo caro
                entry_z  = z
                entry_date = date

        elif position != 0:
            # Stop: correlacao quebrou
            if abs(z) >= Z_STOP:
                trades.append({'date': date, 'dir': position, 'entry_z': entry_z,
                               'exit_z': z, 'result': 'STOP', 'pnl': -abs(entry_z)})
                position = 0

            # Saida: z voltou ao centro
            elif position == 1 and z >= -0.5:
                ret_val = ret_target.get(date, 0)
                trades.append({'date': date, 'dir': 1, 'entry_z': entry_z,
                               'exit_z': z, 'result': 'WIN' if ret_val > 0 else 'LOSS',
                               'pnl': ret_val * 100})
                position = 0

            elif position == -1 and z <= 0.5:
                ret_val = ret_target.get(date, 0)
                trades.append({'date': date, 'dir': -1, 'entry_z': entry_z,
                               'exit_z': z, 'result': 'WIN' if ret_val < 0 else 'LOSS',
                               'pnl': -ret_val * 100})
                position = 0

    if not trades:
        print(f"   Nenhuma trade gerada para {label}")
        return None

    df_t = pd.DataFrame(trades)
    wins  = len(df_t[df_t['result'] == 'WIN'])
    stops = len(df_t[df_t['result'] == 'STOP'])
    total = len(df_t)
    wr    = wins / total * 100

    print(f"\n   === BACKTEST: {label} ===")
    print(f"   Total de sinais : {total}")
    print(f"   Win Rate        : {wr:.1f}%")
    print(f"   Stops           : {stops} ({stops/total*100:.1f}%)")
    print(f"   Losses          : {total - wins - stops} ({(total-wins-stops)/total*100:.1f}%)")
    print(f"   PnL acumulado   : {df_t['pnl'].sum():.2f}% de retorno")
    print(f"   PnL medio/sinal : {df_t['pnl'].mean():.3f}%")

    df_t.to_csv(f"C:/estrategia/results/{label}_trades.csv", index=False)
    return df_t

# ─────────────────────────────────────────────
# 6. CORRELACOES ESTATICAS
# ─────────────────────────────────────────────
def print_correlations(ret):
    print("\n" + "="*60)
    print("MATRIZ DE CORRELACAO (retornos diarios 2023-2026)")
    print("="*60)

    targets = [c for c in ['win', 'wdo', 'petr4', 'di1'] if c in ret.columns]
    others  = [c for c in ret.columns if c not in targets]

    for t in targets:
        print(f"\n  {t.upper()} correlaciona com:")
        corrs = []
        for o in others:
            if o in ret.columns:
                c = ret[t].corr(ret[o])
                corrs.append((o, c))
        corrs.sort(key=lambda x: abs(x[1]), reverse=True)
        for name, c in corrs:
            bar = '#' * int(abs(c) * 20)
            sinal = '+' if c > 0 else '-'
            print(f"    {name:<12} {sinal}{abs(c):.3f}  {bar}")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    # Coleta dados
    df_b3 = collect_mt5_daily({
        'WIN$':  'win',
        'WDO$N': 'wdo',
        'PETR4': 'petr4',
        'DI1$N': 'di1',
    })

    df_global = collect_yfinance()

    # Sincroniza e calcula retornos
    df_prices, df_ret = build_returns(df_b3, df_global)

    # Salva dados brutos
    df_prices.to_csv("C:/estrategia/data/prices_diarios.csv")
    df_ret.to_csv("C:/estrategia/data/returns_diarios.csv")
    print("\n   Dados salvos em C:/estrategia/data/")

    # Correlacoes
    print_correlations(df_ret)

    # ── Modelo WIN ──────────────────────────────
    if all(c in df_ret.columns for c in ['win', 'spx', 'brent', 'petr4', 'di1', 'us10y']):
        res_win = run_factor_model(
            ret=df_ret,
            target='win',
            features=['spx', 'brent', 'petr4', 'di1', 'us10y']
        )
        res_win.to_csv("C:/estrategia/results/win_zscore.csv")

        print(f"\n   Z-Score WIN atual : {res_win['z_score'].iloc[-1]:.2f}")
        print(f"   R2 medio rolling  : {res_win['r2'].mean():.3f}")

        backtest_zscore(res_win, df_ret['win'], 'WIN')

    # ── Modelo WDO ──────────────────────────────
    if all(c in df_ret.columns for c in ['wdo', 'usdmxn', 'audusd', 'eurusd', 'us10y', 'di1']):
        res_wdo = run_factor_model(
            ret=df_ret,
            target='wdo',
            features=['usdmxn', 'audusd', 'eurusd', 'us10y', 'di1']
        )
        res_wdo.to_csv("C:/estrategia/results/wdo_zscore.csv")

        print(f"\n   Z-Score WDO atual : {res_wdo['z_score'].iloc[-1]:.2f}")
        print(f"   R2 medio rolling  : {res_wdo['r2'].mean():.3f}")

        backtest_zscore(res_wdo, df_ret['wdo'], 'WDO')

    print("\n\nResultados salvos em C:/estrategia/results/")
    print("Arquivos gerados:")
    for f in os.listdir("C:/estrategia/results"):
        print(f"  - {f}")
