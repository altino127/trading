"""
Analise de Abertura M1 — WIN 09:00 a 10:30
Pergunta: qual variacao desde o open de 09:00 gera o melhor sinal de compra/venda?
"""
import pandas as pd
import numpy as np
from scipy import stats
import warnings, sys, os
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RESULTS_DIR = "C:/estrategia/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# 1. CARREGA M1 E FILTRA JANELA
# ─────────────────────────────────────────────
print("Carregando WIN M1...")
df = pd.read_csv("C:/estrategia/data/xp_win_m1.csv", parse_dates=['time'])
df = df.set_index('time').sort_index()

# Filtra 09:00-10:30 BRT
df_window = df.between_time('09:00', '10:30')
dias = sorted(set(df_window.index.date))
print(f"  Total candles M1 na janela 09:00-10:30: {len(df_window):,}")
print(f"  Dias de pregao: {len(dias)}")

# ─────────────────────────────────────────────
# 2. MONTA PERFIL MINUTO A MINUTO POR DIA
# ─────────────────────────────────────────────
print("Construindo perfil de abertura por dia...")

records = []
for dia in dias:
    d = df_window[df_window.index.date == dia].copy()

    c0900 = d.between_time('09:00','09:00')
    c1030 = d.between_time('10:29','10:30')

    if len(c0900) == 0 or len(c1030) == 0:
        continue

    open_0900  = c0900['open'].iloc[0]
    close_1030 = c1030['close'].iloc[-1]
    high_day   = d['high'].max()
    low_day    = d['low'].min()

    row = {
        'date':       dia,
        'dow':        pd.Timestamp(dia).dayofweek,
        'open_0900':  open_0900,
        'close_1030': close_1030,
        'ret_full':   (close_1030 - open_0900) / open_0900 * 100,
        'pts_full':   close_1030 - open_0900,
        'high_pts':   high_day - open_0900,
        'low_pts':    open_0900 - low_day,
    }

    # Para cada minuto N apos o open, calcula:
    # - variacao em pontos do open ate o minuto N
    # - retorno do minuto N ate o fechamento 10:30
    for n_min in [1,2,3,5,7,10,12,15,20,25,30]:
        target_time = f"09:{n_min:02d}" if n_min < 60 else f"10:{n_min-60:02d}"
        candles_n = d.between_time('09:00', target_time)
        if len(candles_n) == 0:
            continue

        price_n    = candles_n['close'].iloc[-1]
        var_n_pts  = price_n - open_0900
        var_n_pct  = var_n_pts / open_0900 * 100
        ret_after  = (close_1030 - price_n) / price_n * 100

        # Retorno alinhado com sinal (momentum vs reversao)
        ret_momentum  = np.sign(var_n_pts) * ret_after   # se subiu, compra; se caiu, vende
        ret_reversion = -np.sign(var_n_pts) * ret_after  # oposto

        row[f'm{n_min:02d}_var_pts']   = round(var_n_pts, 0)
        row[f'm{n_min:02d}_var_pct']   = round(var_n_pct, 4)
        row[f'm{n_min:02d}_ret_after'] = round(ret_after, 4)
        row[f'm{n_min:02d}_momentum']  = round(ret_momentum, 4)
        row[f'm{n_min:02d}_reversion'] = round(ret_reversion, 4)

    records.append(row)

df_daily = pd.DataFrame(records).set_index('date')
df_daily.to_csv(f"{RESULTS_DIR}/win_m1_opening.csv")
print(f"  Dataset: {len(df_daily)} dias validos\n")

DIAS_NOME = ['Seg','Ter','Qua','Qui','Sex']
MINUTOS   = [1,2,3,5,7,10,12,15,20,25,30]

# ─────────────────────────────────────────────
# 3. ANALISE POR MINUTO — MOMENTUM vs REVERSAO
# ─────────────────────────────────────────────
print("="*70)
print("MOMENTUM vs REVERSAO — qual minuto e qual variacao funciona melhor?")
print("="*70)
print(f"\n  {'Min':>4}  {'Estrategia':>12}  {'N':>5}  {'WinRate':>8}  {'RetMed':>8}  {'p-val':>8}  Conclusao")
print(f"  {'-'*70}")

best = []
for n in MINUTOS:
    col_mom = f'm{n:02d}_momentum'
    col_rev = f'm{n:02d}_reversion'
    if col_mom not in df_daily.columns:
        continue

    for strat, col in [('MOMENTUM', col_mom), ('REVERSAO', col_rev)]:
        sub = df_daily[col].dropna()
        if len(sub) < 30: continue
        wr   = (sub > 0).mean() * 100
        med  = sub.mean()
        _, p = stats.ttest_1samp(sub, 0)
        sig  = "*** FORTE" if p<0.01 and wr>53 else "**  ok" if p<0.05 else "*   fraco" if p<0.1 else "    ruido"
        print(f"  {n:>4}  {strat:>12}  {len(sub):>5}  {wr:>7.1f}%  {med:>+7.4f}%  {p:>8.4f}  {sig}")
        best.append({'minuto': n, 'estrategia': strat, 'wr': wr, 'ret_med': med, 'pval': p, 'n': len(sub)})

