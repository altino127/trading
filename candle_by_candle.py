"""
Analise candle a candle M1 — WIN 09:00 a 10:30
Para cada minuto: variacao acumulada desde o open e win rate de compra/venda
"""
import pandas as pd
import numpy as np
from scipy import stats
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RESULTS_DIR = "C:/estrategia/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Carrega M1 ──────────────────────────────────────────────────
print("Carregando WIN M1...")
df = pd.read_csv("C:/estrategia/data/xp_win_m1.csv", parse_dates=['time'])
df = df.set_index('time').sort_index()
df_win = df.between_time('09:00', '10:30')
dias = sorted(set(df_win.index.date))
print(f"  {len(dias)} dias | {dias[0]} -> {dias[-1]}\n")

# ── Monta matriz: linha = dia, coluna = minuto ──────────────────
# Para cada dia e cada minuto, armazena:
#   var_pts  = close_t - open_0900   (variacao acumulada desde o open)
#   ret_fwd  = close_1030 - close_t  (quanto ainda move ate o fim)

print("Construindo matriz minuto a minuto...")

MINUTOS = list(range(0, 91))   # 0 = 09:00, 90 = 10:30

rows_var = []   # variacao acumulada em pontos
rows_fwd = []   # retorno daqui ate 10:30 em pontos

for dia in dias:
    d = df_win[df_win.index.date == dia]

    c0900 = d.between_time('09:00','09:00')
    c1030 = d.between_time('10:29','10:30')
    if len(c0900) == 0 or len(c1030) == 0:
        continue

    open_0900  = c0900['open'].iloc[0]
    close_1030 = c1030['close'].iloc[-1]

    row_var = {'date': dia}
    row_fwd = {'date': dia}

    for m in MINUTOS:
        h  = 9 + m // 60
        mi = m % 60
        t  = f"{h:02d}:{mi:02d}"

        candle = d.between_time(t, t)
        if len(candle) == 0:
            row_var[f't{m:03d}'] = np.nan
            row_fwd[f't{m:03d}'] = np.nan
            continue

        price_t = candle['close'].iloc[-1]
        row_var[f't{m:03d}'] = price_t - open_0900          # var acumulada desde open
        row_fwd[f't{m:03d}'] = close_1030 - price_t         # pontos restantes ate 10:30

    rows_var.append(row_var)
    rows_fwd.append(row_fwd)

df_var = pd.DataFrame(rows_var).set_index('date')
df_fwd = pd.DataFrame(rows_fwd).set_index('date')

print(f"  {len(df_var)} dias validos\n")

# ── Analise por minuto ──────────────────────────────────────────
print("="*75)
print("PERFIL MINUTO A MINUTO — WIN 09:00 a 10:30")
print("Variacao acumulada desde o open de 09:00 (em pontos)")
print("="*75)
print(f"\n  {'Min':>4}  {'Hora':>5}  {'VarMed':>8}  {'VarP25':>8}  {'VarP75':>8}  "
      f"{'WR_Buy%':>8}  {'WR_Sell%':>9}  {'Melhor':>10}  p-val")
print(f"  {'-'*80}")

resultados = []

for m in MINUTOS:
    col = f't{m:03d}'
    if col not in df_var.columns:
        continue

    h  = 9 + m // 60
    mi = m % 60

    var  = df_var[col].dropna()
    fwd  = df_fwd[col].dropna()

    # Alinha indices
    idx  = var.index.intersection(fwd.index)
    var  = var[idx]
    fwd  = fwd[idx]

    if len(var) < 50:
        continue

    var_med = var.median()
    var_p25 = var.quantile(0.25)
    var_p75 = var.quantile(0.75)

    # Win rate COMPRA no minuto m: fwd > 0 (preco sobe daqui ate 10:30)
    wr_buy  = (fwd > 0).mean() * 100

    # Win rate VENDA no minuto m: fwd < 0 (preco cai daqui ate 10:30)
    wr_sell = (fwd < 0).mean() * 100

    # Teste t: retorno forward e diferente de zero?
    _, p = stats.ttest_1samp(fwd, 0)

    melhor = "COMPRA" if wr_buy > wr_sell else "VENDA "
    sig    = "***" if p < 0.01 else "** " if p < 0.05 else "*  " if p < 0.1 else "   "

    print(f"  {m:>4}  {h:02d}:{mi:02d}  {var_med:>+8.0f}  {var_p25:>+8.0f}  {var_p75:>+8.0f}  "
          f"{wr_buy:>7.1f}%  {wr_sell:>8.1f}%  {melhor:>10}  {sig} {p:.3f}")

    resultados.append({
        'minuto': m, 'hora': f'{h:02d}:{mi:02d}',
        'var_med': var_med, 'var_p25': var_p25, 'var_p75': var_p75,
        'wr_buy': wr_buy, 'wr_sell': wr_sell,
        'melhor': melhor, 'pval': p, 'n': len(var)
    })

