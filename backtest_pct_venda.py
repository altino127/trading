"""
Backtest — VENDA quando WIN sobe OU cai 0.50% do open (09:00-10:30)
Direcao VENDA em ambos os casos:
  - ALTA  0.50%: WIN subiu 0.50% do open -> VENDA (reversao da alta)
  - QUEDA 0.50%: WIN caiu  0.50% do open -> VENDA (seguindo a queda)
Testa 5 combinacoes especificas de GAIN x STOP
"""
import pandas as pd
import numpy as np
from scipy import stats
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RESULTS_DIR = "C:/estrategia/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

VALOR_PONTO = 0.20
CONTRATOS   = 1
PCT         = 0.005   # 0.50%

print("Carregando WIN M1...")
df = pd.read_csv("C:/estrategia/data/xp_win_m1.csv", parse_dates=['time'])
df = df.set_index('time').sort_index()
df_win = df.between_time('09:00','10:35')
dias = sorted(set(df_win.index.date))
print(f"  {len(dias)} dias de pregao | {dias[0]} -> {dias[-1]}\n")

SETUPS = [
    (150, 150),
    (300, 150),   # gain, stop  (usuario disse stop 150 gain 300)
    (400, 200),
    (400, 400),
    (500, 500),
]

DIAS_SEMANA = ['Seg','Ter','Qua','Qui','Sex']

# ── Funcao de backtest VENDA ───────────────────────────────────
def backtest_venda_pct(pct, gain_pts, stop_pts, direcao_gatilho):
    """
    direcao_gatilho:
      'ALTA'  = WIN subiu pct do open -> entra VENDENDO
      'QUEDA' = WIN caiu  pct do open -> entra VENDENDO
    VENDA: TP abaixo da entrada, SL acima
    """
    trades = []

    for dia in dias:
        d = df_win[df_win.index.date == dia].copy()

        c0900 = d.between_time('09:00','09:00')
        c1030 = d.between_time('10:29','10:35')
        if len(c0900) == 0 or len(c1030) == 0:
            continue

        open_0900  = c0900['open'].iloc[0]
        close_1030 = c1030['close'].iloc[-1]

        if direcao_gatilho == 'ALTA':
            nivel = open_0900 * (1 + pct)
            toque = d[d['high'] >= nivel]
        else:
            nivel = open_0900 * (1 - pct)
            toque = d[d['low']  <= nivel]

        if len(toque) == 0:
            continue

        entry_candle = toque.index[0]
        entry_price  = nivel
        entry_min    = (entry_candle.hour - 9) * 60 + entry_candle.minute
        var_pts      = round(nivel - open_0900)

        # VENDA: TP abaixo, SL acima
        tp = entry_price - gain_pts
        sl = entry_price + stop_pts

        candles_after = d[d.index > entry_candle]
        candles_after = candles_after[candles_after.index.time <= pd.Timestamp('10:30').time()]

        resultado  = None
        exit_price = None
        exit_min   = None

        for idx, row in candles_after.iterrows():
            min_atual = (idx.hour - 9) * 60 + idx.minute
            if row['low']  <= tp:
                resultado = 'GAIN'; exit_price = tp; exit_min = min_atual; break
            if row['high'] >= sl:
                resultado = 'LOSS'; exit_price = sl; exit_min = min_atual; break

        if resultado is None:
            exit_price = close_1030
            exit_min   = 90
            pnl_pts    = entry_price - exit_price   # venda: lucro se caiu
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
            'open_0900': round(open_0900),
            'var_pts':   var_pts,
            'entry':     round(entry_price),
            'exit':      round(exit_price),
            'resultado': resultado,
            'pnl_pts':   pnl_pts,
            'pnl_brl':   pnl_brl,
        })

    return pd.DataFrame(trades)

