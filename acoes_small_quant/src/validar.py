"""
Script de validação end-to-end do SmallQuant BR.
Roda: coleta → beta → z-score → regime → scanner → backteste → métricas
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import sys

from coleta import baixar_etfs_setoriais, baixar_indices, baixar_acoes_smll
from smll_composicao import todos_os_tickers, SMLL_COMPOSICAO
from beta import calcular_retornos, beta_todos
from distorcao import calcular_distorcoes, calcular_zscore_peer, snapshot_atual
from momentum import regime_macro_ok, setores_ativos, resumo_regime, modo_mercado
from backteste import rodar_backteste
from metricas import resumo_metricas, retorno_por_setor, equity_curve


SEP = "-" * 60


def ok(msg): print(f"  [OK]  {msg}")
def erro(msg): print(f"  [ERRO]  {msg}")
def info(msg): print(f"  -->  {msg}")
def titulo(msg): print(f"\n{SEP}\n  {msg}\n{SEP}")


# ── 1. COLETA ────────────────────────────────────────────────
titulo("ETAPA 1 — Coleta de Dados")

print("\n[ETFs Setoriais EUA]")
try:
    etfs = baixar_etfs_setoriais(periodo="1y")
    ok(f"{etfs.shape[1]} ETFs carregados | {etfs.shape[0]} dias")
    nulos = etfs.isnull().sum()
    if nulos.any():
        info(f"ETFs com dados faltantes: {nulos[nulos > 0].to_dict()}")
except Exception as e:
    erro(f"Falha ETFs: {e}")
    sys.exit(1)

print("\n[Índices]")
try:
    indices = baixar_indices(periodo="1y")
    ok(f"{indices.shape[1]} índices carregados")
    faltando = [c for c in ["ibov","smll","russell","vix","usdbrl"] if c not in indices.columns]
    if faltando:
        erro(f"Índices ausentes: {faltando}")
    else:
        ok("Todos os índices presentes")
except Exception as e:
    erro(f"Falha índices: {e}")
    sys.exit(1)

print("\n[Ações SMLL]")
try:
    tickers = todos_os_tickers()
    acoes = baixar_acoes_smll(tickers, periodo="1y")
    n_ok  = acoes.shape[1]
    n_tot = len(tickers)
    ok(f"{n_ok}/{n_tot} ações carregadas com dados")

    # Tickers que não vieram
    ausentes = [t + ".SA" for t in tickers if (t + ".SA") not in acoes.columns]
    if ausentes:
        info(f"Tickers sem dados ({len(ausentes)}): {', '.join(ausentes)}")

    # Tickers com muitos nulos
    cobertura = (acoes.notna().mean() * 100).round(1)
    ruins = cobertura[cobertura < 70]
    if not ruins.empty:
        info(f"Tickers com cobertura < 70%: {ruins.to_dict()}")
except Exception as e:
    erro(f"Falha ações SMLL: {e}")
    sys.exit(1)


# ── 2. BETA E Z-SCORE ────────────────────────────────────────
titulo("ETAPA 2 — Beta Rolling e Z-score")

try:
    ret_acoes   = calcular_retornos(acoes)
    ret_indices = calcular_retornos(indices)
    ret_ibov    = ret_indices["ibov"].dropna()

    betas        = beta_todos(ret_acoes, ret_ibov)
    zscores      = calcular_distorcoes(ret_acoes, ret_ibov, betas)
    zscores_peer = calcular_zscore_peer(ret_acoes, SMLL_COMPOSICAO)

    ok(f"Betas calculados para {betas.shape[1]} acoes")
    ok(f"Z-scores (IBOV) para {zscores.shape[1]} acoes")
    ok(f"Z-scores (peer) para {zscores_peer.shape[1]} acoes")

    snap = snapshot_atual(zscores, betas, zscores_peer)
    snap.index.name = "ticker"
    snap["setor"] = snap.index.map(
        lambda t: SMLL_COMPOSICAO.get(t.replace(".SA", ""), "Desconhecido")
    )

    print(f"\n  Top 5 distorcoes vs IBOV [BULL MODE]:")
    top5 = snap.nsmallest(5, "zscore")[["zscore", "zscore_peer", "beta", "setor"]]
    for ticker, row in top5.iterrows():
        print(f"    {ticker:<12} z_ibov={row['zscore']:+.2f}  z_peer={row['zscore_peer']:+.2f}  [{row['setor']}]")

    print(f"\n  Top 5 forca relativa vs peers [BEAR MODE]:")
    top5b = snap.nlargest(5, "zscore_peer")[["zscore", "zscore_peer", "beta", "setor"]]
    for ticker, row in top5b.iterrows():
        print(f"    {ticker:<12} z_ibov={row['zscore']:+.2f}  z_peer={row['zscore_peer']:+.2f}  [{row['setor']}]")

except Exception as e:
    erro(f"Falha beta/z-score: {e}")
    sys.exit(1)


# ── 3. REGIME E SETORES ──────────────────────────────────────
titulo("ETAPA 3 — Regime Macro e Setores Ativos")

try:
    spy     = indices["spy"] if "spy" in indices.columns else None
    regime  = regime_macro_ok(indices)
    modo    = modo_mercado(regime)
    setores = setores_ativos(etfs, regime, spy)
    resumo_regime(regime, setores, modo)

    n_ativos = sum(v for v in setores.values())
    info(f"{n_ativos}/11 setores com fator global ativo hoje")
except Exception as e:
    erro(f"Falha regime/setores: {e}")
    sys.exit(1)


# ── 4. SCANNER SEMANAL ───────────────────────────────────────
titulo("ETAPA 4 — Carteira da Semana Atual")

try:
    snap["setor_ativo"]   = snap["setor"].map(setores).fillna(False)
    snap["distorcao_flag"] = snap["zscore"] < -1.0

    candidatas = snap[snap["setor_ativo"] & snap["distorcao_flag"]].sort_values("zscore").reset_index()

    if candidatas.empty:
        info("Nenhuma candidata esta semana (regime ou setores sem sinal).")
    else:
        carteira = (
            candidatas
            .groupby("setor", group_keys=False)
            .apply(lambda g: g.nsmallest(1, "zscore"))
            .reset_index(drop=True)
        )
        ok(f"{len(carteira)} ações selecionadas para a carteira desta semana:")
        print()
        print(f"  {'TICKER':<12} {'SETOR':<25} {'Z-SCORE':>8} {'BETA':>6}")
        print(f"  {'-'*12} {'-'*25} {'-'*8} {'-'*6}")
        for _, row in carteira.iterrows():
            print(f"  {row['ticker']:<12} {row['setor']:<25} {row['zscore']:>+8.2f} {row['beta']:>6.2f}")
except Exception as e:
    erro(f"Falha scanner: {e}")
    sys.exit(1)


# ── 5. BACKTESTE ─────────────────────────────────────────────
titulo("ETAPA 5 — Backteste Walk-Forward (1 ano)")

try:
    trades, equity = rodar_backteste(
        acoes, indices, etfs,
        inicio=str((pd.Timestamp.today() - pd.DateOffset(years=1)).date()),
        fim=str(pd.Timestamp.today().date()),
        dias_hold=5,
    )

    if trades.empty:
        info("Nenhum trade gerado — regime macro pode ter ficado inativo no período.")
    else:
        metricas = resumo_metricas(trades, equity, indices["ibov"], indices["smll"])

        print()
        print(f"  {'MÉTRICA':<25} {'VALOR':>12}")
        print(f"  {'-'*25} {'-'*12}")
        for k, v in metricas.items():
            print(f"  {k:<25} {v:>12}")

        por_setor = retorno_por_setor(trades)
        if not por_setor.empty:
            print(f"\n  Retorno médio por setor:")
            print(f"  {'SETOR':<25} {'RET MÉDIO':>10} {'TRADES':>7} {'WIN%':>6}")
            print(f"  {'-'*25} {'-'*10} {'-'*7} {'-'*6}")
            for setor, row in por_setor.iterrows():
                print(f"  {setor:<25} {row['ret_medio']:>+10.2%} {int(row['n_trades']):>7} {row['win_rate']:>6.0%}")

        curve = equity_curve(equity)
        print(f"\n  Equity curve: {curve.iloc[0]:.3f} >> {curve.iloc[-1]:.3f}  ({(curve.iloc[-1]-1)*100:+.1f}%)")
        print(f"  Semanas com posição: {(equity != 0).sum()} de {len(equity)}")

except Exception as e:
    erro(f"Falha backteste: {e}")
    import traceback; traceback.print_exc()


# ── FIM ──────────────────────────────────────────────────────
titulo("VALIDAÇÃO CONCLUÍDA")
print()
