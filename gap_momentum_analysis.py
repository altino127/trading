"""
Hipotese 1: Momentum dos primeiros 30min reverte nos 60min seguintes?
Hipotese 2: Gap de abertura tende a fechar dentro da janela 09:00-10:30?
Ativo: WIN e WDO | Timeframe: M15 | Periodo: 2023-2026
"""
import pandas as pd
import numpy as np
from scipy import stats
import warnings, os, sys
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR    = "C:/estrategia/data"
RESULTS_DIR = "C:/estrategia/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# CARREGA E AJUSTA TIMEZONE
# ─────────────────────────────────────────────
def load_b3(fname):
    df = pd.read_csv(f"{DATA_DIR}/{fname}", parse_dates=['time'])
    df['time'] = df['time'] + pd.Timedelta(hours=-3)   # UTC -> BRT
    return df.set_index('time').sort_index()

print("Carregando dados...")
win = load_b3("xp_win_m15.csv")
wdo = load_b3("xp_wdo_m15.csv")
print(f"  WIN: {len(win):,} candles | {win.index[0].date()} -> {win.index[-1].date()}")

# ─────────────────────────────────────────────
# MONTA DATASET DIARIO
# ─────────────────────────────────────────────
def build_daily(df, name):
    """
    Para cada dia de pregao, extrai:
    - gap         : open 09:00 - close anterior (pontos e %)
    - ret_h1      : retorno 09:00 -> 09:30 (primeiros 2 candles M15)
    - ret_h2      : retorno 09:30 -> 10:30 (proximos 4 candles M15)
    - ret_full    : retorno 09:00 -> 10:30 (janela completa)
    - gap_closed  : o gap foi fechado dentro da janela?
    - max_favor   : maximo favoravel durante h2 (para calcular profit potencial)
    - max_adverse : maximo adverso durante h2
    """
    rows = []
    dias = sorted(set(df.index.date))

    for i in range(1, len(dias)):
        today     = dias[i]
        yesterday = dias[i-1]

        # Candles do dia de hoje
        today_df = df[df.index.date == today]
        # Candles de ontem
        yest_df  = df[df.index.date == yesterday]

        if len(today_df) == 0 or len(yest_df) == 0:
            continue

        # --- Candles por horario ---
        c_0900 = today_df.between_time('09:00','09:14')
        c_0915 = today_df.between_time('09:15','09:29')
        c_0930 = today_df.between_time('09:30','09:44')
        c_0945 = today_df.between_time('09:45','09:59')
        c_1000 = today_df.between_time('10:00','10:14')
        c_1015 = today_df.between_time('10:15','10:29')
        c_h2   = today_df.between_time('09:30','10:29')

        if len(c_0900)==0 or len(c_0915)==0 or len(c_h2)<2:
            continue

        open_0900   = c_0900['open'].iloc[0]
        close_0930  = c_0915['close'].iloc[-1]   # fim dos primeiros 30min
        open_0930   = c_h2['open'].iloc[0]        # inicio da segunda metade
        close_1030  = c_h2['close'].iloc[-1]      # fim da janela

        prev_close  = yest_df['close'].iloc[-1]   # fechamento de ontem

        if open_0900 == 0 or prev_close == 0:
            continue

        # --- Gap ---
        gap_pts = open_0900 - prev_close
        gap_pct = gap_pts / prev_close * 100

        # --- Retornos ---
        ret_h1   = (close_0930 - open_0900)  / open_0900  * 100
        ret_h2   = (close_1030 - open_0930)  / open_0930  * 100
        ret_full = (close_1030 - open_0900)  / open_0900  * 100

        # --- Gap fechado? ---
        # Gap positivo: open > prev_close → gap fecha se preco desce ate prev_close
        # Gap negativo: open < prev_close → gap fecha se preco sobe ate prev_close
        h2_lows  = c_h2['low'].values
        h2_highs = c_h2['high'].values

        if gap_pts > 0:
            gap_closed = bool(np.any(h2_lows <= prev_close))
        elif gap_pts < 0:
            gap_closed = bool(np.any(h2_highs >= prev_close))
        else:
            gap_closed = True

        # --- Max favor/adverse para H2 (sentido contrario ao H1) ---
        direction_h2 = -1 if ret_h1 > 0 else 1   # espera reversao
        if direction_h2 == 1:   # espera alta em h2
            max_favor   = (c_h2['high'].max()  - open_0930) / open_0930 * 100
            max_adverse = (c_h2['low'].min()   - open_0930) / open_0930 * 100
        else:                    # espera queda em h2
            max_favor   = (open_0930 - c_h2['low'].min())  / open_0930 * 100
            max_adverse = (open_0930 - c_h2['high'].max()) / open_0930 * 100

        rows.append({
            'date':       pd.Timestamp(today),
            'dow':        pd.Timestamp(today).dayofweek,
            'dow_name':   ['Seg','Ter','Qua','Qui','Sex'][pd.Timestamp(today).dayofweek],
            'open_0900':  open_0900,
            'prev_close': prev_close,
            'gap_pts':    round(gap_pts, 2),
            'gap_pct':    round(gap_pct, 4),
            'ret_h1':     round(ret_h1, 4),
            'ret_h2':     round(ret_h2, 4),
            'ret_full':   round(ret_full, 4),
            'gap_closed': gap_closed,
            'max_favor':  round(max_favor, 4),
            'max_adverse':round(max_adverse, 4),
        })

    return pd.DataFrame(rows).set_index('date')

