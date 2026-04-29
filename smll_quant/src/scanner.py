import pandas as pd
import numpy as np
from beta import calcular_retornos, beta_todos
from distorcao import (
    calcular_distorcoes, calcular_zscore_peer,
    calcular_volatilidade, classificar_risco, snapshot_atual,
)
from momentum import regime_macro_ok, setores_ativos, resumo_regime, modo_mercado, score_setores
from smll_composicao import SMLL_COMPOSICAO
from config import SETORES, N_SETORES_CARTEIRA, PESOS_RANK, ZSCORE_ENTRADA_BULL, ZSCORE_PEER_BEAR, JANELA_MOMENTUM_DIAS


def rodar_scanner(
    precos_acoes: pd.DataFrame,
    precos_indices: pd.DataFrame,
    precos_etfs: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:

    ret_acoes   = calcular_retornos(precos_acoes)
    ret_indices = calcular_retornos(precos_indices)
    ret_ibov    = ret_indices["ibov"].dropna()

    betas        = beta_todos(ret_acoes, ret_ibov)
    zscores      = calcular_distorcoes(ret_acoes, ret_ibov, betas)
    zscores_peer = calcular_zscore_peer(ret_acoes, SMLL_COMPOSICAO)
    vols         = calcular_volatilidade(ret_acoes).iloc[-1].dropna()

    spy     = precos_indices["spy"].dropna() if "spy" in precos_indices.columns else None
    regime  = regime_macro_ok(precos_indices)
    setores = setores_ativos(precos_etfs, regime, spy)
    modo    = modo_mercado(regime)
    resumo_regime(regime, setores, modo)

    snap = snapshot_atual(zscores, betas, zscores_peer, vols)
    snap["setor"]       = snap.index.map(lambda t: SMLL_COMPOSICAO.get(t.replace(".SA", ""), "Desconhecido"))
    snap["setor_ativo"] = snap["setor"].map(setores).fillna(False)

    # Filtro de tendência: MA20 (bear) e MA60 (bull)
    preco_atual = precos_acoes.iloc[-1]
    ma20 = precos_acoes.rolling(20).mean().iloc[-1]
    ma60 = precos_acoes.rolling(60).mean().iloc[-1]

    ma20_map = {}
    ma60_map = {}
    for col in precos_acoes.columns:
        p = preco_atual.get(col, np.nan)
        m20 = ma20.get(col, np.nan)
        m60 = ma60.get(col, np.nan)
        ma20_map[col] = (not pd.isna(p) and not pd.isna(m20) and p > m20)
        ma60_map[col] = (not pd.isna(p) and not pd.isna(m60) and p > m60)

    # Ranking dos N setores mais fortes e seus pesos
    scores    = score_setores(precos_etfs, regime, spy)
    top_rank  = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:N_SETORES_CARTEIRA]
    setores_top = [s for s, _ in top_rank]
    pesos_rank  = PESOS_RANK[:len(top_rank)]
    peso_map    = {s: pesos_rank[i] for i, (s, _) in enumerate(top_rank)}

    # Classifica risco para cada ação
    snap["risco"] = snap.apply(
        lambda r: classificar_risco(r["vol"] if not pd.isna(r["vol"]) else 0.5, r["setor_ativo"]),
        axis=1,
    )

    sort_col, asc = ("zscore", True) if modo == "bull" else ("zscore_peer", False)
    candidatas = snap[snap["setor"].isin(setores_top)].reset_index()

    # Filtro threshold de z-score + confirmação de tendência
    if modo == "bull":
        # Só entra com distorção real
        candidatas = candidatas[candidatas["zscore"] < ZSCORE_ENTRADA_BULL]
        # Ação deve estar acima da MA60 — lag temporário, tendência de médio prazo intacta
        candidatas = candidatas[candidatas["ticker"].map(lambda t: ma60_map.get(t, False))]
    else:
        # Só entra com força relativa real
        candidatas = candidatas[candidatas["zscore_peer"] > ZSCORE_PEER_BEAR]
        # Ação deve estar acima da MA20 — confirma força relativa genuína
        candidatas = candidatas[candidatas["ticker"].map(lambda t: ma20_map.get(t, False))]

    candidatas = candidatas.sort_values(sort_col, ascending=asc)

    # 1 ação por setor (dos top N) — só setores com candidato válido
    if candidatas.empty:
        carteira = pd.DataFrame()
    else:
        carteira = (
            candidatas
            .groupby("setor", group_keys=False)
            .apply(lambda g: g.sort_values(sort_col, ascending=asc, na_position="last").head(1))
            .reset_index(drop=True)
        )

    if carteira.empty:
        print(f"\n[AVISO] Nenhum candidato passou os filtros em [{modo.upper()} MODE]")
        return pd.DataFrame(), modo

    carteira["peso"] = carteira["setor"].map(peso_map).fillna(PESOS_RANK[-1])
    carteira["modo"] = modo

    print(f"\n=== CARTEIRA DA SEMANA [{modo.upper()} MODE] — TOP {N_SETORES_CARTEIRA} SETORES ===")
    print(f"{'TICKER':<12} {'SETOR':<25} {'PESO':>5} {'Z-IBOV':>7} {'Z-PEER':>7} {'VOL':>6}  RISCO")
    print("-" * 90)
    for _, row in carteira.iterrows():
        zpeer = f"{row['zscore_peer']:+.2f}" if not pd.isna(row.get("zscore_peer")) else "  n/a"
        vol   = f"{row['vol']:.0%}" if not pd.isna(row.get("vol")) else "  n/a"
        peso  = f"{row['peso']:.0%}" if not pd.isna(row.get("peso")) else "  n/a"
        print(f"{row['ticker']:<12} {row['setor']:<25} {peso:>5} {row['zscore']:>+7.2f} {zpeer:>7} {vol:>6}  {row['risco']}")

    return carteira, modo
