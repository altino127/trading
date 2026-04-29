"""
Analise de Distorcao e Reversao — Janela 09:00-10:30 BRT
Hipotese: quando WIN se move alem do que os drivers justificam → tende a reverter
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from scipy import stats
import warnings, os, sys
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR    = "C:/estrategia/data"
RESULTS_DIR = "C:/estrategia/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

INF_OFFSET = 0   # Infinox ja em BRT (confirmado anteriormente)
XP_OFFSET  = -3  # XP em UTC, converte para BRT

# ─────────────────────────────────────────────
# 1. CARREGA TODOS OS ATIVOS
# ─────────────────────────────────────────────
def load(path, offset_h=0):
    df = pd.read_csv(path, parse_dates=['time'])
    df['time'] = df['time'] + pd.Timedelta(hours=offset_h)
    return df.set_index('time').sort_index()

print("[1] Carregando dados M15...")

# B3 (XP) — UTC → BRT (-3h)
win_full   = load(f"{DATA_DIR}/xp_win_m15.csv",   XP_OFFSET)['close']
wdo_full   = load(f"{DATA_DIR}/xp_wdo_m15.csv",   XP_OFFSET)['close']
petr4_full = load(f"{DATA_DIR}/xp_petr4_m15.csv", XP_OFFSET)['close']
di1_full   = load(f"{DATA_DIR}/xp_di1_m15.csv",   XP_OFFSET)['close']

# Globais (Infinox)
glb = {}
for name, fname in {
    'spx':    'spx500', 'oil':    'oil',    'gold':   'gold',
    'nas100': 'nas100', 'audusd': 'audusd', 'usdmxn': 'usdmxn',
    'eurusd': 'eurusd', 'vix':    'vix',    'usdx':   'usdx',
    'usdjpy': 'usdjpy', 'usdcad': 'usdcad', 'china50':'china50',
    'ger40':  'ger40',
}.items():
    try:
        glb[name] = load(f"{DATA_DIR}/infinox_{fname}_m15.csv", INF_OFFSET)['close']
    except:
        print(f"  aviso: {name} nao encontrado")

print(f"  B3: WIN, WDO, PETR4, DI1 | Global: {list(glb.keys())}")

# ─────────────────────────────────────────────
# 2. RETORNO JANELA 09:00-10:30 (B3)
# ─────────────────────────────────────────────
def window_ret(series, h1=9, h2=10, m2=15):
    """Retorno da janela: open 09:00 → close 10:15 (ultimo candle M15 antes 10:30)"""
    w = series.between_time(f'{h1:02d}:00', f'{h2:02d}:{m2:02d}')
    by_day = w.groupby(w.index.date)
    op  = by_day.first()
    cl  = by_day.last()
    ret = (cl - op) / op * 100
    ret.index = pd.DatetimeIndex(ret.index)
    return ret, op, cl

ret_win,  open_win,  close_win  = window_ret(win_full)
ret_wdo,  open_wdo,  close_wdo  = window_ret(wdo_full)
ret_petr4,_,_                   = window_ret(petr4_full)
ret_di1,  _,         close_di1  = window_ret(di1_full)

# ─────────────────────────────────────────────
# 3. RETORNO OVERNIGHT DOS GLOBAIS
#    (de 17:00 BRT de ontem ate 09:00 BRT de hoje)
# ─────────────────────────────────────────────
def overnight_ret(series):
    """Variacao do ativo global das 17h BRT de ontem ate 09h BRT de hoje"""
    sub = series.between_time('09:00','09:15').copy()
    sub_dates = sub.index.normalize()
    at_open = sub.groupby(sub_dates).first()
    at_open.index = pd.DatetimeIndex(at_open.index)
    ret = at_open.pct_change() * 100
    return ret

print("[2] Calculando retornos overnight dos globais...")
glb_ret = {}
for name, s in glb.items():
    glb_ret[name] = overnight_ret(s)

# ─────────────────────────────────────────────
# 4. RETORNO POS-JANELA 10:30-12:00 (para teste de reversao)
# ─────────────────────────────────────────────
def post_window_ret(series, h1=10, m1=30, h2=12, m2=0):
    w   = series.between_time(f'{h1:02d}:{m1:02d}', f'{h2:02d}:{m2:02d}')
    by_day = w.groupby(w.index.date)
    op  = by_day.first()
    cl  = by_day.last()
    ret = (cl - op) / op * 100
    ret.index = pd.DatetimeIndex(ret.index)
    return ret

ret_win_post = post_window_ret(win_full)
ret_wdo_post = post_window_ret(wdo_full)

print("[3] Montando dataset unificado...")
df = pd.DataFrame({'win': ret_win, 'wdo': ret_wdo,
                   'petr4': ret_petr4, 'di1': ret_di1,
                   'win_post': ret_win_post, 'wdo_post': ret_wdo_post,
                   **{f'g_{k}': v for k, v in glb_ret.items()}}).dropna()

print(f"    Dias validos: {len(df)} | {df.index[0].date()} -> {df.index[-1].date()}")

# ─────────────────────────────────────────────
# 5. CORRELACAO COMPLETA (todos os ativos)
# ─────────────────────────────────────────────
print("\n" + "="*65)
print("CORRELACAO TOTAL — WIN e WDO vs TODOS OS ATIVOS (09:00-10:30)")
print("="*65)

all_features = [c for c in df.columns if c not in ['win','wdo','win_post','wdo_post']]

for target in ['win', 'wdo']:
    print(f"\n  {target.upper()} correlaciona com:")
    corrs = []
    for f in all_features:
        c, p = stats.pearsonr(df[target], df[f])
        corrs.append((f.replace('g_',''), c, p))
    corrs.sort(key=lambda x: abs(x[1]), reverse=True)
    print(f"  {'Ativo':<12} {'Corr':>7}  {'p-val':>7}  Sig   Barra")
    print(f"  {'-'*55}")
    for name, c, p in corrs:
        sig  = "***" if p<0.01 else "** " if p<0.05 else "*  " if p<0.1 else "   "
        bar  = '#' * int(abs(c) * 40)
        sn   = '+' if c>0 else '-'
        print(f"  {name:<12} {sn}{abs(c):.3f}  {p:>7.3f}  {sig}   {bar}")

# ─────────────────────────────────────────────
# 6. MODELO DE FAIR VALUE + DISTORCAO
# ─────────────────────────────────────────────
print("\n" + "="*65)
print("MODELO DE FAIR VALUE E DISTORCAO")
print("="*65)

# Seleciona features mais correlacionadas (|corr| > 0.05 e p < 0.10)
def select_features(target, min_corr=0.05, max_p=0.10):
    selected = []
    for f in all_features:
        c, p = stats.pearsonr(df[target], df[f])
        if abs(c) >= min_corr and p <= max_p:
            selected.append(f)
    return selected

feats_win = select_features('win')
feats_wdo = select_features('wdo')
print(f"\n  Features selecionadas para WIN: {[f.replace('g_','') for f in feats_win]}")
print(f"  Features selecionadas para WDO: {[f.replace('g_','') for f in feats_wdo]}")

def build_distortion(target, features, label):
    if not features:
        print(f"  Nenhuma feature significativa para {label}")
        return None

    X = df[features].values
    y = df[target].values

    # Rolling OLS (30 dias) para fair value dinamico
    ROLL = 60
    fair_vals = []
    for i in range(ROLL, len(df)):
        X_w = X[i-ROLL:i]; y_w = y[i-ROLL:i]
        m = LinearRegression().fit(X_w, y_w)
        fair_vals.append({'date': df.index[i],
                          'actual': y[i],
                          'fair':   m.predict(X[[i]])[0],
                          'r2':     m.score(X_w, y_w)})

    res = pd.DataFrame(fair_vals).set_index('date')
    res['distortion']  = res['actual'] - res['fair']
    roll_std           = res['distortion'].rolling(ROLL).std()
    roll_mean          = res['distortion'].rolling(ROLL).mean()
    res['z_score']     = (res['distortion'] - roll_mean) / roll_std
    res['win_post']    = df['win_post'].reindex(res.index)
    res['wdo_post']    = df['wdo_post'].reindex(res.index)
    res['actual_post'] = df[f'{target.split("_")[0]}_post'].reindex(res.index)

    print(f"\n  {label}: R2 medio = {res['r2'].mean():.3f} | Z atual = {res['z_score'].iloc[-1]:.2f}")
    return res

res_win = build_distortion('win', feats_win, 'WIN')
res_wdo = build_distortion('wdo', feats_wdo, 'WDO')

# ─────────────────────────────────────────────
# 7. TESTE DE REVERSAO POR THRESHOLD
# ─────────────────────────────────────────────
print("\n" + "="*65)
print("TESTE DE REVERSAO — 10:30-12:00 apos distorcao na abertura")
print("="*65)

def test_reversion(res, label, post_col='actual_post'):
    print(f"\n  {label} — quando distorcao e grande, o mercado reverte?")
    print(f"  {'Threshold':>10} {'N sinais':>9} {'Win Rate':>9} {'Ret medio':>10} {'p-valor':>9} {'Conclusao'}")
    print(f"  {'-'*70}")

    results = []
    for z_thresh in [1.0, 1.5, 2.0, 2.5, 3.0]:
        sub = res.dropna(subset=[post_col, 'z_score'])

        # Distorcao positiva (mercado subiu demais) → esperamos queda no post
        pos_dist = sub[sub['z_score'] >= z_thresh]
        neg_dist = sub[sub['z_score'] <= -z_thresh]

        all_signals = pd.concat([
            pos_dist[[post_col]].assign(direction=-1),  # espera queda
            neg_dist[[post_col]].assign(direction=+1),  # espera subida
        ])

        if len(all_signals) < 5:
            continue

        all_signals['pnl'] = all_signals['direction'] * all_signals[post_col]
        wins    = (all_signals['pnl'] > 0).sum()
        wr      = wins / len(all_signals) * 100
        avg_ret = all_signals['pnl'].mean()
        _, pval = stats.ttest_1samp(all_signals['pnl'], 0)
        sig     = "***FORTE" if pval<0.01 and wr>55 else "** ok" if pval<0.05 else "*  fraco" if pval<0.1 else "   ruido"

        print(f"  |Z| > {z_thresh:.1f}    {len(all_signals):>9}  {wr:>8.1f}%  {avg_ret:>+9.4f}%  {pval:>9.4f}  {sig}")
        results.append({'z_thresh': z_thresh, 'n': len(all_signals),
                        'wr': wr, 'avg_ret': avg_ret, 'pval': pval})
    return pd.DataFrame(results)

rev_win = test_reversion(res_win, 'WIN')
rev_wdo = test_reversion(res_wdo, 'WDO')

# ─────────────────────────────────────────────
# 8. ANALISE POR DIA DA SEMANA
# ─────────────────────────────────────────────
print("\n" + "="*65)
print("DISTORCAO POR DIA DA SEMANA")
print("="*65)
dias = ['Seg','Ter','Qua','Qui','Sex']
for res, label in [(res_win,'WIN'),(res_wdo,'WDO')]:
    if res is None: continue
    print(f"\n  {label}:")
    for dow in range(5):
        sub = res[res.index.dayofweek == dow].dropna(subset=['actual_post','z_score'])
        if len(sub) < 10: continue
        high_dist = sub[abs(sub['z_score']) >= 1.5]
        if len(high_dist) < 5: continue
        high_dist = high_dist.copy()
        high_dist['pnl'] = -np.sign(high_dist['z_score']) * high_dist['actual_post']
        wr = (high_dist['pnl'] > 0).mean() * 100
        print(f"    {dias[dow]}: {len(high_dist):3d} sinais | Win Rate {wr:.1f}% | Ret medio {high_dist['pnl'].mean():+.4f}%")

# ─────────────────────────────────────────────
# 9. SALVA RESULTADOS
# ─────────────────────────────────────────────
if res_win is not None:
    res_win.to_csv(f"{RESULTS_DIR}/win_distortion.csv")
if res_wdo is not None:
    res_wdo.to_csv(f"{RESULTS_DIR}/wdo_distortion.csv")

print("\n\nArquivos salvos em C:/estrategia/results/")
print(f"  win_distortion.csv — Z-score e distorcao diaria do WIN")
print(f"  wdo_distortion.csv — Z-score e distorcao diaria do WDO")
