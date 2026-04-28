import pandas as pd
import numpy as np
from beta import calcular_retornos, beta_todos
from distorcao import calcular_distorcoes
from config import JANELA_BETA_DIAS, JANELA_MOMENTUM_DIAS, ZSCORE_ENTRADA, SETORES
from smll_composicao import SMLL_COMPOSICAO


def _momentum_serie(precos: pd.Series, janela: int) -> pd.Series:
    return (precos > precos.rolling(janela).mean()).astype(int)


def _pre_calcular_sinais(precos_indices: pd.DataFrame, precos_etfs: pd.DataFrame) -> pd.DataFrame:
    j = JANELA_MOMENTUM_DIAS
    sinais = pd.DataFrame(index=precos_indices.index)

    sinais["ibov_ok"]    = _momentum_serie(precos_indices["ibov"], j)
    sinais["smll_ok"]    = _momentum_serie(precos_indices["smll"], j)
    sinais["russell_ok"] = _momentum_serie(precos_indices["russell"], j)
    sinais["vix_ok"]     = (precos_indices["vix"] < 25).astype(int)
    sinais["usdbrl_ok"]  = (1 - _momentum_serie(precos_indices["usdbrl"], j))

    sinais["macro_ok"] = (
        sinais["ibov_ok"] & sinais["smll_ok"] &
        sinais["vix_ok"] & sinais["russell_ok"]
    )

    for setor, etf in SETORES.items():
        if etf in precos_etfs.columns:
            sinais[f"etf_{setor}"] = _momentum_serie(precos_etfs[etf], j)
        else:
            sinais[f"etf_{setor}"] = 0

    return sinais


def _setor_ativo_em(data: pd.Timestamp, sinais: pd.DataFrame) -> dict:
    if data not in sinais.index:
        return {s: False for s in SETORES}
    row = sinais.loc[data]
    macro = bool(row["macro_ok"])
    return {s: macro and bool(row.get(f"etf_{s}", 0)) for s in SETORES}


def _selecionar_carteira(
    data: pd.Timestamp,
    snap_zscore: pd.DataFrame,
    snap_beta: pd.DataFrame,
    sinais: pd.DataFrame,
) -> pd.DataFrame:
    if data not in snap_zscore.index:
        return pd.DataFrame()

    z = snap_zscore.loc[data].dropna()
    b = snap_beta.loc[data].dropna()
    setores_ok = _setor_ativo_em(data, sinais)

    registros = []
    for ticker in z.index:
        nome = ticker.replace(".SA", "")
        setor = SMLL_COMPOSICAO.get(nome, "Desconhecido")
        if not setores_ok.get(setor, False):
            continue
        zscore_val = z[ticker]
        if zscore_val >= ZSCORE_ENTRADA:
            continue
        registros.append({
            "ticker": ticker,
            "setor": setor,
            "zscore": zscore_val,
            "beta": b.get(ticker, np.nan),
        })

    if not registros:
        return pd.DataFrame()

    df = pd.DataFrame(registros)
    return (
        df.sort_values("zscore")
        .groupby("setor", group_keys=False)
        .apply(lambda g: g.nsmallest(1, "zscore"))
        .reset_index(drop=True)
    )


def rodar_backteste(
    precos_acoes: pd.DataFrame,
    precos_indices: pd.DataFrame,
    precos_etfs: pd.DataFrame,
    inicio: str = None,
    fim: str = None,
    dias_hold: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Walk-forward semanal sem look-ahead.
    Retorna (trades, equity_curve).
    """
    print("Pré-calculando betas e z-scores (pode levar alguns segundos)...")
    ret_acoes = calcular_retornos(precos_acoes)
    ret_indices = calcular_retornos(precos_indices)
    ret_ibov = ret_indices["ibov"].dropna()

    betas_full = beta_todos(ret_acoes, ret_ibov)
    zscores_full = calcular_distorcoes(ret_acoes, ret_ibov, betas_full)

    print("Pré-calculando sinais de momentum...")
    sinais = _pre_calcular_sinais(precos_indices, precos_etfs)

    idx = precos_acoes.index
    if inicio:
        idx = idx[idx >= pd.Timestamp(inicio)]
    if fim:
        idx = idx[idx <= pd.Timestamp(fim)]

    # Segundas-feiras dentro do período
    segundas = [d for d in idx if d.weekday() == 0]

    trades = []
    equity = {}

    print(f"Simulando {len(segundas)} semanas...")

    for entrada in segundas:
        # Sinal gerado com dados até a sexta anterior
        posicao_sinais = zscores_full.index[zscores_full.index < entrada]
        if len(posicao_sinais) == 0:
            continue
        data_sinal = posicao_sinais[-1]

        carteira = _selecionar_carteira(data_sinal, zscores_full, betas_full, sinais)
        if carteira.empty:
            equity[entrada] = 0.0
            continue

        # Saída: dias_hold dias úteis após entrada
        pos_entrada = precos_acoes.index.get_loc(entrada) if entrada in precos_acoes.index else None
        if pos_entrada is None:
            continue

        idx_saida = pos_entrada + dias_hold
        if idx_saida >= len(precos_acoes):
            continue
        saida = precos_acoes.index[idx_saida]

        retornos_semana = []
        for _, row in carteira.iterrows():
            ticker = row["ticker"]
            if ticker not in precos_acoes.columns:
                continue
            p_in = precos_acoes.loc[entrada, ticker]
            p_out = precos_acoes.loc[saida, ticker]
            if pd.isna(p_in) or pd.isna(p_out) or p_in == 0:
                continue
            ret = (p_out / p_in) - 1
            trades.append({
                "entrada": entrada,
                "saida": saida,
                "ticker": ticker,
                "setor": row["setor"],
                "zscore": row["zscore"],
                "beta": row["beta"],
                "retorno": ret,
            })
            retornos_semana.append(ret)

        ret_carteira = np.mean(retornos_semana) if retornos_semana else 0.0
        equity[entrada] = ret_carteira

    trades_df = pd.DataFrame(trades)
    equity_df = pd.Series(equity, name="retorno_semanal").sort_index()

    return trades_df, equity_df
