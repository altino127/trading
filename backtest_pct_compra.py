"""
Backtest — COMPRA quando WIN sobe ou cai 0.50% do open (09:00-10:30)
Gatilho: percentual fixo do preco de abertura (nao pontos fixos)
Testa combinacoes especificas de GAIN x STOP em pontos
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
PCT         = 0.005   # 0,50%

# ── Carrega dados M1 ───────────────────────────────────────────
print("Carregando WIN M1...")
df = pd.read_csv("C:/estrategia/data/xp_win_m1.csv", parse_dates=['time'])
df = df.set_index('time').sort_index()
df_win = df.between_time('09:00','10:35')
dias = sorted(set(df_win.index.date))
print(f"  {len(dias)} dias de pregao | {dias[0]} -> {dias[-1]}\n")

# ── Combinacoes especificas solicitadas ────────────────────────
SETUPS = [
    (150, 150),
    (150, 300),   # gain, stop
    (200, 400),
    (400, 400),
    (500, 500),
]

# ── Funcao de backtest ─────────────────────────────────────────
def backtest_pct(pct, gain_pts, stop_pts, direcao_entrada):
    """
    direcao_entrada: 'ALTA'  = WIN subiu pct -> entrada COMPRA
                     'QUEDA' = WIN caiu  pct -> entrada COMPRA
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

        if direcao_entrada == 'ALTA':
            nivel      = open_0900 * (1 + pct)
            toque      = d[d['high'] >= nivel]
        else:
            nivel      = open_0900 * (1 - pct)
            toque      = d[d['low']  <= nivel]

        if len(toque) == 0:
            continue

        entry_candle = toque.index[0]
        entry_price  = nivel
        entry_min    = (entry_candle.hour - 9) * 60 + entry_candle.minute
        var_pts      = round(nivel - open_0900)   # pontos de variacao no gatilho

        # COMPRA: TP acima, SL abaixo
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
                resultado = 'GAIN'; exit_price = tp;  exit_min = min_atual; break
            if row['low']  <= sl:
                resultado = 'LOSS'; exit_price = sl;  exit_min = min_atual; break

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
# COMPARACAO: ALTA 0.50% vs QUEDA 0.50% — resumo por setup
# ══════════════════════════════════════════════════════════════

DIAS_SEMANA = ['Seg','Ter','Qua','Qui','Sex']

