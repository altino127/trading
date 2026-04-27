"""
Detalhamento COMPRA -500 pts:
  - Setup A: GAIN=200 / STOP=500
  - Setup B: GAIN=500 / STOP=500
Analise: geral, por ano, ultimos 60 dias, trade a trade
"""
import pandas as pd
import numpy as np
from scipy import stats
import sys, os, warnings
from datetime import date, timedelta
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RESULTS_DIR = "C:/estrategia/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

VALOR_PONTO   = 0.20
CONTRATOS     = 1
NIVEL_ENTRADA = -500

print("Carregando WIN M1...")
df = pd.read_csv("C:/estrategia/data/xp_win_m1.csv", parse_dates=['time'])
df = df.set_index('time').sort_index()
df_win = df.between_time('09:00','10:35')
dias = sorted(set(df_win.index.date))
print(f"  {len(dias)} dias de pregao | {dias[0]} -> {dias[-1]}\n")

DATA_CORTE_60 = date(2026, 4, 26) - timedelta(days=60)  # ~2026-02-25
DATA_2025_INI = date(2025, 1, 1)
DATA_2025_FIM = date(2025, 12, 31)

# ── Funcao de backtest ─────────────────────────────────────────
def backtest(nivel, gain_pts, stop_pts):
    trades = []
    for dia in dias:
        d = df_win[df_win.index.date == dia].copy()
        c0900 = d.between_time('09:00','09:00')
        c1030 = d.between_time('10:29','10:35')
        if len(c0900) == 0 or len(c1030) == 0:
            continue

        open_0900  = c0900['open'].iloc[0]
        close_1030 = c1030['close'].iloc[-1]
        preco_alvo = open_0900 + nivel

        toque = d[d['low'] <= preco_alvo]
        if len(toque) == 0:
            continue

        entry_candle = toque.index[0]
        entry_price  = preco_alvo
        entry_min    = (entry_candle.hour - 9) * 60 + entry_candle.minute

        tp = entry_price + gain_pts
        sl = entry_price - stop_pts

        candles_after = d[d.index > entry_candle]
        candles_after = candles_after[candles_after.index.time <= pd.Timestamp('10:30').time()]

        resultado  = None
        exit_price = None
        exit_min   = None

        for idx, row in candles_after.iterrows():
            min_atual = (idx.hour - 9) * 60 + idx.minute
            if row['high'] >= tp:
                resultado = 'GAIN'; exit_price = tp; exit_min = min_atual; break
            if row['low'] <= sl:
                resultado = 'LOSS'; exit_price = sl; exit_min = min_atual; break

        if resultado is None:
            exit_price = close_1030
            exit_min   = 90
            pnl_pts    = exit_price - entry_price
            resultado  = 'EXPIRADO'
        else:
            pnl_pts = gain_pts if resultado == 'GAIN' else -stop_pts

        pnl_brl = pnl_pts * VALOR_PONTO * CONTRATOS

        trades.append({
            'date':      dia,
            'ano':       dia.year,
            'dow':       pd.Timestamp(dia).dayofweek,
            'entry_min': entry_min,
            'exit_min':  exit_min,
            'entry':     entry_price,
            'open_0900': open_0900,
            'exit':      exit_price,
            'resultado': resultado,
            'pnl_pts':   pnl_pts,
            'pnl_brl':   pnl_brl,
        })

    return pd.DataFrame(trades)

