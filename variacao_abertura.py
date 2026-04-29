"""
Analise de Variacao da Abertura — WIN M1 09:00-10:30
Pergunta: quando o WIN atinge X pontos do open, compra ou vende?
Metodo: para cada nivel de variacao, calcula win rate de compra e venda
        medido da primeira vez que o preco atinge esse nivel ate 10:30
"""
import pandas as pd
import numpy as np
from scipy import stats
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RESULTS_DIR = "C:/estrategia/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Carrega e filtra janela ─────────────────────────────────────
print("Carregando WIN M1...")
df = pd.read_csv("C:/estrategia/data/xp_win_m1.csv", parse_dates=['time'])
df = df.set_index('time').sort_index()
df_win = df.between_time('09:00','10:30')
dias = sorted(set(df_win.index.date))
print(f"  {len(dias)} dias | {dias[0]} -> {dias[-1]}\n")

# ── Niveis de variacao a testar (pontos do open) ────────────────
NIVEIS = [-1500,-1200,-1000,-800,-600,-500,-400,-300,-200,-150,
          -100,-50,50,100,150,200,300,400,500,600,800,1000,1200,1500]

# ── Para cada nivel: acha o primeiro toque e o resultado ────────
print("Calculando primeiro toque em cada nivel de variacao...")

resultado = {n: {'compra': [], 'venda': [], 'minuto': []} for n in NIVEIS}

for dia in dias:
    d = df_win[df_win.index.date == dia].copy()

    c0900 = d.between_time('09:00','09:00')
    c1030 = d.between_time('10:29','10:30')
    if len(c0900) == 0 or len(c1030) == 0:
        continue

    open_0900  = c0900['open'].iloc[0]
    close_1030 = c1030['close'].iloc[-1]

    # Variacao maxima e minima do dia na janela
    var_max = d['high'].max() - open_0900
    var_min = d['low'].min()  - open_0900

    for nivel in NIVEIS:
        # Verifica se o nivel foi tocado
        if nivel > 0 and var_max < nivel:
            continue
        if nivel < 0 and var_min > nivel:
            continue

        # Preco alvo do nivel
        preco_alvo = open_0900 + nivel

        # Acha o primeiro candle que toca o nivel
        if nivel > 0:
            toque = d[d['high'] >= preco_alvo]
        else:
            toque = d[d['low']  <= preco_alvo]

        if len(toque) == 0:
            continue

        # Minuto do primeiro toque
        primeiro = toque.index[0]
        min_toque = (primeiro.hour - 9) * 60 + primeiro.minute

        # Preco de entrada = preco_alvo (preenchimento exato no nivel)
        entry = preco_alvo

        # Retorno de entrada ate 10:30
        ret_pts = close_1030 - entry   # positivo = preco subiu

        resultado[nivel]['compra'].append(ret_pts)    # ganho se comprou
        resultado[nivel]['venda'].append(-ret_pts)    # ganho se vendeu
        resultado[nivel]['minuto'].append(min_toque)

# ── Monta tabela de resultados ──────────────────────────────────
print("\n" + "="*80)
print("VARIACAO DO OPEN vs MELHOR ACAO — WIN 09:00-10:30")
print("Resultado medido do primeiro toque no nivel ate o fechamento 10:30")
print("="*80)
print(f"\n  {'Variacao':>10}  {'N dias':>7}  {'Min medio':>10}  "
      f"{'WR Compra':>10}  {'WR Venda':>9}  {'Ret C':>8}  {'Ret V':>8}  {'MELHOR':>8}  Sig")
print(f"  {'-'*88}")

rows = []
for nivel in sorted(NIVEIS):
    r = resultado[nivel]
    n = len(r['compra'])
    if n < 15:
        continue

    arr_c = np.array(r['compra'])
    arr_v = np.array(r['venda'])
    mins  = np.array(r['minuto'])

    wr_c  = (arr_c > 0).mean() * 100
    wr_v  = (arr_v > 0).mean() * 100
    ret_c = arr_c.mean()
    ret_v = arr_v.mean()
    min_m = mins.mean()

    # Teste estatistico
    melhor_arr = arr_c if wr_c > wr_v else arr_v
    _, p = stats.ttest_1samp(melhor_arr, 0)
    sig  = "***" if p<0.01 else "** " if p<0.05 else "*  " if p<0.1 else "   "

    melhor = "COMPRA" if wr_c > wr_v else "VENDA "
    acao_icon = "^ COMPRA ^" if wr_c > wr_v else "v VENDA  v"

    destaque = " <<<<" if max(wr_c, wr_v) >= 55 else ""

    print(f"  {nivel:>+10}  {n:>7}  {min_m:>9.1f}m  "
          f"{wr_c:>9.1f}%  {wr_v:>8.1f}%  "
          f"{ret_c:>+7.0f}  {ret_v:>+7.0f}  "
          f"{melhor:>8}  {sig}{destaque}")

    rows.append({'nivel': nivel, 'n': n, 'min_medio': min_m,
                 'wr_compra': wr_c, 'wr_venda': wr_v,
                 'ret_compra': ret_c, 'ret_venda': ret_v,
                 'melhor': melhor, 'pval': p})

