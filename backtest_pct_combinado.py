"""
Backtest percentual — WIN 09:00-10:30
  Regra 1: WIN CAI  0.50% do open -> COMPRA
  Regra 2: WIN SOBE 0.50% do open -> VENDA
5 combinacoes de GAIN x STOP testadas em cada regra
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
PCT         = 0.005   # 0.50%

print("Carregando WIN M1...")
df = pd.read_csv("C:/estrategia/data/xp_win_m1.csv", parse_dates=['time'])
df = df.set_index('time').sort_index()
df_win = df.between_time('09:00','10:35')
dias = sorted(set(df_win.index.date))
print(f"  {len(dias)} dias | {dias[0]} -> {dias[-1]}\n")

# GAIN, STOP conforme solicitado
SETUPS = [
    (150, 150),
    (300, 150),
    (400, 200),
    (400, 400),
    (500, 500),
]
DIAS_NOME = ['Seg','Ter','Qua','Qui','Sex']

# ── Backtest generico ──────────────────────────────────────────
def backtest(pct, gain, stop, direcao):
    """
    direcao='COMPRA': entra comprado, TP acima, SL abaixo
    direcao='VENDA' : entra vendido,  TP abaixo, SL acima
    gatilho: COMPRA quando LOW <= open*(1-pct)
             VENDA  quando HIGH>= open*(1+pct)
    """
    trades = []
    for dia in dias:
        d = df_win[df_win.index.date == dia].copy()
        c0900 = d.between_time('09:00','09:00')
        c1030 = d.between_time('10:29','10:35')
        if len(c0900) == 0 or len(c1030) == 0:
            continue

        open0 = c0900['open'].iloc[0]
        close1030 = c1030['close'].iloc[-1]

        if direcao == 'COMPRA':
            nivel = open0 * (1 - pct)
            toque = d[d['low'] <= nivel]
        else:
            nivel = open0 * (1 + pct)
            toque = d[d['high'] >= nivel]

        if len(toque) == 0:
            continue

        ec  = toque.index[0]
        ep  = nivel
        emin = (ec.hour - 9) * 60 + ec.minute

        if direcao == 'COMPRA':
            tp, sl = ep + gain, ep - stop
        else:
            tp, sl = ep - gain, ep + stop

        after = d[(d.index > ec) &
                  (d.index.time <= pd.Timestamp('10:30').time())]

        res = xp = xmin = None
        for idx, row in after.iterrows():
            m = (idx.hour - 9)*60 + idx.minute
            if direcao == 'COMPRA':
                if row['high'] >= tp: res='GAIN'; xp=tp; xmin=m; break
                if row['low']  <= sl: res='LOSS'; xp=sl; xmin=m; break
            else:
                if row['low']  <= tp: res='GAIN'; xp=tp; xmin=m; break
                if row['high'] >= sl: res='LOSS'; xp=sl; xmin=m; break

        if res is None:
            xp   = close1030
            xmin = 90
            pts  = (xp - ep) if direcao=='COMPRA' else (ep - xp)
            res  = 'EXPIRADO'
        else:
            pts = gain if res=='GAIN' else -stop

        trades.append({
            'date': dia, 'ano': dia.year,
            'dow': pd.Timestamp(dia).dayofweek,
            'entry_min': emin, 'exit_min': xmin,
            'open0': round(open0), 'nivel': round(nivel),
            'var_pts': round(nivel - open0),
            'entry': round(ep), 'exit': round(xp),
            'resultado': res,
            'pnl_pts': pts,
            'pnl_brl': pts * VALOR_PONTO,
        })
    return pd.DataFrame(trades)

# ── Metricas ───────────────────────────────────────────────────
def metricas(df_t, gain, stop):
    n   = len(df_t)
    wr  = (df_t['resultado']=='GAIN').mean()*100
    be  = stop/(gain+stop)*100
    gw  = df_t[df_t['pnl_brl']>0]['pnl_brl'].sum()
    gl  = abs(df_t[df_t['pnl_brl']<0]['pnl_brl'].sum())
    pf  = gw/gl if gl>0 else 99
    tot = df_t['pnl_brl'].sum()
    med = df_t['pnl_brl'].mean()
    eq  = df_t['pnl_brl'].cumsum()
    dd  = (eq - eq.cummax()).min()
    cur=ms=0
    for r in df_t['resultado']:
        cur = cur+1 if r!='GAIN' else 0
        ms  = max(ms,cur)
    _,p = stats.ttest_1samp(df_t['pnl_brl'],0)
    sig = "***" if p<0.01 else "** " if p<0.05 else "*  " if p<0.1 else "   "
    return dict(n=n,wr=wr,be=be,pf=pf,tot=tot,med=med,dd=dd,ms=ms,p=p,sig=sig)

def detalhe(df_t, gain, stop, titulo):
    m = metricas(df_t, gain, stop)
    gc = (df_t['resultado']=='GAIN').sum()
    lc = (df_t['resultado']=='LOSS').sum()
    ec = (df_t['resultado']=='EXPIRADO').sum()
    sig2 = "***" if m['p']<0.01 else "**" if m['p']<0.05 else "*" if m['p']<0.1 else "n.s."

    print(f"\n{'='*70}")
    print(f"  {titulo}  |  GAIN={gain}  STOP={stop}")
    print(f"{'='*70}")
    print(f"  Variacao media no gatilho : {df_t['var_pts'].mean():+.0f} pts")
    print(f"  Operacoes : {m['n']}  (GAIN={gc}  LOSS={lc}  EXPIRADO={ec})")
    print(f"  Win Rate  : {m['wr']:.1f}%   Breakeven: {m['be']:.1f}%")
    print(f"  P. Factor : {m['pf']:.2f}")
    print(f"  P&L Total : R$ {m['tot']:,.2f} (1 mini)  |  R$ {m['tot']*10:,.2f} (10 minis)")
    print(f"  Max DD    : R$ {m['dd']:,.2f}")
    print(f"  P&L/op    : R$ {m['med']:.2f}")
    print(f"  Sig.      : {sig2}  (p={m['p']:.4f})")

    print(f"\n  Por ano:")
    print(f"  {'Ano':>5}  {'N':>4}  {'WR%':>7}  {'P&L':>10}  {'MaxDD':>9}  {'P&L/op':>8}")
    for ano, g in df_t.groupby('ano'):
        wa = (g['resultado']=='GAIN').mean()*100
        ta = g['pnl_brl'].sum()
        ea = g['pnl_brl'].cumsum(); da=(ea-ea.cummax()).min()
        print(f"  {ano:>5}  {len(g):>4}  {wa:>6.1f}%  R${ta:>8,.0f}  R${da:>7,.0f}  R${g['pnl_brl'].mean():>6,.1f}")

    print(f"\n  Por dia da semana:")
    print(f"  {'Dia':>5}  {'N':>4}  {'WR%':>7}  {'P&L':>10}  {'P&L/op':>8}")
    for dow, nome in enumerate(DIAS_NOME):
        g = df_t[df_t['dow']==dow]
        if len(g)<3: continue
        wa = (g['resultado']=='GAIN').mean()*100
        print(f"  {nome:>5}  {len(g):>4}  {wa:>6.1f}%  R${g['pnl_brl'].sum():>8,.0f}  R${g['pnl_brl'].mean():>6,.1f}")

    print(f"\n  Por horario de entrada:")
    print(f"  {'Faixa':>12}  {'N':>4}  {'WR%':>7}  {'P&L/op':>8}")
    for f1,f2,lbl in [(0,20,'09:00-09:20'),(20,40,'09:20-09:40'),
                       (40,60,'09:40-10:00'),(60,90,'10:00-10:30')]:
        g = df_t[(df_t['entry_min']>=f1)&(df_t['entry_min']<f2)]
        if len(g)<3: continue
        wa = (g['resultado']=='GAIN').mean()*100
        print(f"  {lbl:>12}  {len(g):>4}  {wa:>6.1f}%  R${g['pnl_brl'].mean():>6,.1f}")

# ══════════════════════════════════════════════════════════════
# REGRA 1 — CAI 0.50% -> COMPRA
# ══════════════════════════════════════════════════════════════
print("="*70)
print("REGRA 1 — WIN CAI 0.50% DO OPEN -> COMPRA")
print("="*70)
print(f"\n  {'GAIN':>6}  {'STOP':>6}  {'N':>5}  {'WR%':>7}  {'BE%':>6}  {'PF':>6}  "
      f"{'P&L 1mini':>11}  {'P&L 10mini':>12}  {'MaxDD':>9}  {'Seq':>5}  Sig")
print(f"  {'-'*95}")

comp_dfs = {}
for gain, stop in SETUPS:
    df_t = backtest(PCT, gain, stop, 'COMPRA')
    comp_dfs[(gain,stop)] = df_t
    m = metricas(df_t, gain, stop)
    ok = " <" if m['tot']>0 and m['pf']>1.3 else ""
    print(f"  {gain:>6}  {stop:>6}  {m['n']:>5}  {m['wr']:>6.1f}%  {m['be']:>5.1f}%  {m['pf']:>6.2f}  "
          f"R${m['tot']:>9,.0f}  R${m['tot']*10:>10,.0f}  R${m['dd']:>7,.0f}  {m['ms']:>5}  {m['sig']}{ok}")

# detalha os dois melhores
positivos = [(g,s) for g,s in SETUPS if metricas(comp_dfs[(g,s)],g,s)['tot']>0]
if positivos:
    ranked = sorted(positivos, key=lambda x: metricas(comp_dfs[x],x[0],x[1])['pf'], reverse=True)
    for gs in ranked[:2]:
        g, s = gs
        detalhe(comp_dfs[(g,s)], g, s, f"DETALHAMENTO — CAI 0.50% -> COMPRA")

# ══════════════════════════════════════════════════════════════
# REGRA 2 — SOBE 0.50% -> VENDA
# ══════════════════════════════════════════════════════════════
print("\n\n" + "="*70)
print("REGRA 2 — WIN SOBE 0.50% DO OPEN -> VENDA")
print("="*70)
print(f"\n  {'GAIN':>6}  {'STOP':>6}  {'N':>5}  {'WR%':>7}  {'BE%':>6}  {'PF':>6}  "
      f"{'P&L 1mini':>11}  {'P&L 10mini':>12}  {'MaxDD':>9}  {'Seq':>5}  Sig")
print(f"  {'-'*95}")

vend_dfs = {}
for gain, stop in SETUPS:
    df_t = backtest(PCT, gain, stop, 'VENDA')
    vend_dfs[(gain,stop)] = df_t
    m = metricas(df_t, gain, stop)
    ok = " <" if m['tot']>0 and m['pf']>1.3 else ""
    print(f"  {gain:>6}  {stop:>6}  {m['n']:>5}  {m['wr']:>6.1f}%  {m['be']:>5.1f}%  {m['pf']:>6.2f}  "
          f"R${m['tot']:>9,.0f}  R${m['tot']*10:>10,.0f}  R${m['dd']:>7,.0f}  {m['ms']:>5}  {m['sig']}{ok}")

positivos_v = [(g,s) for g,s in SETUPS if metricas(vend_dfs[(g,s)],g,s)['tot']>0]
if positivos_v:
    ranked_v = sorted(positivos_v, key=lambda x: metricas(vend_dfs[x],x[0],x[1])['pf'], reverse=True)
    for gs in ranked_v[:2]:
        g, s = gs
        detalhe(vend_dfs[(g,s)], g, s, f"DETALHAMENTO — SOBE 0.50% -> VENDA")

# ══════════════════════════════════════════════════════════════
# RESUMO FINAL LADO A LADO
# ══════════════════════════════════════════════════════════════
print("\n\n" + "="*70)
print("RESUMO FINAL — COMPRA na QUEDA vs VENDA na ALTA (0.50%)")
print("="*70)
print(f"\n  {'Setup':>12}  {'Regra':>8}  {'N':>5}  {'WR%':>7}  {'PF':>6}  "
      f"{'P&L 1m':>9}  {'P&L 10m':>10}  {'MaxDD':>9}  {'Ratio P/DD':>11}  Sig")
print(f"  {'-'*95}")

for gain, stop in SETUPS:
    lbl = f"G{gain}/S{stop}"
    for regra, dfs in [('CAI->COMPRA', comp_dfs), ('ALTA->VENDA', vend_dfs)]:
        df_t = dfs[(gain,stop)]
        m = metricas(df_t, gain, stop)
        ratio = abs(m['tot']/m['dd']) if m['dd']!=0 else 0
        ok = " ***MELHOR***" if m['pf']>=2.0 else " <" if m['tot']>0 and m['pf']>1.3 else ""
        print(f"  {lbl:>12}  {regra:>8}  {m['n']:>5}  {m['wr']:>6.1f}%  {m['pf']:>6.2f}  "
              f"R${m['tot']:>7,.0f}  R${m['tot']*10:>8,.0f}  R${m['dd']:>7,.0f}  "
              f"{ratio:>10.1f}x  {m['sig']}{ok}")
    print()

# Salva os melhores
for gain, stop in SETUPS:
    comp_dfs[(gain,stop)].to_csv(
        f"{RESULTS_DIR}/pct_compra_queda_{gain}g_{stop}s.csv", index=False)
    vend_dfs[(gain,stop)].to_csv(
        f"{RESULTS_DIR}/pct_venda_alta_{gain}g_{stop}s.csv", index=False)
print("Arquivos salvos em C:/estrategia/results/")