# ══════════════════════════════════════════════════════════════
def imprimir_bloco(direcao, label_gatilho):
    print("="*80)
    print(f"VENDA quando WIN {label_gatilho} 0.50% do open | Janela ate 10:30 | 1 mini")
    print("="*80)
    print(f"\n  {'GAIN':>6}  {'STOP':>6}  {'N':>5}  {'WR%':>7}  {'BE%':>6}  {'PF':>6}  "
          f"{'P&L Total':>11}  {'P&L/op':>8}  {'MaxDD':>9}  {'Seq-':>6}  Sig")
    print(f"  {'-'*88}")

    todos = []

    for gain, stop in SETUPS:
        df_t = backtest_venda_pct(PCT, gain, stop, direcao)
        if len(df_t) < 10:
            continue

        n    = len(df_t)
        wr   = (df_t['resultado']=='GAIN').mean()*100
        be   = stop / (gain + stop) * 100
        gw   = df_t[df_t['pnl_brl']>0]['pnl_brl'].sum()
        gl   = abs(df_t[df_t['pnl_brl']<0]['pnl_brl'].sum())
        pf   = gw / gl if gl > 0 else 99
        tot  = df_t['pnl_brl'].sum()
        med  = df_t['pnl_brl'].mean()
        eq   = df_t['pnl_brl'].cumsum()
        dd   = (eq - eq.cummax()).min()

        cur = ms = 0
        for r in df_t['resultado']:
            cur = cur+1 if r != 'GAIN' else 0
            ms  = max(ms, cur)

        _, p = stats.ttest_1samp(df_t['pnl_brl'], 0)
        sig  = "***" if p<0.01 else "** " if p<0.05 else "*  " if p<0.1 else "   "
        ok   = " <--" if tot > 0 and pf > 1.2 else ""

        print(f"  {gain:>6}  {stop:>6}  {n:>5}  {wr:>6.1f}%  {be:>5.1f}%  {pf:>6.2f}  "
              f"R${tot:>9,.0f}  R${med:>6,.1f}  R${dd:>7,.0f}  {ms:>6}  {sig}{ok}")

        todos.append({'gain': gain, 'stop': stop, 'n': n, 'wr': wr, 'be': be,
                      'pf': pf, 'total': tot, 'per_op': med, 'max_dd': dd,
                      'max_streak': ms, 'pval': p, 'df': df_t})

    # ── Detalha o melhor (maior PF entre os positivos) ──
    positivos = [r for r in todos if r['total'] > 0]
    if not positivos:
        print(f"\n  Nenhum setup positivo.\n")
        return todos

    best = max(positivos, key=lambda x: x['pf'])
    df_b  = best['df']
    gain  = best['gain']
    stop  = best['stop']

    print(f"\n{'─'*80}")
    print(f"DETALHAMENTO MELHOR SETUP — GAIN={gain}  STOP={stop}  ({direcao} 0.50% → VENDA)")
    print(f"{'─'*80}")

    print(f"\n  Variacao media no gatilho  : {df_b['var_pts'].mean():+.0f} pts")
    print(f"  Variacao min/max no gatilho: {df_b['var_pts'].min():+.0f} / {df_b['var_pts'].max():+.0f} pts")

    # Por ano
    print(f"\n  Por ano:")
    print(f"  {'Ano':>5}  {'N':>5}  {'WR%':>7}  {'P&L':>10}  {'MaxDD':>10}  {'P&L/op':>9}")
    for ano, g in df_b.groupby('ano'):
        wr_a = (g['resultado']=='GAIN').mean()*100
        tot  = g['pnl_brl'].sum()
        eq_a = g['pnl_brl'].cumsum()
        dd_a = (eq_a - eq_a.cummax()).min()
        print(f"  {ano:>5}  {len(g):>5}  {wr_a:>6.1f}%  R${tot:>8,.0f}  R${dd_a:>8,.0f}  R${g['pnl_brl'].mean():>7,.1f}")

    # Por dia da semana
    print(f"\n  Por dia da semana:")
    print(f"  {'Dia':>5}  {'N':>5}  {'WR%':>7}  {'P&L':>10}  {'P&L/op':>9}")
    for dow, nome in enumerate(DIAS_SEMANA):
        g = df_b[df_b['dow']==dow]
        if len(g) < 3: continue
        wr_d = (g['resultado']=='GAIN').mean()*100
        print(f"  {nome:>5}  {len(g):>5}  {wr_d:>6.1f}%  R${g['pnl_brl'].sum():>8,.0f}  R${g['pnl_brl'].mean():>7,.1f}")

    # Por horario
    print(f"\n  Por horario de entrada:")
    print(f"  {'Faixa':>12}  {'N':>5}  {'WR%':>7}  {'P&L/op':>9}")
    for f1, f2, lbl in [(0,20,'09:00-09:20'),(20,40,'09:20-09:40'),
                         (40,60,'09:40-10:00'),(60,90,'10:00-10:30')]:
        g = df_b[(df_b['entry_min']>=f1) & (df_b['entry_min']<f2)]
        if len(g) < 3: continue
        wr_h = (g['resultado']=='GAIN').mean()*100
        print(f"  {lbl:>12}  {len(g):>5}  {wr_h:>6.1f}%  R${g['pnl_brl'].mean():>7,.1f}")

    # Resultado por tipo
    g_cnt = (df_b['resultado']=='GAIN').sum()
    l_cnt = (df_b['resultado']=='LOSS').sum()
    e_cnt = (df_b['resultado']=='EXPIRADO').sum()
    n     = len(df_b)
    wr    = (df_b['resultado']=='GAIN').mean()*100
    tot   = df_b['pnl_brl'].sum()
    eq    = df_b['pnl_brl'].cumsum()
    dd    = (eq - eq.cummax()).min()
    gw    = df_b[df_b['pnl_brl']>0]['pnl_brl'].sum()
    gl2   = abs(df_b[df_b['pnl_brl']<0]['pnl_brl'].sum())
    pf    = gw/gl2 if gl2 > 0 else 99
    _, p  = stats.ttest_1samp(df_b['pnl_brl'], 0)
    sig   = "***" if p<0.01 else "**" if p<0.05 else "*" if p<0.1 else "n.s."

    print(f"\n  RESUMO FINAL:")
    print(f"  Operacoes    : {n}  (GAIN={g_cnt} | LOSS={l_cnt} | EXPIRADO={e_cnt})")
    print(f"  Win Rate     : {wr:.1f}%  |  Breakeven: {stop/(gain+stop)*100:.1f}%")
    print(f"  Profit Factor: {pf:.2f}")
    print(f"  P&L Total    : R$ {tot:,.2f} (1 mini) | R$ {tot*10:,.2f} (10 minis)")
    print(f"  Max Drawdown : R$ {dd:,.2f}")
    print(f"  P&L medio/op : R$ {df_b['pnl_brl'].mean():.2f}")
    print(f"  Significancia: {sig}  (p={p:.4f})")

    df_b.to_csv(f"{RESULTS_DIR}/backtest_venda_pct_{direcao.lower()}_{gain}g_{stop}s.csv", index=False)
    print(f"  Trades salvos: results/backtest_venda_pct_{direcao.lower()}_{gain}g_{stop}s.csv")
    print()
    return todos

