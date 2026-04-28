import pandas as pd
import numpy as np
from config import JANELA_BETA_DIAS, ZSCORE_ENTRADA


def retorno_esperado(retornos_ibov: pd.Series, beta: pd.Series) -> pd.Series:
    return beta * retornos_ibov


def distorcao_diaria(retornos_acao: pd.Series, retornos_ibov: pd.Series, beta: pd.Series) -> pd.Series:
    esperado = retorno_esperado(retornos_ibov, beta)
    return retornos_acao - esperado


def zscore_distorcao(distorcao: pd.Series, janela: int = JANELA_BETA_DIAS) -> pd.Series:
    media = distorcao.rolling(janela).mean()
    std = distorcao.rolling(janela).std()
    return (distorcao - media) / std


def calcular_distorcoes(
    retornos_acoes: pd.DataFrame,
    retornos_ibov: pd.Series,
    betas: pd.DataFrame,
    janela: int = JANELA_BETA_DIAS,
) -> pd.DataFrame:
    zscores = {}
    for ticker in retornos_acoes.columns:
        if ticker not in betas.columns:
            continue
        ret = retornos_acoes[ticker]
        beta = betas[ticker]
        idx = ret.index.intersection(retornos_ibov.index).intersection(beta.dropna().index)
        if len(idx) < janela:
            continue
        dist = distorcao_diaria(ret.loc[idx], retornos_ibov.loc[idx], beta.loc[idx])
        zscores[ticker] = zscore_distorcao(dist, janela)
    return pd.DataFrame(zscores)


def snapshot_atual(zscores: pd.DataFrame, betas: pd.DataFrame) -> pd.DataFrame:
    ultima = zscores.iloc[-1].dropna()
    beta_atual = betas.iloc[-1].dropna()

    df = pd.DataFrame({
        "zscore": ultima,
        "beta": beta_atual,
    }).dropna()

    df = df.sort_values("zscore")
    df["distorcao_flag"] = df["zscore"] < ZSCORE_ENTRADA
    return df
