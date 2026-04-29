"""
Sincronizacao de dados B3 + Global em M15
Janela de analise: 09:00 - 10:30 BRT (horario de Brasilia)
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

# ─────────────────────────────────────────────
# 1. CARREGA CSVs
# ─────────────────────────────────────────────
def load_csv(path, name):
    df = pd.read_csv(path, parse_dates=['time'])
    df = df.set_index('time').sort_index()
    df.index.name = 'time'
    return df[['open','high','low','close','volume']].rename(
        columns={c: f"{name}_{c}" for c in ['open','high','low','close','volume']}
    )

print("[1/5] Carregando dados...")

b3 = {
    'win':   load_csv(f"{DATA_DIR}/xp_win_m15.csv",   'win'),
    'wdo':   load_csv(f"{DATA_DIR}/xp_wdo_m15.csv",   'wdo'),
    'petr4': load_csv(f"{DATA_DIR}/xp_petr4_m15.csv", 'petr4'),
    'di1':   load_csv(f"{DATA_DIR}/xp_di1_m15.csv",   'di1'),
}

glb = {
    'spx':    load_csv(f"{DATA_DIR}/infinox_spx500_m15.csv", 'spx'),
    'oil':    load_csv(f"{DATA_DIR}/infinox_oil_m15.csv",    'oil'),
    'gold':   load_csv(f"{DATA_DIR}/infinox_gold_m15.csv",   'gold'),
    'nas100': load_csv(f"{DATA_DIR}/infinox_nas100_m15.csv", 'nas100'),
    'audusd': load_csv(f"{DATA_DIR}/infinox_audusd_m15.csv", 'audusd'),
    'usdmxn': load_csv(f"{DATA_DIR}/infinox_usdmxn_m15.csv",'usdmxn'),
    'eurusd': load_csv(f"{DATA_DIR}/infinox_eurusd_m15.csv",'eurusd'),
}

# ─────────────────────────────────────────────
# 2. DETECTA TIMEZONE AUTOMATICAMENTE
# ─────────────────────────────────────────────
print("\n[2/5] Detectando timezones dos terminais...")

# WIN opera 09:00-18:00 BRT = 12:00-21:00 UTC
win_hours = b3['win'].index.hour.value_counts().sort_index()
peak_hour_win = win_hours.idxmax()
print(f"   XP  WIN  - hora com mais bars: {peak_hour_win:02d}h")
# se peak_hour_win == 9  → armazenou em BRT (UTC-3) → offset = 0
# se peak_hour_win == 12 → armazenou em UTC         → offset = -3 (converte p/ BRT)

spx_hours = glb['spx'].index.hour.value_counts().sort_index()
peak_hour_spx = spx_hours.idxmax()
print(f"   Infinox SPX - hora com mais bars: {peak_hour_spx:02d}h")
# SPX opera 14:30-21:00 UTC = 11:30-18:00 BRT

# XP: B3 opera 09:00-18:00 BRT
# Se XP armazena em BRT -> hora pico WIN ~ 10-14h
# Se XP armazena em UTC -> hora pico WIN ~ 13-17h
if peak_hour_win <= 11:
    xp_utc_offset = 0    # ja esta em BRT
    xp_label = "BRT (UTC-3) - sem ajuste"
else:
    xp_utc_offset = -3   # esta em UTC, converte para BRT
    xp_label = "UTC - convertendo para BRT (-3h)"

# Infinox: geralmente UTC+2 ou UTC+0
# SPX opera 14:30-21:00 UTC = 16:30-23:00 UTC+2
if peak_hour_spx >= 15:
    inf_utc_offset = -2  # esta em UTC+2, converte para BRT (UTC-3) = -5h do UTC+2
    inf_label = "UTC+2 - convertendo para BRT (-5h)"
elif peak_hour_spx >= 12:
    inf_utc_offset = -3  # esta em UTC, converte para BRT
    inf_label = "UTC - convertendo para BRT (-3h)"
else:
    inf_utc_offset = 0
    inf_label = "BRT - sem ajuste"

print(f"   XP ajuste:      {xp_label}")
print(f"   Infinox ajuste: {inf_label}")

# ─────────────────────────────────────────────
# 3. CONVERTE PARA BRT E FILTRA 09:00-10:30
# ─────────────────────────────────────────────
print("\n[3/5] Convertendo para BRT e filtrando 09:00-10:30...")

def adjust_tz(df, offset_h):
    df = df.copy()
    df.index = df.index + pd.Timedelta(hours=offset_h)
    return df

for key in b3:
    b3[key] = adjust_tz(b3[key], xp_utc_offset)
for key in glb:
    glb[key] = adjust_tz(glb[key], inf_utc_offset)

# Mostra distribuicao de horas pos-ajuste
print(f"   WIN horas disponiveis pos-ajuste: {sorted(b3['win'].index.hour.unique().tolist())}")
print(f"   SPX horas disponiveis pos-ajuste: {sorted(glb['spx'].index.hour.unique().tolist())}")

# Filtra janela 09:00-10:30 BRT (inclui candles: 09:00, 09:15, 09:30, 09:45, 10:00, 10:15 = 6 candles M15)
def filter_window(df, h_start=9, h_end=10, m_end=30):
    mask = (
        (df.index.hour > h_start) |
        ((df.index.hour == h_start) & (df.index.minute >= 0))
    ) & (
        (df.index.hour < h_end) |
        ((df.index.hour == h_end) & (df.index.minute <= m_end))
    )
    return df[mask]

win_window   = filter_window(b3['win'])
wdo_window   = filter_window(b3['wdo'])
petr4_window = filter_window(b3['petr4'])
di1_window   = filter_window(b3['di1'])

print(f"   WIN  candles na janela 09:00-10:30: {len(win_window):,}")
print(f"   WDO  candles na janela 09:00-10:30: {len(wdo_window):,}")
print(f"   Horas cobertas: {sorted(win_window.index.hour.unique().tolist())}")

# ─────────────────────────────────────────────
# 4. MONTA RETORNOS DIARIOS DA JANELA
# ─────────────────────────────────────────────
print("\n[4/5] Calculando retornos da janela por dia...")

def window_return(df, price_col):
    """Retorno do dia = (close 10:30 - open 09:00) / open 09:00"""
    df_close = df.groupby(df.index.date)[price_col].last()   # close 10:30
    df_open  = df.groupby(df.index.date)[price_col].first()  # open 09:00
    ret = (df_close - df_open) / df_open * 100
    ret.index = pd.DatetimeIndex(ret.index)
    return ret

def overnight_return(df_global, price_col, b3_open_hour=9):
    """Retorno overnight = preco global no momento do open B3 vs fechamento anterior"""
    # Pega o valor mais proximo do open da B3 (09:00 BRT)
    at_open = df_global.between_time('09:00', '09:15')[price_col].groupby(
        df_global.between_time('09:00', '09:15').index.date
    ).first()
    at_open.index = pd.DatetimeIndex(at_open.index)
    ret = at_open.pct_change() * 100
    return ret

# Retornos da janela B3
ret_win   = window_return(win_window,   'win_close')
ret_wdo   = window_return(wdo_window,   'wdo_close')
ret_petr4 = window_return(petr4_window, 'petr4_close')
ret_di1   = window_return(di1_window,   'di1_close')

# Retornos overnight dos ativos globais
ret_spx    = overnight_return(glb['spx'],    'spx_close')
ret_oil    = overnight_return(glb['oil'],    'oil_close')
ret_gold   = overnight_return(glb['gold'],   'gold_close')
ret_nas100 = overnight_return(glb['nas100'], 'nas100_close')
ret_audusd = overnight_return(glb['audusd'], 'audusd_close')
ret_usdmxn = overnight_return(glb['usdmxn'], 'usdmxn_close')

# Monta DataFrame unificado
df_all = pd.DataFrame({
    'win':    ret_win,
    'wdo':    ret_wdo,
    'petr4':  ret_petr4,
    'di1':    ret_di1,
    'spx':    ret_spx,
    'oil':    ret_oil,
    'gold':   ret_gold,
    'nas100': ret_nas100,
    'audusd': ret_audusd,
    'usdmxn': ret_usdmxn,
}).dropna()

df_all.to_csv(f"{RESULTS_DIR}/janela_09_1030_returns.csv")
print(f"   Dias validos com dados completos: {len(df_all)}")
print(f"   Periodo: {df_all.index[0].date()} -> {df_all.index[-1].date()}")

# ─────────────────────────────────────────────
# 5. CORRELACOES E MODELO NA JANELA 09-10:30
# ─────────────────────────────────────────────
print("\n[5/5] Analise de correlacoes e modelo fatorial...")
print("\n" + "="*60)
print("CORRELACOES NA JANELA 09:00-10:30 BRT")
print("="*60)

targets  = ['win', 'wdo']
features = ['spx', 'oil', 'gold', 'nas100', 'audusd', 'usdmxn', 'petr4', 'di1']

for t in targets:
    print(f"\n  {t.upper()} (retorno 09:00-10:30) correlaciona com:")
    corrs = []
    for f in features:
        c  = df_all[t].corr(df_all[f])
        p  = stats.pearsonr(df_all[t].dropna(), df_all[f].dropna())[1]
        corrs.append((f, c, p))
    corrs.sort(key=lambda x: abs(x[1]), reverse=True)

    for name, c, p in corrs:
        sig  = "***" if p < 0.01 else "** " if p < 0.05 else "*  " if p < 0.1 else "   "
        bar  = '#' * int(abs(c) * 30)
        sinal= '+' if c > 0 else '-'
        print(f"    {name:<10} {sinal}{abs(c):.3f} {sig} p={p:.3f}  {bar}")

print("\n  Legenda: *** p<0.01 (altamente significativo)")
print("           **  p<0.05  *  p<0.10")

# ── Regressao multivariada WIN ────────────────
print("\n" + "="*60)
print("REGRESSAO MULTIVARIADA — WIN 09:00-10:30")
print("="*60)

for target in ['win', 'wdo']:
    feat_cols = ['spx', 'oil', 'gold', 'nas100', 'audusd', 'usdmxn']
    X = df_all[feat_cols].values
    y = df_all[target].values

    model = LinearRegression().fit(X, y)
    r2    = model.score(X, y)

    print(f"\n  Modelo {target.upper()}:")
    print(f"  R2 = {r2:.3f} ({r2*100:.1f}% do movimento explicado pelos drivers globais)")
    print(f"  Coeficientes (impacto de +1% no driver sobre {target.upper()}):")
    for name, coef in sorted(zip(feat_cols, model.coef_), key=lambda x: abs(x[1]), reverse=True):
        bar  = '#' * int(abs(coef) * 20)
        sinal= '+' if coef > 0 else '-'
        print(f"    {name:<10} {sinal}{abs(coef):.3f}%   {bar}")

# ── Estatisticas descritivas da janela ────────
print("\n" + "="*60)
print("ESTATISTICAS DA JANELA 09:00-10:30 (por ativo B3)")
print("="*60)
for t in ['win', 'wdo']:
    s = df_all[t]
    pos = (s > 0).sum()
    neg = (s < 0).sum()
    print(f"\n  {t.upper()}:")
    print(f"    Media     : {s.mean():.4f}%")
    print(f"    Desvio    : {s.std():.4f}%")
    print(f"    Min/Max   : {s.min():.3f}% / {s.max():.3f}%")
    print(f"    Dias +     : {pos} ({pos/len(s)*100:.1f}%)")
    print(f"    Dias -     : {neg} ({neg/len(s)*100:.1f}%)")
    print(f"    Sharpe aprox: {s.mean()/s.std()*np.sqrt(252):.2f}")

print(f"\nArquivo salvo: {RESULTS_DIR}/janela_09_1030_returns.csv")