# ─────────────────────────────────────────────
# 4. ANALISE POR THRESHOLD DE VARIACAO (PONTOS)
# ─────────────────────────────────────────────
print("\n" + "="*70)
print("THRESHOLD DE VARIACAO — a partir de quantos pontos o sinal e confiavel?")
print("="*70)

for n in [5, 10, 15, 30]:
    col_pts = f'm{n:02d}_var_pts'
    col_rev = f'm{n:02d}_reversion'
    col_mom = f'm{n:02d}_momentum'
    if col_pts not in df_daily.columns: continue

    print(f"\n  Minuto {n:02d} pos-open:")
    print(f"  {'Threshold':>20}  {'N':>5}  {'WinMOM%':>8}  {'WinREV%':>8}  {'Vencedor':>12}  p-val")
    print(f"  {'-'*65}")

    thresholds = [0, 50, 100, 150, 200, 250, 300, 400, 500, 600, 800]
    for thr in thresholds:
        sub = df_daily[abs(df_daily[col_pts]) >= thr]
        if len(sub) < 15: continue

        mom_pnl = sub[col_mom]
        rev_pnl = sub[col_rev]

        wr_mom = (mom_pnl > 0).mean() * 100
        wr_rev = (rev_pnl > 0).mean() * 100
        _, p_m = stats.ttest_1samp(mom_pnl, 0)
        _, p_r = stats.ttest_1samp(rev_pnl, 0)

        if wr_mom > wr_rev:
            vencedor = f"MOMENTUM({wr_mom:.1f}%)"
            p_best   = p_m
        else:
            vencedor = f"REVERSAO({wr_rev:.1f}%)"
            p_best   = p_r

        sig = "***" if p_best<0.01 else "** " if p_best<0.05 else "*  " if p_best<0.1 else "   "
        print(f"  |var| >= {thr:>5} pts  {len(sub):>5}  {wr_mom:>7.1f}%  {wr_rev:>7.1f}%  {vencedor:>20}  {sig} p={p_best:.3f}")

# ─────────────────────────────────────────────
# 5. DISTRIBUICAO DOS MOVIMENTOS NA ABERTURA
# ─────────────────────────────────────────────
print("\n" + "="*70)
print("DISTRIBUICAO DOS MOVIMENTOS NOS PRIMEIROS 5, 10, 15, 30 MINUTOS")
print("="*70)

for n in [5, 10, 15, 30]:
    col = f'm{n:02d}_var_pts'
    if col not in df_daily.columns: continue
    s = df_daily[col].dropna()
    print(f"\n  Min {n:02d}: media={s.mean():+.0f}pts  std={s.std():.0f}pts  "
          f"p10={s.quantile(.1):.0f}  p25={s.quantile(.25):.0f}  "
          f"p75={s.quantile(.75):.0f}  p90={s.quantile(.9):.0f}  "
          f"max={s.max():.0f}  min={s.min():.0f}")

    # Distribuicao por faixas
    bins = [(-9999,-600),(-600,-400),(-400,-200),(-200,-100),
            (-100,0),(0,100),(100,200),(200,400),(400,600),(600,9999)]
    linha = []
    for lo, hi in bins:
        n_sub = ((s >= lo) & (s < hi)).sum()
        pct   = n_sub / len(s) * 100
        if n_sub > 0:
            linha.append(f"[{lo:>5},{hi:>5}): {n_sub:3d} ({pct:4.1f}%)")
    for item in linha:
        print(f"    {item}")

# ─────────────────────────────────────────────
# 6. MELHOR COMBINACAO — RESUMO EXECUTIVO
# ─────────────────────────────────────────────
print("\n" + "="*70)
print("RESUMO — MELHORES COMBINACOES MINUTO x THRESHOLD")
print("="*70)

df_best = pd.DataFrame(best)
if len(df_best) > 0:
    top = df_best[df_best['pval'] < 0.15].sort_values('wr', ascending=False).head(10)
    print(f"\n  Top resultados por win rate (p < 0.15):")
    print(f"  {'Min':>4}  {'Estrategia':>12}  {'N':>5}  {'WinRate':>8}  {'Ret medio':>10}  p-val")
    for _, r in top.iterrows():
        print(f"  {r['minuto']:>4}  {r['estrategia']:>12}  {r['n']:>5}  {r['wr']:>7.1f}%  {r['ret_med']:>+9.4f}%  {r['pval']:.4f}")
