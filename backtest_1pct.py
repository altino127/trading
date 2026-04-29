"""
Backtest — Mean Reversion 1%
  Se WIN subir >= 1% do open 09:00 -> VENDA
  Se WIN cair  >= 1% do open 09:00 -> COMPRA

Combinacoes testadas:
  Stop 150 / Gain 150
  Stop 150 / Gain 300
  Stop 200 / Gain 400
  Stop 400 / Gain 400
  Stop 400 / Gain 500

Janela: 09:00 - 16:30 BRT | Dados: xp_win_m1.csv
"""
import pandas as pd
import numpy as np
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RESULTS_DIR = "C:/estrategia/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

VALOR_PONTO = 0.20   # R$ por ponto por mini contrato
CONTRATOS   = 1
GATILHO_PCT = 0.01   # 1% do open

COMBINACOES = [
    (150, 150),
    (150, 300),
    (200, 400),
    (400, 400),
    (400, 500),
]

# ── Carrega dados ──────────────────────────────────────────────────────────────
print("Carregando WIN M1...")
df = pd.read_csv("C:/estrategia/data/xp_win_m1.csv", parse_dates=['time'])
df = df.set_index('time').sort_index()
df_sess = df.between_time('09:00', '16:30')
dias = sorted(set(df_sess.index.date))
print(f"  {len(dias)} dias de pregao | {dias[0]} -> {dias[-1]}\n")

# ── Motor de backtest ──────────────────────────────────────────────────────────
def backtest_dia(d, open_0900, direcao, gain_pts, stop_pts):
    """
    Retorna dict com resultado de um trade num dia, ou None se gatilho nao atingido.
    direcao: 'COMPRA' ou 'VENDA'
    """
    gatilho = open_0900 * (1 - GATILHO_PCT) if direcao == 'COMPRA' else open_0900 * (1 + GATILHO_PCT)
    gatilho = round(gatilho)

    # Primeiro candle que toca o gatilho
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

    # Varre candles apos entrada ate 16:30
    candles_after = d[(d.index > entry_candle)]

    resultado  = None
    exit_price = None
    exit_min   = None

    for idx, row in candles_after.iterrows():
        if direcao == 'COMPRA':
            if row['high'] >= tp:
                resultado  = 'GAIN'
                exit_price = tp
                exit_min   = (idx.hour - 9) * 60 + idx.minute
                break
            if row['low'] <= sl:
                resultado  = 'LOSS'
                exit_price = sl
                exit_min   = (idx.hour - 9) * 60 + idx.minute
                break
        else:
            if row['low'] <= tp:
                resultado  = 'GAIN'
                exit_price = tp
                exit_min   = (idx.hour - 9) * 60 + idx.minute
                break
            if row['high'] >= sl:
                resultado  = 'LOSS'
                exit_price = sl
                exit_min   = (idx.hour - 9) * 60 + idx.minute
                break

    # Saida forcada 10:30
    if resultado is None:
        ultimo = candles_after.iloc[-1] if len(candles_after) > 0 else None
        if ultimo is not None:
            exit_price = ultimo['close']
            exit_min   = (candles_after.index[-1].hour - 9) * 60 + candles_after.index[-1].minute
            pnl_pts    = (exit_price - entry_price) if direcao == 'COMPRA' else (entry_price - exit_price)
            resultado  = 'TIMEOUT'
        else:
            return None

    if resultado != 'TIMEOUT':
        pnl_pts = gain_pts if resultado == 'GAIN' else -stop_pts

    return {
        'date':        entry_candle.date(),
        'direcao':     direcao,
        'entry_min':   entry_min,
        'exit_min':    exit_min,
        'entry_price': entry_price,
        'exit_price':  exit_price,
        'resultado':   resultado,
        'pnl_pts':     pnl_pts,
        'pnl_brl':     pnl_pts * VALOR_PONTO * CONTRATOS,
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
print(f"{'Combo':<22} {'Trades':>6} {'WinRate':>8} {'PF':>6} {'P&L pts':>10} {'P&L R$':>10} {'MaxDD R$':>10}")
print("-" * 80)

resumo_geral = []

for stop_pts, gain_pts in COMBINACOES:
    df_trades = rodar_combinacao(stop_pts, gain_pts)

    if len(df_trades) == 0:
        print(f"  S{stop_pts}/G{gain_pts}: sem trades")
        continue

    n_total  = len(df_trades)
    n_gain   = (df_trades['resultado'] == 'GAIN').sum()
    n_loss   = (df_trades['resultado'] == 'LOSS').sum()
    winrate  = n_gain / n_total * 100
    pnl_pts  = df_trades['pnl_pts'].sum()
    pnl_brl  = df_trades['pnl_brl'].sum()

    gross_gain = df_trades.loc[df_trades['pnl_brl'] > 0, 'pnl_brl'].sum()
    gross_loss = abs(df_trades.loc[df_trades['pnl_brl'] < 0, 'pnl_brl'].sum())
    pf = gross_gain / gross_loss if gross_loss > 0 else float('inf')

    # Drawdown maximo
    equity = df_trades.sort_values('date')['pnl_brl'].cumsum()
    roll_max = equity.cummax()
    drawdown = (equity - roll_max)
    max_dd   = drawdown.min()

    combo = f"S{stop_pts}/G{gain_pts}"
    print(f"  {combo:<20} {n_total:>6} {winrate:>7.1f}% {pf:>6.2f} {pnl_pts:>10.0f} {pnl_brl:>10.2f} {max_dd:>10.2f}")

    # Salva CSV detalhado
    path = os.path.join(RESULTS_DIR, f"1pct_s{stop_pts}_g{gain_pts}.csv")
    df_trades.to_csv(path, index=False)

    resumo_geral.append({
        'stop': stop_pts, 'gain': gain_pts,
        'trades': n_total, 'gain_trades': n_gain, 'loss_trades': n_loss,
        'winrate_pct': round(winrate, 1),
        'profit_factor': round(pf, 2),
        'pnl_pts': round(pnl_pts, 0),
        'pnl_brl': round(pnl_brl, 2),
        'max_drawdown_brl': round(max_dd, 2),
    })

print("-" * 80)

# Salva resumo geral
df_resumo = pd.DataFrame(resumo_geral)
resumo_path = os.path.join(RESULTS_DIR, "1pct_resumo.csv")
df_resumo.to_csv(resumo_path, index=False)
print(f"\nResumo salvo em: {resumo_path}")
print("CSVs detalhados salvos em: C:/estrategia/results/1pct_*.csv")

# ── Detalhes por direcao ───────────────────────────────────────────────────────
print("\n\n=== DETALHES POR DIRECAO ===\n")
print(f"{'Combo':<22} {'Dir':>6} {'Trades':>6} {'WinRate':>8} {'P&L R$':>10}")
print("-" * 60)

for stop_pts, gain_pts in COMBINACOES:
    path = os.path.join(RESULTS_DIR, f"1pct_s{stop_pts}_g{gain_pts}.csv")
    if not os.path.exists(path):
        continue
    df_t = pd.read_csv(path)
    combo = f"S{stop_pts}/G{gain_pts}"
    for direcao in ('COMPRA', 'VENDA'):
        sub = df_t[df_t['direcao'] == direcao]
        if len(sub) == 0:
            continue
        wr  = (sub['resultado'] == 'GAIN').mean() * 100
        pnl = sub['pnl_brl'].sum()
        print(f"  {combo:<20} {direcao:>6} {len(sub):>6} {wr:>7.1f}% {pnl:>10.2f}")

print()