# ── Roda os dois cenarios ──────────────────────────────────────
res_alta  = imprimir_bloco('ALTA',  'SUBIU')
res_queda = imprimir_bloco('QUEDA', 'CAIU')

# ── Tabela comparativa final ───────────────────────────────────
print("="*80)
print("RESUMO COMPARATIVO — TODOS SETUPS | VENDA em ALTA e VENDA em QUEDA")
print(f"  Gatilho: +-0.50% do open | Janela 09:00-10:30 | 1 mini contrato")
print("="*80)
print(f"\n  {'Gatilho':>10}  {'GAIN':>6}  {'STOP':>6}  {'N':>5}  {'WR%':>7}  {'BE%':>6}  "
      f"{'PF':>6}  {'P&L Total':>11}  {'MaxDD':>9}  Sig")
print(f"  {'-'*92}")

for direcao, label, todos in [('ALTA','SUBIU +0.50%',res_alta),('QUEDA','CAIU -0.50%',res_queda)]:
    for r in todos:
        _, p = stats.ttest_1samp(r['df']['pnl_brl'], 0)
        sig  = "***" if p<0.01 else "** " if p<0.05 else "*  " if p<0.1 else "   "
        ok   = " <<<" if r['total'] > 0 and r['pf'] > 1.3 else " <" if r['total'] > 0 and r['pf'] > 1.1 else ""
        print(f"  {label:>10}  {r['gain']:>6}  {r['stop']:>6}  {r['n']:>5}  {r['wr']:>6.1f}%  "
              f"{r['be']:>5.1f}%  {r['pf']:>6.2f}  R${r['total']:>9,.0f}  R${r['max_dd']:>7,.0f}  {sig}{ok}")
    print()