df_res = pd.DataFrame(rows)
df_res.to_csv(f"{RESULTS_DIR}/variacao_abertura.csv", index=False)

# ── Resumo executivo ────────────────────────────────────────────
print("\n" + "="*80)
print("RESUMO — REGRAS CLARAS DE ENTRADA")
print("="*80)

# Compras (niveis negativos com WR_compra alto)
print("\n  COMPRA — quando WIN cai X pontos do open:")
comp = df_res[(df_res['nivel'] < 0) & (df_res['wr_compra'] > df_res['wr_venda'])].sort_values('nivel')
for _, r in comp.iterrows():
    bar = '#' * int(r['wr_compra'] / 5)
    print(f"    {r['nivel']:>+6} pts  |  WR {r['wr_compra']:.1f}%  {bar}  "
          f"RetMed {r['ret_compra']:>+5.0f}pts  ~{r['min_medio']:.0f}min apos open")

print("\n  VENDA — quando WIN sobe X pontos do open:")
vend = df_res[(df_res['nivel'] > 0) & (df_res['wr_venda'] > df_res['wr_compra'])].sort_values('nivel')
for _, r in vend.iterrows():
    bar = '#' * int(r['wr_venda'] / 5)
    print(f"    {r['nivel']:>+6} pts  |  WR {r['wr_venda']:.1f}%  {bar}  "
          f"RetMed {r['ret_venda']:>+5.0f}pts  ~{r['min_medio']:.0f}min apos open")

# ── Analise por dia da semana nos melhores niveis ───────────────
print("\n" + "="*80)
print("ANALISE POR DIA DA SEMANA — NIVEIS COM MAIOR EDGE")
print("="*80)

top_niveis = df_res.copy()
top_niveis['wr_max'] = top_niveis[['wr_compra','wr_venda']].max(axis=1)
top_niveis = top_niveis.nlargest(6,'wr_max')

DIAS = ['Seg','Ter','Qua','Qui','Sex']

for _, r in top_niveis.sort_values('nivel').iterrows():
    nivel = int(r['nivel'])
    melhor = r['melhor']
    print(f"\n  Nivel {nivel:>+5} pts → {melhor}  (WR geral {r['wr_max']:.1f}%)")
    print(f"  {'Dia':>5}  {'N':>5}  {'WR%':>7}  {'RetMed':>8}")

    rr = resultado[nivel]
    arr_entry = np.array(rr['compra'] if melhor=='COMPRA' else rr['venda'])

    # Precisa reconstruir por dia da semana
    dias_validos = []
    for dia in dias:
        d = df_win[df_win.index.date == dia].copy()
        c0900 = d.between_time('09:00','09:00')
        c1030 = d.between_time('10:29','10:30')
        if len(c0900)==0 or len(c1030)==0: continue
        open_0900  = c0900['open'].iloc[0]
        close_1030 = c1030['close'].iloc[-1]
        preco_alvo = open_0900 + nivel
        toque = d[d['high'] >= preco_alvo] if nivel > 0 else d[d['low'] <= preco_alvo]
        if len(toque)==0: continue
        entry   = preco_alvo
        ret_pts = close_1030 - entry
        pnl     = ret_pts if melhor=='COMPRA' else -ret_pts
        dias_validos.append({'dow': pd.Timestamp(dia).dayofweek, 'pnl': pnl})

    if not dias_validos: continue
    df_dow = pd.DataFrame(dias_validos)
    for dow, nome in enumerate(DIAS):
        sub = df_dow[df_dow['dow']==dow]['pnl']
        if len(sub) < 5: continue
        wr = (sub > 0).mean() * 100
        print(f"  {nome:>5}  {len(sub):>5}  {wr:>6.1f}%  {sub.mean():>+7.0f}pts")
