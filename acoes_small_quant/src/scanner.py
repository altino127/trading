import pandas as pd
from beta import calcular_retornos, beta_todos
from distorcao import calcular_distorcoes, snapshot_atual
from momentum import regime_macro_ok, setores_ativos, resumo_regime
from smll_composicao import SMLL_COMPOSICAO, acoes_por_setor


def rodar_scanner(
    precos_acoes: pd.DataFrame,
    precos_indices: pd.DataFrame,
    precos_etfs: pd.DataFrame,
) -> pd.DataFrame:

    ret_acoes = calcular_retornos(precos_acoes)
    ret_indices = calcular_retornos(precos_indices)
    ret_ibov = ret_indices["ibov"].dropna()

    print("Calculando betas rolling...")
    betas = beta_todos(ret_acoes, ret_ibov)

    print("Calculando z-scores de distorção...")
    zscores = calcular_distorcoes(ret_acoes, ret_ibov, betas)

    snap = snapshot_atual(zscores, betas)
    snap.index.name = "ticker"
    snap["setor"] = snap.index.map(
        lambda t: SMLL_COMPOSICAO.get(t.replace(".SA", ""), "Desconhecido")
    )

    regime = regime_macro_ok(precos_indices)
    setores = setores_ativos(precos_etfs, regime)
    resumo_regime(regime, setores)

    snap["setor_ativo"] = snap["setor"].map(setores).fillna(False)

    candidatas = (
        snap[snap["setor_ativo"] & snap["distorcao_flag"]]
        .sort_values("zscore")
        .reset_index()
    )

    print("\n=== CANDIDATAS DA SEMANA ===")
    if candidatas.empty:
        print("  Nenhuma distorção encontrada com setores ativos.")
        return pd.DataFrame()

    carteira = (
        candidatas
        .groupby("setor", group_keys=False)
        .apply(lambda g: g.nsmallest(1, "zscore"))
        .reset_index(drop=True)
    )

    print(carteira[["ticker", "setor", "zscore", "beta"]].to_string(index=False))
    return carteira
