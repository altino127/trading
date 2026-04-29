"""
Backtest WDO — Mean Reversion 1.00%
  Se WDO cair  >= 1.00% do open 09:00 -> COMPRA
  Se WDO subir >= 1.00% do open 09:00 -> VENDA

Combinacoes:
  Stop  5 / Gain  5
  Stop  5 / Gain 10
  Stop  7 / Gain  7
  Stop  7 / Gain 10
  Stop 10 / Gain 10
  Stop 10 / Gain  5

Janela: 09:00 - 16:30 BRT | Dados: xp_wdo_m1.csv
WDO mini: 1 ponto = R$ 10,00 por contrato
"""
import pandas as pd
import numpy as np
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RESULTS_DIR  = "C:/estrategia/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

VALOR_PONTO  = 10.0   # R$ por ponto por mini contrato WDO
CONTRATOS    = 1
GATILHO_PCT  = 0.01   # 1.00%

COMBINACOES = [
    ( 5,  5),
    ( 5, 10),
    ( 7,  7),
    ( 7, 10),
    (10, 10),
    (10,  5),
]

# ── Carrega dados ──────────────────────────────────────────────────────────────
print("Carregando WDO M1...")
df = pd.read_csv("C:/estrategia/data/xp_wdo_m1.csv", parse_dates=['time'])
df = df.set_index('time').sort_index()
df_sess = df.between_time('09:00', '16:30')
dias = sorted(set(df_sess.index.date))
print(f"  {len(dias)} dias de pregao | {dias[0]} -> {dias[-1]}\n")

# ── Motor de backtest ──────────────────────────────────────────────────────────
def backtest_dia(d, open_0900, direcao, gain_pts, stop_pts):
    gatilho = open_0900 * (1 - GATILHO_PCT) if direcao == 'COMPRA' else open_0900 * (1 + GATILHO_PCT)

    if direcao == 'COMPRA':
        toque = d[d['low'] <= gatilho]
    else:
        toque = d[d['high'] >= gatilho]

    if len(toque) == 0:
        return None

    entry_candle = toque.index[0]
    entry_price  = gatilho
    entry_min    = (entry_candle.hour - 9) * 60 + entry_candle.minute

    if direcao == 'COMPRA':
        tp = entry_price + gain_pts
        sl = entry_price - stop_pts
    else:
        tp = entry_price - gain_pts
        sl = entry_price + stop_pts

    candles_after = d[d.index > entry_candle]

    resultado  = None
    exit_price = None
    exit_min   = None

    for idx, row in candles_after.iterrows():
        if direcao == 'COMPRA':
            if row['high'] >= tp:
                resultado = 'GAIN'; exit_price = tp
                exit_min  = (idx.hour - 9) * 60 + idx.minute; break
            if row['low'] <= sl:
                resultado = 'LOSS'; exit_price = sl
                exit_min  = (idx.hour - 9) * 60 + idx.minute; break
        else:
            if row['low'] <= tp:
                resultado = 'GAIN'; exit_price = tp
                exit_min  = (idx.hour - 9) * 60 + idx.minute; break
            if row['high'] >= sl:
                resultado = 'LOSS'; exit_price = sl
                exit_min  = (idx.hour - 9) * 60 + idx.minute; break

    # Saida forcada 10:30
    if resultado is None:
        if len(candles_after) == 0:
            return None
        ultimo     = candles_after.iloc[-1]
        exit_price = ultimo['close']
        exit_min   = (candles_after.index[-1].hour - 9) * 60 + candles_after.index[-1].minute
        pnl_pts    = (exit_price - entry_price) if direcao == 'COMPRA' else (entry_price - exit_price)
        resultado  = 'TIMEOUT'
    else:
        pnl_pts = gain_pts if resultado == 'GAIN' else -stop_pts

    return {
        'date':        entry_candle.date(),
        'direcao':     direcao,
        'entry_min':   entry_min,
        'exit_min':    exit_min,
        'entry_price': round(entry_price, 1),
        'exit_price':  round(exit_price,  1),
        'resultado':   resultado,
        'pnl_pts':     round(pnl_pts, 1),
        'pnl_brl':     round(pnl_pts * VALOR_PONTO * CONTRATOS, 2),
    }


