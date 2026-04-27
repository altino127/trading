"""
Backtest — VENDA quando WIN sobe >= 500 pts do open (09:00-10:30)
Testa combinacoes de gain e stop em pontos
WIN mini: 1 ponto = R$ 0.20 por contrato
"""
import pandas as pd
import numpy as np
from scipy import stats
from itertools import product
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RESULTS_DIR = "C:/estrategia/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

VALOR_PONTO  = 0.20   # R$ por ponto por mini contrato
CONTRATOS    = 1
NIVEL_ENTRADA = 500   # WIN sobe 500 pts do open -> VENDA

# ── Carrega dados M1 ───────────────────────────────────────────
print("Carregando WIN M1...")
df = pd.read_csv("C:/estrategia/data/xp_win_m1.csv", parse_dates=['time'])
df = df.set_index('time').sort_index()
df_win = df.between_time('09:00','10:35')
dias = sorted(set(df_win.index.date))
print(f"  {len(dias)} dias de pregao\n")

# ── Funcao de backtest ─────────────────────────────────────────
def backtest(nivel, gain_pts, stop_pts, direcao='VENDA'):
    trades = []

    for dia in dias:
        d = df_win[df_win.index.date == dia].copy()

        c0900 = d.between_time('09:00','09:00')
        c1030 = d.between_time('10:29','10:35')
        if len(c0900) == 0 or len(c1030) == 0:
            continue

        open_0900  = c0900['open'].iloc[0]
        close_1030 = c1030['close'].iloc[-1]
        preco_alvo = open_0900 + nivel  # nivel > 0 = subida, < 0 = queda

        # Verifica se preco tocou o nivel de entrada
        if nivel > 0:
            toque = d[d['high'] >= preco_alvo]
        else:
            toque = d[d['low']  <= preco_alvo]

        if len(toque) == 0:
            continue

        # Candle de entrada = primeiro toque
        entry_candle = toque.index[0]
        entry_price  = preco_alvo
        entry_min    = (entry_candle.hour - 9) * 60 + entry_candle.minute

        # Define TP e SL conforme direcao
        if direcao == 'VENDA':
            tp = entry_price - gain_pts
            sl = entry_price + stop_pts
        else:  # COMPRA
            tp = entry_price + gain_pts
            sl = entry_price - stop_pts

        # Varre candles apos a entrada ate 10:30
        candles_after = d[d.index > entry_candle]
        candles_after = candles_after[candles_after.index.time <= pd.Timestamp('10:30').time()]

        resultado  = None
        exit_price = None
        exit_min   = None

        for idx, row in candles_after.iterrows():
            min_atual = (idx.hour - 9) * 60 + idx.minute

            if direcao == 'VENDA':
                if row['low']  <= tp:
                    resultado  = 'GAIN'
                    exit_price = tp
                    exit_min   = min_atual
                    break
                if row['high'] >= sl:
                    resultado  = 'LOSS'
                    exit_price = sl
                    exit_min   = min_atual
                    break
            else:
                if row['high'] >= tp:
                    resultado  = 'GAIN'
                    exit_price = tp
                    exit_min   = min_atual
                    break
                if row['low']  <= sl:
                    resultado  = 'LOSS'
                    exit_price = sl
                    exit_min   = min_atual
                    break

        # Saida forcada no fechamento 10:30
        if resultado is None:
            exit_price = close_1030
            exit_min   = 90
            pnl_pts    = (entry_price - exit_price) if direcao=='VENDA' else (exit_price - entry_price)
            resultado  = 'EXPIRADO'
        else:
            pnl_pts = gain_pts if resultado == 'GAIN' else -stop_pts

        pnl_brl = pnl_pts * VALOR_PONTO * CONTRATOS

        trades.append({
            'date':       dia,
            'dow':        pd.Timestamp(dia).dayofweek,
            'entry_min':  entry_min,
            'exit_min':   exit_min,
            'entry':      entry_price,
            'exit':       exit_price,
            'resultado':  resultado,
            'pnl_pts':    pnl_pts,
            'pnl_brl':    pnl_brl,
        })

    return pd.DataFrame(trades)

# ── Grid search: todas as combinacoes de gain x stop ──────────
GAINS = [50, 100, 150, 200, 250, 300, 400, 500]
STOPS = [50, 100, 150, 200, 250, 300, 400, 500]

print("="*75)
print(f"GRID SEARCH — VENDA em +{NIVEL_ENTRADA} pts do open")
print("Resultado por combinacao de GAIN x STOP (1 mini contrato)")
print("="*75)
print(f"\n  {'GAIN':>6}  {'STOP':>6}  {'N':>5}  {'WR%':>7}  {'PF':>6}  "
      f"{'P&L Total':>11}  {'P&L/op':>9}  {'MaxDD':>9}  {'Consec-':>9}  Sig")
print(f"  {'-'*85}")

grid_results = []