for direcao in ['ALTA', 'QUEDA']:
    print("="*80)
    print(f"COMPRA quando WIN {'SOBE' if direcao=='ALTA' else 'CAI'} 0.50% do open de 09:00")
    print(f"Janela de saida: ate 10:30 | 1 mini contrato")
    print("="*80)
    print(f"\n  {'GAIN':>6}  {'STOP':>6}  {'N':>5}  {'WR%':>7}  {'BE%':>6}  {'PF':>6}  "
          f"{'P&L Total':>11}  {'P&L/op':>8}  {'MaxDD':>9}  {'Seq-':>6}  Sig")
    print(f"  {'-'*88}")

    resultados_dir = []

    for gain, stop in SETUPS:
        df_t = backtest_pct(PCT, gain, stop, direcao)
        if len(df_t) < 10:
            print(f"  {gain:>6}  {stop:>6}  {'<10':>5}  — sem dados suficientes")
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

        ok = " <--" if tot > 0 and pf > 1.2 and wr >= be else ""

        print(f"  {gain:>6}  {stop:>6}  {n:>5}  {wr:>6.1f}%  {be:>5.1f}%  {pf:>6.2f}  "
              f"R${tot:>9,.0f}  R${med:>6,.1f}  R${dd:>7,.0f}  {ms:>6}  {sig}{ok}")

        resultados_dir.append({
            'gain': gain, 'stop': stop, 'n': n, 'wr': wr, 'be': be,
            'pf': pf, 'total': tot, 'per_op': med, 'max_dd': dd,
            'max_streak': ms, 'pval': p, 'direcao': direcao, 'df': df_t
        })

    # ── Detalhamento do melhor setup ──
    if resultados_dir:
        positivos = [r for r in resultados_dir if r['total'] > 0]
        if not positivos:
            print(f"\n  Nenhum setup positivo para {direcao}.")
            continue

        best = max(positivos, key=lambda x: x['pf'] if x['total'] > 0 else 0)
        df_b = best['df']

        print(f"\n{'─'*80}")
        print(f"DETALHAMENTO — GAIN={best['gain']}  STOP={best['stop']}  "
              f"[{'melhor PF positivo'}]  {direcao} 0.50%")
        print(f"{'─'*80}")

        # Variacao media em pontos no gatilho
        print(f"\n  Variacao media no gatilho: {df_b['var_pts'].mean():+.0f} pts "
              f"({df_b['var_pts'].min():+.0f} a {df_b['var_pts'].max():+.0f} pts)")

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

        # Resumo final
        n     = len(df_b)
        wr    = (df_b['resultado']=='GAIN').mean()*100
        tot   = df_b['pnl_brl'].sum()
        eq    = df_b['pnl_brl'].cumsum()
        dd    = (eq - eq.cummax()).min()
        gw    = df_b[df_b['pnl_brl']>0]['pnl_brl'].sum()
        gl    = abs(df_b[df_b['pnl_brl']<0]['pnl_brl'].sum())
        pf    = gw/gl if gl > 0 else 99
        g_cnt = (df_b['resultado']=='GAIN').sum()
        l_cnt = (df_b['resultado']=='LOSS').sum()
        e_cnt = (df_b['resultado']=='EXPIRADO').sum()
        _, p  = stats.ttest_1samp(df_b['pnl_brl'], 0)
        sig   = "***" if p<0.01 else "**" if p<0.05 else "*" if p<0.1 else "n.s."

        print(f"\n  RESUMO FINAL ({direcao} 0.50% → COMPRA):")
        print(f"  Operacoes    : {n}  (GAIN={g_cnt}  LOSS={l_cnt}  EXP={e_cnt})")
        print(f"  Win Rate     : {wr:.1f}%  |  Breakeven: {best['stop']/(best['gain']+best['stop'])*100:.1f}%")
        print(f"  Profit Factor: {pf:.2f}")
        print(f"  P&L Total    : R$ {tot:,.2f} (1 mini)  |  R$ {tot*10:,.2f} (10 minis)")
        print(f"  Max Drawdown : R$ {dd:,.2f}")
        print(f"  P&L medio/op : R$ {df_b['pnl_brl'].mean():.2f}")
        print(f"  Significancia: {sig}  (p={p:.4f})")

        df_b.to_csv(f"{RESULTS_DIR}/backtest_pct_{direcao.lower()}_{best['gain']}g_{best['stop']}s.csv", index=False)

    print()

# ══════════════════════════════════════════════════════════════
# TABELA RESUMO FINAL — TODOS OS SETUPS E DIRECOES
# ══════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("RESUMO COMPARATIVO — TODOS SETUPS | AMBAS DIRECOES")
print(f"  Gatilho: 0.50% do open | Janela: 09:00-10:30 | 1 mini contrato")
print("="*80)
print(f"\n  {'Direcao':>8}  {'GAIN':>6}  {'STOP':>6}  {'N':>5}  {'WR%':>7}  {'BE%':>6}  {'PF':>6}  {'P&L Total':>11}  {'MaxDD':>9}  Sig")
print(f"  {'-'*90}")

for direcao in ['ALTA', 'QUEDA']:
    for gain, stop in SETUPS:
        df_t = backtest_pct(PCT, gain, stop, direcao)
        if len(df_t) < 10:
            continue
        n   = len(df_t)
        wr  = (df_t['resultado']=='GAIN').mean()*100
        be  = stop/(gain+stop)*100
        gw  = df_t[df_t['pnl_brl']>0]['pnl_brl'].sum()
        gl  = abs(df_t[df_t['pnl_brl']<0]['pnl_brl'].sum())
        pf  = gw/gl if gl > 0 else 99
        tot = df_t['pnl_brl'].sum()
        eq  = df_t['pnl_brl'].cumsum()
        dd  = (eq - eq.cummax()).min()
        _, p = stats.ttest_1samp(df_t['pnl_brl'], 0)
        sig  = "***" if p<0.01 else "** " if p<0.05 else "*  " if p<0.1 else "   "
        ok   = " <<" if tot > 0 and pf > 1.2 else ""
        print(f"  {direcao:>8}  {gain:>6}  {stop:>6}  {n:>5}  {wr:>6.1f}%  {be:>5.1f}%  {pf:>6.2f}  "
              f"R${tot:>9,.0f}  R${dd:>7,.0f}  {sig}{ok}")
    print()