def rodar_combinacao(stop_pts, gain_pts):
    trades = []
    for dia in dias:
        d = df_sess[df_sess.index.date == dia].copy()
        c0900 = d.between_time('09:00', '09:00')
        if len(c0900) == 0:
            continue
        open_0900 = c0900['open'].iloc[0]
        for direcao in ('COMPRA', 'VENDA'):
            t = backtest_dia(d, open_0900, direcao, gain_pts, stop_pts)
            if t:
                trades.append(t)
    return pd.DataFrame(trades)


# ── Roda todas as combinacoes ──────────────────────────────────────────────────
print(f"{'Combo':<20} {'Trades':>6} {'WinRate':>8} {'PF':>6} {'P&L pts':>9} {'P&L R$':>10} {'MaxDD R$':>10}")
print("-" * 75)

resumo = []

for stop_pts, gain_pts in COMBINACOES:
    df_t = rodar_combinacao(stop_pts, gain_pts)

    if len(df_t) == 0:
        print(f"  S{stop_pts}/G{gain_pts}: sem trades")
        continue

    n_total = len(df_t)
    n_gain  = (df_t['resultado'] == 'GAIN').sum()
    winrate = n_gain / n_total * 100
    pnl_pts = df_t['pnl_pts'].sum()
    pnl_brl = df_t['pnl_brl'].sum()

    gg = df_t.loc[df_t['pnl_brl'] > 0, 'pnl_brl'].sum()
    gl = abs(df_t.loc[df_t['pnl_brl'] < 0, 'pnl_brl'].sum())
    pf = gg / gl if gl > 0 else float('inf')

    equity = df_t.sort_values('date')['pnl_brl'].cumsum()
    max_dd = (equity - equity.cummax()).min()

    combo = f"S{stop_pts}/G{gain_pts}"
    print(f"  {combo:<18} {n_total:>6} {winrate:>7.1f}% {pf:>6.2f} {pnl_pts:>9.1f} {pnl_brl:>10.2f} {max_dd:>10.2f}")

    path = os.path.join(RESULTS_DIR, f"wdo_1pct_s{stop_pts}_g{gain_pts}.csv")
    df_t.to_csv(path, index=False)

    resumo.append({
        'stop': stop_pts, 'gain': gain_pts, 'trades': n_total,
        'winrate_pct': round(winrate, 1), 'profit_factor': round(pf, 2),
        'pnl_pts': round(pnl_pts, 1), 'pnl_brl': round(pnl_brl, 2),
        'max_drawdown_brl': round(max_dd, 2),
    })

print("-" * 75)

pd.DataFrame(resumo).to_csv(os.path.join(RESULTS_DIR, "wdo_1pct_resumo.csv"), index=False)

# ── Detalhes por direcao ───────────────────────────────────────────────────────
print("\n=== DETALHES POR DIRECAO ===\n")
print(f"{'Combo':<20} {'Dir':>6} {'Trades':>6} {'WinRate':>8} {'P&L R$':>10} {'MaxDD R$':>10}")
print("-" * 65)

for stop_pts, gain_pts in COMBINACOES:
    path = os.path.join(RESULTS_DIR, f"wdo_1pct_s{stop_pts}_g{gain_pts}.csv")
    if not os.path.exists(path):
        continue
    df_t  = pd.read_csv(path)
    combo = f"S{stop_pts}/G{gain_pts}"
    for direcao in ('COMPRA', 'VENDA'):
        sub = df_t[df_t['direcao'] == direcao]
        if len(sub) == 0:
            continue
        wr   = (sub['resultado'] == 'GAIN').mean() * 100
        pnl  = sub['pnl_brl'].sum()
        eq   = sub.sort_values('date')['pnl_brl'].cumsum()
        dd   = (eq - eq.cummax()).min()
        print(f"  {combo:<18} {direcao:>6} {len(sub):>6} {wr:>7.1f}% {pnl:>10.2f} {dd:>10.2f}")

print()
