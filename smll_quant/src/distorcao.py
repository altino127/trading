import pandas as pd
import numpy as np
from config import JANELA_BETA_DIAS, JANELA_PEER_DIAS, ZSCORE_ENTRADA_BULL, ZSCORE_PEER_BEAR, VOL_BAIXA, VOL_ALTA


def retorno_esperado(retornos_ibov: pd.Series, beta: pd.Series) -> pd.Series:
    return beta * retornos_ibov


def distorcao_diaria(retornos_acao: pd.Series, retornos_ibov: pd.Series, beta: pd.Series) -> pd.Series:
    return retornos_acao - retorno_esperado(retornos_ibov, beta)


def zscore_serie(serie: pd.Series, janela: int) -> pd.Series:
    media = serie.rolling(janela).mean()
    std = serie.rolling(janela).std()
    return (serie - media) / std


def calcular_distorcoes(
    retornos_acoes: pd.DataFrame,
    retornos_ibov: pd.Series,
    betas: pd.DataFrame,
    janela: int = JANELA_BETA_DIAS,
) -> pd.DataFrame:
    """Z-score da distorção de cada ação vs IBOV (ajustado por beta)."""
    zscores = {}
    for ticker in retornos_acoes.columns:
        if ticker not in betas.columns:
            continue
        ret  = retornos_acoes[ticker]
        beta = betas[ticker]
        idx  = ret.index.intersection(retornos_ibov.index).intersection(beta.dropna().index)
        if len(idx) < janela:
            continue
        dist = distorcao_diaria(ret.loc[idx], retornos_ibov.loc[idx], beta.loc[idx])
        zscores[ticker] = zscore_serie(dist, janela)
    return pd.DataFrame(zscores)


def calcular_zscore_peer(
    retornos_acoes: pd.DataFrame,
    composicao: dict,
    janela: int = JANELA_PEER_DIAS,
) -> pd.DataFrame:
    """
    Z-score peer-relativo: cada ação vs média do seu setor.
    Positivo = ação superando os pares = força relativa.
    Negativo = ação atrasando vs pares = candidata à reversão.
    """
    zscores_peer = {}
    for ticker in retornos_acoes.columns:
        nome  = ticker.replace(".SA", "")
        setor = composicao.get(nome, "Desconhecido")

        peers = [
            t + ".SA" for t, s in composicao.items()
            if s == setor and (t + ".SA") in retornos_acoes.columns and (t + ".SA") != ticker
        ]
        if len(peers) < 2:
            continue

        ret_acao  = retornos_acoes[ticker]
        ret_peers = retornos_acoes[peers].mean(axis=1)

        idx = ret_acao.index.intersection(ret_peers.index)
        if len(idx) < janela:
            continue

        diff = ret_acao.loc[idx] - ret_peers.loc[idx]
        zscores_peer[ticker] = zscore_serie(diff, janela)

    return pd.DataFrame(zscores_peer)


def calcular_volatilidade(
    retornos_acoes: pd.DataFrame,
    janela: int = JANELA_PEER_DIAS,
) -> pd.Series:
    """Volatilidade anualizada rolling (252 dias úteis)."""
    return retornos_acoes.rolling(janela).std() * np.sqrt(252)


def classificar_risco(vol: float, setor_ativo: bool) -> str:
    """
    Classifica o risco combinando volatilidade anualizada e atividade do setor.
    Setor inativo degrada o risco em um nível.
    """
    if vol < VOL_BAIXA:
        nivel = 0  # baixo
    elif vol < VOL_ALTA:
        nivel = 1  # médio
    else:
        nivel = 2  # alto

    if not setor_ativo:
        nivel = min(nivel + 1, 2)

    labels = [
        "Baixa Volatilidade - baixo risco",
        "Media Volatilidade - medio risco",
        "Alta Volatilidade - alto risco",
    ]
    return labels[nivel]


def snapshot_atual(
    zscores: pd.DataFrame,
    betas: pd.DataFrame,
    zscores_peer: pd.DataFrame = None,
    volatilidades: pd.Series = None,
) -> pd.DataFrame:
    ultima      = zscores.iloc[-1].dropna()
    beta_atual  = betas.iloc[-1].dropna()

    df = pd.DataFrame({"zscore": ultima, "beta": beta_atual}).dropna()
    df.index.name = "ticker"

    if zscores_peer is not None and not zscores_peer.empty:
        df["zscore_peer"] = zscores_peer.iloc[-1].dropna().reindex(df.index)
    else:
        df["zscore_peer"] = np.nan

    if volatilidades is not None:
        df["vol"] = volatilidades.reindex(df.index)
    else:
        df["vol"] = np.nan

    df = df.sort_values("zscore")
    df["flag_bull"] = df["zscore"] < ZSCORE_ENTRADA_BULL
    df["flag_bear"] = df["zscore_peer"] > ZSCORE_PEER_BEAR

    return df