# ── Funcao de relatorio ────────────────────────────────────────
def relatorio(df_t, titulo):
    n     = len(df_t)
    if n == 0:
        print(f"  Sem trades no periodo.")
        return

    wr    = (df_t['resultado']=='GAIN').mean()*100
    total = df_t['pnl_brl'].sum()
    eq    = df_t['pnl_brl'].cumsum()
    dd    = (eq - eq.cummax()).min()
    gw    = df_t[df_t['pnl_brl']>0]['pnl_brl'].sum()
    gl    = abs(df_t[df_t['pnl_brl']<0]['pnl_brl'].sum())
    pf    = gw / gl if gl > 0 else 99
    med   = df_t['pnl_brl'].mean()

    # Max sequencia de perdas
    cur = ms = 0
    for r in df_t['resultado']:
        cur = cur+1 if r != 'GAIN' else 0
        ms  = max(ms, cur)

    _, pval = stats.ttest_1samp(df_t['pnl_brl'], 0)
    sig = "***" if pval<0.01 else "**" if pval<0.05 else "*" if pval<0.1 else "n.s."

    print(f"\n  {titulo}")
    print(f"  {'='*55}")
    print(f"  Operacoes    : {n}")
    print(f"  Win Rate     : {wr:.1f}%  (breakevent: {100*1/(1+gain/stop):.1f}%)")
    print(f"  Profit Factor: {pf:.2f}")
    print(f"  P&L Total    : R$ {total:,.2f} (1 mini) | R$ {total*10:,.2f} (10 minis)")
    print(f"  Max Drawdown : R$ {dd:,.2f}")
    print(f"  P&L medio/op : R$ {med:.2f}")
    print(f"  Max seq perd : {ms} trades")
    print(f"  Significancia: {sig} (p={pval:.4f})")

    # Por resultado
    g_cnt = (df_t['resultado']=='GAIN').sum()
    l_cnt = (df_t['resultado']=='LOSS').sum()
    e_cnt = (df_t['resultado']=='EXPIRADO').sum()
    print(f"\n  Resultado    : GAIN={g_cnt} ({g_cnt/n*100:.1f}%)  "
          f"LOSS={l_cnt} ({l_cnt/n*100:.1f}%)  "
          f"EXP={e_cnt} ({e_cnt/n*100:.1f}%)")

def analise_por_semana(df_t):
    DIAS = ['Seg','Ter','Qua','Qui','Sex']
    print(f"\n  Por dia da semana:")
    print(f"  {'Dia':>5}  {'N':>5}  {'WR%':>7}  {'P&L':>10}  {'P&L/op':>9}")
    for dow, nome in enumerate(DIAS):
        g = df_t[df_t['dow']==dow]
        if len(g) < 3: continue
        wr_d = (g['resultado']=='GAIN').mean()*100
        tot  = g['pnl_brl'].sum()
        med  = g['pnl_brl'].mean()
        print(f"  {nome:>5}  {len(g):>5}  {wr_d:>6.1f}%  R${tot:>8,.0f}  R${med:>7,.1f}")

def analise_por_horario(df_t):
    print(f"\n  Por horario de entrada:")
    print(f"  {'Faixa':>12}  {'N':>5}  {'WR%':>7}  {'P&L/op':>9}")
    for faixa, faixa2, label in [(0,20,'09:00-09:20'),(20,40,'09:20-09:40'),
                                   (40,60,'09:40-10:00'),(60,90,'10:00-10:30')]:
        g = df_t[(df_t['entry_min']>=faixa) & (df_t['entry_min']<faixa2)]
        if len(g) < 3: continue
        wr_h = (g['resultado']=='GAIN').mean()*100
        med  = g['pnl_brl'].mean()
        print(f"  {label:>12}  {len(g):>5}  {wr_h:>6.1f}%  R${med:>7,.1f}")

def analise_por_ano(df_t):
    print(f"\n  Por ano:")
    print(f"  {'Ano':>5}  {'N':>5}  {'WR%':>7}  {'P&L':>10}  {'MaxDD':>10}  {'P&L/op':>9}")
    for ano, g in df_t.groupby('ano'):
        wr_a = (g['resultado']=='GAIN').mean()*100
        tot  = g['pnl_brl'].sum()
        eq_a = g['pnl_brl'].cumsum()
        dd_a = (eq_a - eq_a.cummax()).min()
        med  = g['pnl_brl'].mean()
        print(f"  {ano:>5}  {len(g):>5}  {wr_a:>6.1f}%  R${tot:>8,.0f}  R${dd_a:>8,.0f}  R${med:>7,.1f}")

