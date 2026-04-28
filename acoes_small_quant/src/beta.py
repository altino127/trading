import pandas as pd
import numpy as np
from config import JANELA_BETA_DIAS


def calcular_retornos(precos: pd.DataFrame) -> pd.DataFrame:
    return precos.pct_change().dropna()


def rolling_beta(retornos_acao: pd.Series, retornos_benchmark: pd.Series, janela: int = JANELA_BETA_DIAS) -> pd.Series:
    cov = retornos_acao.rolling(janela).cov(retornos_benchmark)
    var = retornos_benchmark.rolling(janela).var()
    return cov / var


def beta_todos(retornos_acoes: pd.DataFrame, retornos_ibov: pd.Series, janela: int = JANELA_BETA_DIAS) -> pd.DataFrame:
    betas = {}
    for ticker in retornos_acoes.columns:
        serie = retornos_acoes[ticker].dropna()
        bench = retornos_ibov.reindex(serie.index).dropna()
        idx_comum = serie.index.intersection(bench.index)
        if len(idx_comum) < janela:
            continue
        betas[ticker] = rolling_beta(serie.loc[idx_comum], bench.loc[idx_comum], janela)
    return pd.DataFrame(betas)