for gain, stop in product(GAINS, STOPS):
    df_t = backtest(NIVEL_ENTRADA, gain, stop, 'VENDA')
    if len(df_t) < 20:
        continue

    wins   = df_t[df_t['resultado'] == 'GAIN']
    losses = df_t[df_t['resultado'] == 'LOSS']
    exp    = df_t[df_t['resultado'] == 'EXPIRADO']

    n      = len(df_t)
    wr     = len(wins) / n * 100
    gross_w = wins['pnl_brl'].sum()
    gross_l = abs(losses['pnl_brl'].sum()) + abs(exp[exp['pnl_brl']<0]['pnl_brl'].sum())
    pf     = gross_w / gross_l if gross_l > 0 else 99
    total  = df_t['pnl_brl'].sum()
    per_op = df_t['pnl_brl'].mean()

    # Drawdown maximo
    equity = df_t['pnl_brl'].cumsum()
    dd     = (equity - equity.cummax()).min()

    # Sequencia maxima de perdas
    streak = 0; max_streak = 0; cur = 0
    for r in df_t['resultado']:
        if r != 'GAIN':
            cur += 1; max_streak = max(max_streak, cur)
        else:
            cur = 0

    # Significancia
    _, p = stats.ttest_1samp(df_t['pnl_brl'], 0)
    sig  = "***" if p<0.01 else "** " if p<0.05 else "*  " if p<0.1 else "   "

    destaque = " <" if total > 0 and pf > 1.3 and wr > 52 else ""

    print(f"  {gain:>6}  {stop:>6}  {n:>5}  {wr:>6.1f}%  {pf:>6.2f}  "
          f"R${total:>9,.0f}  R${per_op:>7,.1f}  R${dd:>7,.0f}  {max_streak:>9}  {sig}{destaque}")

    grid_results.append({
        'gain': gain, 'stop': stop, 'n': n, 'wr': wr, 'pf': pf,
        'total_brl': total, 'per_op': per_op, 'max_dd': dd,
        'max_streak_loss': max_streak, 'pval': p
    })

df_grid = pd.DataFrame(grid_results)

# ── Top 5 combinacoes por resultado total ──────────────────────
print("\n" + "="*75)
print("TOP 5 COMBINACOES POR RESULTADO TOTAL")
print("="*75)
top5 = df_grid[df_grid['total_brl'] > 0].nlargest(5, 'total_brl')
for _, r in top5.iterrows():
    print(f"  GAIN={r['gain']:>4}  STOP={r['stop']:>4}  |  "
          f"N={r['n']:>3}  WR={r['wr']:.1f}%  PF={r['pf']:.2f}  "
          f"Total=R${r['total_brl']:>8,.0f}  MaxDD=R${r['max_dd']:>7,.0f}")

# ── Backtest detalhado da melhor combinacao ────────────────────
if len(top5) > 0:
    best = top5.iloc[0]
    g_best = int(best['gain'])
    s_best = int(best['stop'])
    print(f"\n{'='*75}")
    print(f"BACKTEST DETALHADO — GAIN={g_best}pts  STOP={s_best}pts")
    print(f"{'='*75}")

    df_best = backtest(NIVEL_ENTRADA, g_best, s_best, 'VENDA')
    df_best['equity'] = df_best['pnl_brl'].cumsum()

    # Por ano
    df_best['ano'] = pd.DatetimeIndex(df_best['date']).year
    print(f"\n  Por ano:")
    print(f"  {'Ano':>5}  {'N':>5}  {'WR%':>7}  {'P&L':>12}  {'MaxDD':>10}")
    for ano, g in df_best.groupby('ano'):
        wr_a = (g['resultado']=='GAIN').mean()*100
        tot  = g['pnl_brl'].sum()
        eq_a = g['pnl_brl'].cumsum()
        dd_a = (eq_a - eq_a.cummax()).min()
        print(f"  {ano:>5}  {len(g):>5}  {wr_a:>6.1f}%  R${tot:>9,.0f}  R${dd_a:>8,.0f}")

    # Por dia da semana
    print(f"\n  Por dia da semana:")
    print(f"  {'Dia':>5}  {'N':>5}  {'WR%':>7}  {'P&L':>12}")
    DIAS = ['Seg','Ter','Qua','Qui','Sex']
    for dow, nome in enumerate(DIAS):
        g = df_best[df_best['dow']==dow]
        if len(g) < 5: continue
        wr_d = (g['resultado']=='GAIN').mean()*100
        tot  = g['pnl_brl'].sum()
        print(f"  {nome:>5}  {len(g):>5}  {wr_d:>6.1f}%  R${tot:>9,.0f}")

    # Por horario de entrada
    print(f"\n  Por horario de entrada:")
    print(f"  {'Minuto':>7}  {'Hora':>6}  {'N':>5}  {'WR%':>7}  {'P&L medio':>12}")
    for faixa, faixa2, label in [(0,20,'09:00-09:20'),(20,40,'09:20-09:40'),(40,60,'09:40-10:00'),(60,90,'10:00-10:30')]:
        g = df_best[(df_best['entry_min']>=faixa) & (df_best['entry_min']<faixa2)]
        if len(g) < 5: continue
        wr_h = (g['resultado']=='GAIN').mean()*100
        med  = g['pnl_brl'].mean()
        print(f"  {label:>10}  {len(g):>5}  {wr_h:>6.1f}%  R${med:>9,.1f}")

    # Estatisticas finais
    n     = len(df_best)
    wr    = (df_best['resultado']=='GAIN').mean()*100
    total = df_best['pnl_brl'].sum()
    eq    = df_best['pnl_brl'].cumsum()
    dd    = (eq - eq.cummax()).min()
    pf    = df_best[df_best['pnl_brl']>0]['pnl_brl'].sum() / abs(df_best[df_best['pnl_brl']<0]['pnl_brl'].sum())

    print(f"\n  RESUMO FINAL:")
    print(f"  Operacoes    : {n}")
    print(f"  Win Rate     : {wr:.1f}%")
    print(f"  Profit Factor: {pf:.2f}")
    print(f"  P&L Total    : R$ {total:,.2f} (1 mini contrato)")
    print(f"  P&L Total    : R$ {total*10:,.2f} (10 mini contratos)")
    print(f"  Max Drawdown : R$ {dd:,.2f}")
    print(f"  P&L medio/op : R$ {df_best['pnl_brl'].mean():.2f}")

    df_best.to_csv(f"{RESULTS_DIR}/backtest_venda_500.csv", index=False)
    print(f"\n  Trades salvos: {RESULTS_DIR}/backtest_venda_500.csv")