df_res = pd.DataFrame(resultados)
df_res.to_csv(f"{RESULTS_DIR}/win_candle_profile.csv", index=False)

# ── Melhores momentos de compra e venda ─────────────────────────
print("\n" + "="*75)
print("MELHORES MOMENTOS DE COMPRA (maior win rate longo)")
print("="*75)
top_buy = df_res.nlargest(10, 'wr_buy')[['hora','var_med','wr_buy','wr_sell','pval']]
for _, r in top_buy.iterrows():
    print(f"  {r['hora']}  var={r['var_med']:>+6.0f}pts  "
          f"WR_Buy={r['wr_buy']:.1f}%  WR_Sell={r['wr_sell']:.1f}%  p={r['pval']:.3f}")

print("\n" + "="*75)
print("MELHORES MOMENTOS DE VENDA (maior win rate curto)")
print("="*75)
top_sell = df_res.nlargest(10, 'wr_sell')[['hora','var_med','wr_buy','wr_sell','pval']]
for _, r in top_sell.iterrows():
    print(f"  {r['hora']}  var={r['var_med']:>+6.0f}pts  "
          f"WR_Buy={r['wr_buy']:.1f}%  WR_Sell={r['wr_sell']:.1f}%  p={r['pval']:.3f}")

# ── Analise por faixa de variacao em cada minuto chave ──────────
print("\n" + "="*75)
print("FAIXAS DE VARIACAO x WIN RATE — MINUTOS CHAVE")
print("Para cada faixa de variacao acumulada, qual o acerto de compra/venda?")
print("="*75)

for m in [5, 10, 15, 20, 30]:
    col_v = f't{m:03d}'
    col_f = f't{m:03d}'
    if col_v not in df_var.columns:
        continue

    h  = 9 + m // 60
    mi = m % 60

    df_m = pd.DataFrame({
        'var': df_var[col_v],
        'fwd': df_fwd[col_f]
    }).dropna()

    print(f"\n  {h:02d}:{mi:02d} (min {m}) — {len(df_m)} dias")
    print(f"  {'Faixa (pts)':>22}  {'N':>5}  {'WR_Buy%':>8}  {'WR_Sell%':>9}  {'Melhor':>10}  RetMedio")
    print(f"  {'-'*72}")

    bins = [
        (-9999, -600, "queda forte >600"),
        (-600,  -400, "queda 400-600"),
        (-400,  -250, "queda 250-400"),
        (-250,  -150, "queda 150-250"),
        (-150,   -80, "queda 80-150"),
        ( -80,     0, "queda <80"),
        (   0,    80, "alta <80"),
        (  80,   150, "alta 80-150"),
        ( 150,   250, "alta 150-250"),
        ( 250,   400, "alta 250-400"),
        ( 400,   600, "alta 400-600"),
        ( 600,  9999, "alta forte >600"),
    ]

    for lo, hi, label in bins:
        sub = df_m[(df_m['var'] >= lo) & (df_m['var'] < hi)]
        if len(sub) < 8:
            continue

        wr_b = (sub['fwd'] > 0).mean() * 100
        wr_s = (sub['fwd'] < 0).mean() * 100
        med  = sub['fwd'].mean()
        melhor = "COMPRA" if wr_b > wr_s else "VENDA "
        destaque = " <--" if abs(wr_b - 50) > 8 or abs(wr_s - 50) > 8 else ""

        print(f"  {label:>22}  {len(sub):>5}  {wr_b:>7.1f}%  {wr_s:>8.1f}%  "
              f"{melhor:>10}  {med:>+7.0f}pts{destaque}")