def trades_detalhados(df_t, titulo):
    print(f"\n  Trades — {titulo}")
    print(f"  {'Data':>12}  {'Dia':>4}  {'EntMin':>7}  {'Entry':>8}  {'Exit':>8}  "
          f"{'Result':>9}  {'PnL pts':>9}  {'PnL R$':>9}  {'Equity':>10}")
    print(f"  {'-'*96}")
    DIAS = ['Seg','Ter','Qua','Qui','Sex','Sab','Dom']
    equity = 0
    for _, r in df_t.iterrows():
        equity += r['pnl_brl']
        dia_nome = DIAS[r['dow']]
        h = 9 + int(r['entry_min']) // 60
        mi = int(r['entry_min']) % 60
        print(f"  {str(r['date']):>12}  {dia_nome:>4}  "
              f"{h:02d}:{mi:02d}    "
              f"{r['entry']:>8.0f}  {r['exit']:>8.0f}  "
              f"{r['resultado']:>9}  {r['pnl_pts']:>+9.0f}  "
              f"R${r['pnl_brl']:>7,.2f}  R${equity:>8,.2f}")

# ══════════════════════════════════════════════════════════════
# SETUP A: GAIN=200 / STOP=500
# ══════════════════════════════════════════════════════════════
gain, stop = 200, 500
print("\n" + "#"*75)
print(f"# SETUP A — COMPRA -500 pts  |  GAIN={gain}pts  STOP={stop}pts")
print("#"*75)

df_A = backtest(NIVEL_ENTRADA, gain, stop)
df_A['date'] = pd.to_datetime(df_A['date']).dt.date

# Geral
relatorio(df_A, f"GERAL — {len(df_A)} trades")
analise_por_ano(df_A)
analise_por_semana(df_A)
analise_por_horario(df_A)

# 2025
df_A_2025 = df_A[(df_A['date'] >= DATA_2025_INI) & (df_A['date'] <= DATA_2025_FIM)]
print(f"\n{'='*75}")
print(f"SETUP A — ANO 2025")
print(f"{'='*75}")
relatorio(df_A_2025, f"2025 — {len(df_A_2025)} trades")
analise_por_semana(df_A_2025)
analise_por_horario(df_A_2025)
trades_detalhados(df_A_2025, "2025")

# Ultimos 60 dias
df_A_60 = df_A[df_A['date'] >= DATA_CORTE_60]
print(f"\n{'='*75}")
print(f"SETUP A — ULTIMOS 60 DIAS (a partir de {DATA_CORTE_60})")
print(f"{'='*75}")
relatorio(df_A_60, f"60 dias — {len(df_A_60)} trades")
analise_por_semana(df_A_60)
analise_por_horario(df_A_60)
trades_detalhados(df_A_60, "ultimos 60 dias")

df_A.to_csv(f"{RESULTS_DIR}/backtest_compra_200g_500s.csv", index=False)

# ══════════════════════════════════════════════════════════════
# SETUP B: GAIN=500 / STOP=500
# ══════════════════════════════════════════════════════════════
gain, stop = 500, 500
print("\n\n" + "#"*75)
print(f"# SETUP B — COMPRA -500 pts  |  GAIN={gain}pts  STOP={stop}pts")
print("#"*75)

df_B = backtest(NIVEL_ENTRADA, gain, stop)
df_B['date'] = pd.to_datetime(df_B['date']).dt.date

# Geral
relatorio(df_B, f"GERAL — {len(df_B)} trades")
analise_por_ano(df_B)
analise_por_semana(df_B)
analise_por_horario(df_B)

# 2025
df_B_2025 = df_B[(df_B['date'] >= DATA_2025_INI) & (df_B['date'] <= DATA_2025_FIM)]
print(f"\n{'='*75}")
print(f"SETUP B — ANO 2025")
print(f"{'='*75}")
relatorio(df_B_2025, f"2025 — {len(df_B_2025)} trades")
analise_por_semana(df_B_2025)
analise_por_horario(df_B_2025)
trades_detalhados(df_B_2025, "2025")

# Ultimos 60 dias
df_B_60 = df_B[df_B['date'] >= DATA_CORTE_60]
print(f"\n{'='*75}")
print(f"SETUP B — ULTIMOS 60 DIAS (a partir de {DATA_CORTE_60})")
print(f"{'='*75}")
relatorio(df_B_60, f"60 dias — {len(df_B_60)} trades")
analise_por_semana(df_B_60)
analise_por_horario(df_B_60)
trades_detalhados(df_B_60, "ultimos 60 dias")

df_B.to_csv(f"{RESULTS_DIR}/backtest_compra_500g_500s.csv", index=False)

print(f"\n\nArquivos salvos em {RESULTS_DIR}/")