print("Construindo dataset diario...")
df_win = build_daily(win, 'WIN')
df_wdo = build_daily(wdo, 'WDO')
print(f"  WIN: {len(df_win)} dias | WDO: {len(df_wdo)} dias")

# Salva dataset
df_win.to_csv(f"{RESULTS_DIR}/win_gap_momentum.csv")
df_wdo.to_csv(f"{RESULTS_DIR}/wdo_gap_momentum.csv")

# ─────────────────────────────────────────────
# ANALISE COMPLETA POR ATIVO
# ─────────────────────────────────────────────
DIAS = ['Seg','Ter','Qua','Qui','Sex']

def full_analysis(df, name):
    print("\n" + "="*65)
    print(f"ANALISE COMPLETA — {name}")
    print("="*65)

    # ── HIPOTESE 1: Momentum H1 → Reversao H2 ────────────────────
    print(f"\n{'─'*65}")
    print(f"HIPOTESE 1 — Primeiros 30min revertem nos 60min seguintes?")
    print(f"{'─'*65}")
    print(f"\n  Logica: se WIN sobe muito em 09:00-09:30 → vende esperando queda em 09:30-10:30")
    print(f"          se WIN cai  muito em 09:00-09:30 → compra esperando alta em 09:30-10:30\n")

    # Sinal de reversao: -sign(ret_h1) * ret_h2
    df['rev_pnl'] = -np.sign(df['ret_h1']) * df['ret_h2']

    print(f"  {'Filtro':<25} {'N':>5} {'Win%':>7} {'Med%':>8} {'Max%':>8} {'Min%':>8} {'p-val':>8} {'Sig'}")
    print(f"  {'-'*72}")

    for label, mask in [
        ("Todos os dias",          pd.Series(True, index=df.index)),
        ("|H1| > 0.10%",           abs(df['ret_h1']) > 0.10),
        ("|H1| > 0.15%",           abs(df['ret_h1']) > 0.15),
        ("|H1| > 0.20%",           abs(df['ret_h1']) > 0.20),
        ("|H1| > 0.25%",           abs(df['ret_h1']) > 0.25),
        ("|H1| > 0.30%",           abs(df['ret_h1']) > 0.30),
        ("H1 > +0.15% (so alta)",  df['ret_h1'] > 0.15),
        ("H1 < -0.15% (so queda)", df['ret_h1'] < -0.15),
    ]:
        sub = df[mask]['rev_pnl'].dropna()
        if len(sub) < 10: continue
        wr   = (sub > 0).mean() * 100
        med  = sub.mean()
        mx   = sub.max()
        mn   = sub.min()
        _, p = stats.ttest_1samp(sub, 0)
        sig  = "***" if p<0.01 else "** " if p<0.05 else "*  " if p<0.1 else "   "
        print(f"  {label:<25} {len(sub):>5} {wr:>6.1f}%  {med:>+7.4f}%  {mx:>+7.4f}%  {mn:>+7.4f}%  {p:>7.4f}  {sig}")

    # Por dia da semana (melhor threshold)
    best_thresh = 0.20
    print(f"\n  Por dia da semana (|H1| > {best_thresh}%):")
    print(f"  {'Dia':<8} {'N':>5} {'Win%':>7} {'Ret medio':>11} {'Sig'}")
    for dow, dname in enumerate(DIAS):
        sub = df[(abs(df['ret_h1']) > best_thresh) & (df['dow']==dow)]['rev_pnl'].dropna()
        if len(sub) < 5: continue
        wr   = (sub > 0).mean() * 100
        med  = sub.mean()
        _, p = stats.ttest_1samp(sub, 0)
        sig  = "***" if p<0.01 else "** " if p<0.05 else "*  " if p<0.1 else "   "
        print(f"  {dname:<8} {len(sub):>5} {wr:>6.1f}%  {med:>+9.4f}%  {sig}")

    # ── HIPOTESE 2: Gap fecha na janela? ─────────────────────────
    print(f"\n{'─'*65}")
    print(f"HIPOTESE 2 — Gap de abertura fecha dentro de 09:00-10:30?")
    print(f"{'─'*65}")
    print(f"\n  Logica: se WIN abre acima do fechamento anterior → preco volta ao nivel anterior?\n")

    # Taxa geral de fechamento de gap
    total     = len(df)
    gap_up    = df[df['gap_pts'] > 0]
    gap_down  = df[df['gap_pts'] < 0]
    gap_zero  = df[df['gap_pts'] == 0]

    pct_up   = len(gap_up)  / total * 100
    pct_down = len(gap_down)/ total * 100

    print(f"  Distribuicao de gaps:")
    print(f"    Gap positivo (abre acima): {len(gap_up):>4} dias ({pct_up:.1f}%)")
    print(f"    Gap negativo (abre abaixo):{len(gap_down):>4} dias ({pct_down:.1f}%)")
    print(f"    Sem gap:                   {len(gap_zero):>4} dias")

    print(f"\n  Taxa de fechamento do gap por tamanho:")
    print(f"  {'Filtro':<30} {'N':>5} {'Fecha%':>8} {'Med pts':>9} {'p-val':>8} {'Sig'}")
    print(f"  {'-'*65}")

    for label, mask in [
        ("Qualquer gap",           abs(df['gap_pts']) > 0),
        ("Gap > 50 pts",           abs(df['gap_pts']) > 50),
        ("Gap > 100 pts",          abs(df['gap_pts']) > 100),
        ("Gap > 200 pts",          abs(df['gap_pts']) > 200),
        ("Gap > 300 pts",          abs(df['gap_pts']) > 300),
        ("Gap > 500 pts",          abs(df['gap_pts']) > 500),
        ("Gap positivo > 100 pts", df['gap_pts'] > 100),
        ("Gap negativo < -100 pts",df['gap_pts'] < -100),
    ]:
        sub = df[mask]
        if len(sub) < 5: continue
        close_rate = sub['gap_closed'].mean() * 100
        med_gap    = sub['gap_pts'].abs().median()
        # Teste binomial vs 50%
        n_closed   = sub['gap_closed'].sum()
        res        = stats.binomtest(int(n_closed), len(sub), 0.5)
        p          = res.pvalue
        sig        = "***" if p<0.01 else "** " if p<0.05 else "*  " if p<0.1 else "   "
        print(f"  {label:<30} {len(sub):>5} {close_rate:>7.1f}%  {med_gap:>8.0f}pts  {p:>7.4f}  {sig}")

    # Distribuicao dos gaps em buckets
    print(f"\n  Distribuicao e taxa de fechamento por faixa de gap:")
    print(f"  {'Faixa (pts)':<25} {'N':>5} {'Fecha%':>8} {'Ret H2 medio':>14}")
    bins = [(-9999,-500),(-500,-300),(-300,-200),(-200,-100),(-100,-50),
            (-50,0),(0,50),(50,100),(100,200),(200,300),(300,500),(500,9999)]
    for lo, hi in bins:
        sub = df[(df['gap_pts'] >= lo) & (df['gap_pts'] < hi)]
        if len(sub) < 3: continue
        cr  = sub['gap_closed'].mean() * 100
        r2  = sub['ret_h2'].mean()
        print(f"  [{lo:>6}, {hi:>6})         {len(sub):>5} {cr:>7.1f}%  {r2:>+12.4f}%")

    # Por dia da semana
    print(f"\n  Taxa de fechamento por dia da semana (gap > 100 pts):")
    print(f"  {'Dia':<8} {'N':>5} {'Fecha%':>8} {'Gap medio':>11}")
    for dow, dname in enumerate(DIAS):
        sub = df[(abs(df['gap_pts']) > 100) & (df['dow']==dow)]
        if len(sub) < 5: continue
        cr   = sub['gap_closed'].mean() * 100
        mg   = sub['gap_pts'].abs().mean()
        print(f"  {dname:<8} {len(sub):>5} {cr:>7.1f}%  {mg:>10.0f}pts")

    # ── ESTATISTICAS DESCRITIVAS ──────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"ESTATISTICAS DESCRITIVAS — {name}")
    print(f"{'─'*65}")
    print(f"  Gap (pontos):  media={df['gap_pts'].mean():.0f}  std={df['gap_pts'].std():.0f}  "
          f"min={df['gap_pts'].min():.0f}  max={df['gap_pts'].max():.0f}")
    print(f"  Ret H1 (%):    media={df['ret_h1'].mean():.4f}  std={df['ret_h1'].std():.4f}  "
          f"p90={df['ret_h1'].quantile(.9):.4f}  p10={df['ret_h1'].quantile(.1):.4f}")
    print(f"  Ret H2 (%):    media={df['ret_h2'].mean():.4f}  std={df['ret_h2'].std():.4f}")
    print(f"  Correlacao H1 x H2: {df['ret_h1'].corr(df['ret_h2']):.4f}")
    _, p_corr = stats.pearsonr(df['ret_h1'].dropna(), df['ret_h2'].dropna())
    print(f"  p-valor correlacao: {p_corr:.4f} {'*** SIGNIFICATIVO' if p_corr < 0.05 else '(nao significativo)'}")

# ─────────────────────────────────────────────
# RODA PARA WIN E WDO
# ─────────────────────────────────────────────
full_analysis(df_win, "WIN (Mini Indice)")
full_analysis(df_wdo, "WDO (Mini Dolar)")

print("\n\nArquivos salvos:")
print(f"  {RESULTS_DIR}/win_gap_momentum.csv")
print(f"  {RESULTS_DIR}/wdo_gap_momentum.csv")
