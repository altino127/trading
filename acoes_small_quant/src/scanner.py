import pandas as pd
from beta import calcular_retornos, beta_todos
from distorcao import calcular_distorcoes, calcular_zscore_peer, snapshot_atual
from momentum import regime_macro_ok, setores_ativos, resumo_regime, modo_mercado
from smll_composicao import SMLL_COMPOSICAO, acoes_por_setor


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

    spy   = precos_indices["spy"].dropna() if "spy" in precos_indices.columns else None
    regime  = regime_macro_ok(precos_indices)
    setores = setores_ativos(precos_etfs, regime, spy)
    modo    = modo_mercado(regime)
    resumo_regime(regime, setores, modo)

    snap = snapshot_atual(zscores, betas, zscores_peer)
    snap["setor"] = snap.index.map(
        lambda t: SMLL_COMPOSICAO.get(t.replace(".SA", ""), "Desconhecido")
    )
    snap["setor_ativo"] = snap["setor"].map(setores).fillna(False)

    # seleciona flag correta pelo modo
    flag_col = "flag_bull" if modo == "bull" else "flag_bear"
    candidatas = (
        snap[snap["setor_ativo"] & snap[flag_col]]
        .sort_values("zscore" if modo == "bull" else "zscore_peer",
                     ascending=(modo == "bull"))
        .reset_index()
    )

    print(f"\n=== CANDIDATAS DA SEMANA [{modo.upper()} MODE] ===")
    if candidatas.empty:
        print("  Nenhuma candidata encontrada.")
        return pd.DataFrame(), modo

    carteira = (
        candidatas
        .groupby("setor", group_keys=False)
        .apply(lambda g: g.nsmallest(1, "zscore") if modo == "bull"
               else g.nlargest(1, "zscore_peer"))
        .reset_index(drop=True)
    )

    cols = ["ticker", "setor", "zscore", "zscore_peer", "beta"]
    print(carteira[[c for c in cols if c in carteira.columns]].to_string(index=False))
    return carteira, modo
