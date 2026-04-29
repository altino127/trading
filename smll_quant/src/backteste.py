import pandas as pd
import numpy as np
from beta import calcular_retornos, beta_todos
from distorcao import calcular_distorcoes, calcular_zscore_peer, calcular_volatilidade, classificar_risco
from config import (
    JANELA_BETA_DIAS, JANELA_MOMENTUM_DIAS,
    ZSCORE_ENTRADA_BULL, ZSCORE_PEER_BEAR,
    SETORES, MACRO_MINIMO_ON,
    N_SETORES_CARTEIRA, PESOS_RANK,
)
from smll_composicao import SMLL_COMPOSICAO


def _momentum_serie(precos: pd.Series, janela: int) -> pd.Series:
    return (precos > precos.rolling(janela).mean()).astype(int)


def _ret_relativo_serie(etf: pd.Series, spy: pd.Series, janela: int) -> pd.Series:
    return etf.pct_change(janela) - spy.pct_change(janela)


def _pre_calcular_sinais(
    precos_indices: pd.DataFrame,
    precos_etfs: pd.DataFrame,
) -> pd.DataFrame:
    j = JANELA_MOMENTUM_DIAS
    sinais = pd.DataFrame(index=precos_indices.index)

    sinais["ibov_ok"]    = _momentum_serie(precos_indices["ibov"], j)
    sinais["smll_ok"]    = _momentum_serie(precos_indices["smll"], j)
    sinais["russell_ok"] = _momentum_serie(precos_indices["russell"], j)
    sinais["vix_ok"]     = (precos_indices["vix"] < 25).astype(int)

    macro_cols = ["ibov_ok", "smll_ok", "russell_ok", "vix_ok"]
    sinais["n_macro_ok"] = sinais[macro_cols].sum(axis=1)
    sinais["modo_bull"]  = (sinais["n_macro_ok"] >= MACRO_MINIMO_ON).astype(int)

    spy = precos_indices.get("spy", None)

    for setor in SETORES:
        if setor not in precos_etfs.columns:
            sinais[f"score_{setor}"] = np.nan
            continue
        if spy is not None:
            sinais[f"score_{setor}"] = _ret_relativo_serie(precos_etfs[setor], spy, j)
        else:
            sinais[f"score_{setor}"] = precos_etfs[setor].pct_change(j)

    return sinais


def _top_setores_em(data: pd.Timestamp, sinais: pd.DataFrame, modo: str) -> dict:
    """Retorna dict {setor: peso} para os N setores mais fortes na data."""
    if data not in sinais.index:
        return {}

    row = sinais.loc[data]
    scores = {}
    for setor in SETORES:
        col = f"score_{setor}"
        val = row.get(col, np.nan)
        if not pd.isna(val):
            scores[setor] = float(val)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:N_SETORES_CARTEIRA]
    pesos  = PESOS_RANK[:len(ranked)]
    return {s: pesos[i] for i, (s, _) in enumerate(ranked)}


def _selecionar_carteira(
    data: pd.Timestamp,
    snap_zscore: pd.DataFrame,
    snap_beta: pd.DataFrame,
    snap_peer: pd.DataFrame,
    snap_vols: pd.DataFrame,
    sinais: pd.DataFrame,
    precos_acoes: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    if data not in snap_zscore.index:
        return pd.DataFrame(), "bull"

    modo      = "bull" if sinais.loc[data, "modo_bull"] == 1 else "bear"
    z         = snap_zscore.loc[data].dropna()
    b         = snap_beta.loc[data].dropna()
    zp        = snap_peer.loc[data].dropna() if data in snap_peer.index else pd.Series()
    vols_hoje = snap_vols.loc[data].dropna() if data in snap_vols.index else pd.Series()

    peso_map  = _top_setores_em(data, sinais, modo)
    if not peso_map:
        return pd.DataFrame(), modo

    # MA20 e MA60 da própria ação na data do sinal
    loc = precos_acoes.index.get_loc(data) if data in precos_acoes.index else None
    ma20_map = {}
    ma60_map = {}
    if loc is not None and loc >= 60:
        preco_val = precos_acoes.iloc[loc]
        ma20_val  = precos_acoes.iloc[max(0, loc - 20): loc + 1].mean()
        ma60_val  = precos_acoes.iloc[max(0, loc - 60): loc + 1].mean()
        for col in precos_acoes.columns:
            p = preco_val.get(col, np.nan)
            if pd.isna(p):
                continue
            ma20_map[col] = p > ma20_val.get(col, np.nan)
            ma60_map[col] = p > ma60_val.get(col, np.nan)

    sort_col, asc = ("zscore", True) if modo == "bull" else ("zscore_peer", False)

    registros = []
    for ticker in z.index:
        nome      = ticker.replace(".SA", "")
        setor     = SMLL_COMPOSICAO.get(nome, "Desconhecido")
        if setor not in peso_map:
            continue

        zscore_val = float(z[ticker])
        zpeer_val  = float(zp.get(ticker, np.nan))
        vol_val    = float(vols_hoje.get(ticker, 0.5))
        acima_ma20 = ma20_map.get(ticker, False)

        # Filtro threshold + confirmação de tendência
        if modo == "bull":
            if zscore_val >= ZSCORE_ENTRADA_BULL:
                continue
            # Bull: lag temporário — ação deve estar acima da MA60 (tendência de médio prazo intacta)
            if not ma60_map.get(ticker, False):
                continue
        else:
            if pd.isna(zpeer_val) or zpeer_val <= ZSCORE_PEER_BEAR:
                continue
            # Bear: força relativa — ação deve estar acima da MA20
            if not ma20_map.get(ticker, False):
                continue

        registros.append({
            "ticker":      ticker,
            "setor":       setor,
            "zscore":      zscore_val,
            "zscore_peer": zpeer_val,
            "beta":        b.get(ticker, np.nan),
            "vol":         vol_val,
            "risco":       classificar_risco(vol_val, True),
            "modo":        modo,
            "peso":        peso_map[setor],
        })

    if not registros:
        return pd.DataFrame(), modo

    df = pd.DataFrame(registros)
    carteira = (
        df.sort_values(sort_col, ascending=asc, na_position="last")
        .groupby("setor", group_keys=False)
        .apply(lambda g: g.sort_values(sort_col, ascending=asc, na_position="last").head(1))
        .reset_index(drop=True)
    )
    return carteira, modo


def _simular_trade(
    ticker: str,
    entrada: pd.Timestamp,
    dias_hold: int,
    precos_acoes: pd.DataFrame,
    vol: float,
) -> float | None:
    """Simula retorno com stop e alvo intraweek. Retorna retorno realizado."""
    if ticker not in precos_acoes.columns:
        return None

    daily_vol   = vol / np.sqrt(252)
    holding_vol = daily_vol * np.sqrt(dias_hold)
    stop_pct    = float(np.clip(-1.0 * holding_vol, -0.08, -0.02))
    alvo_pct    = float(np.clip(2.0 * holding_vol, abs(stop_pct) * 2.0, 0.15))

    try:
        p_in = precos_acoes.loc[entrada, ticker]
    except KeyError:
        return None
    if pd.isna(p_in) or p_in == 0:
        return None

    stop_preco = p_in * (1 + stop_pct)
    alvo_preco = p_in * (1 + alvo_pct)

    loc_entrada = precos_acoes.index.get_loc(entrada)
    for i in range(1, dias_hold + 1):
        idx = loc_entrada + i
        if idx >= len(precos_acoes):
            break
        p = precos_acoes.iloc[idx][ticker]
        if pd.isna(p):
            continue
        if p <= stop_preco:
            return (stop_preco / p_in) - 1
        if p >= alvo_preco:
            return (alvo_preco / p_in) - 1

    # Saída no vencimento
    idx_saida = loc_entrada + dias_hold
    if idx_saida >= len(precos_acoes):
        return None
    p_out = precos_acoes.iloc[idx_saida][ticker]
    if pd.isna(p_out):
        return None
    return (p_out / p_in) - 1


def rodar_backteste(
    precos_acoes: pd.DataFrame,
    precos_indices: pd.DataFrame,
    precos_etfs: pd.DataFrame,
    inicio: str = None,
    fim: str = None,
    dias_hold: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("Pre-calculando betas e z-scores...")
    ret_acoes   = calcular_retornos(precos_acoes)
    ret_indices = calcular_retornos(precos_indices)
    ret_ibov    = ret_indices["ibov"].dropna()

    betas_full   = beta_todos(ret_acoes, ret_ibov)
    zscores_full = calcular_distorcoes(ret_acoes, ret_ibov, betas_full)
    peer_full    = calcular_zscore_peer(ret_acoes, SMLL_COMPOSICAO)
    vols_full    = calcular_volatilidade(ret_acoes)

    print("Pre-calculando sinais bull/bear e scores de setor...")
    sinais = _pre_calcular_sinais(precos_indices, precos_etfs)

    idx = precos_acoes.index
    if inicio:
        idx = idx[idx >= pd.Timestamp(inicio)]
    if fim:
        idx = idx[idx <= pd.Timestamp(fim)]

    segundas = [d for d in idx if d.weekday() == 0]
    trades   = []
    equity   = {}

    print(f"Simulando {len(segundas)} semanas (top {N_SETORES_CARTEIRA} setores, stop/alvo ativos)...")

    for entrada in segundas:
        pos_sinal = zscores_full.index[zscores_full.index < entrada]
        if len(pos_sinal) == 0:
            continue
        data_sinal = pos_sinal[-1]

        carteira, modo = _selecionar_carteira(
            data_sinal, zscores_full, betas_full, peer_full, vols_full, sinais, precos_acoes
        )
        if carteira.empty:
            equity[entrada] = 0.0
            continue

        retorno_ponderado = 0.0
        peso_total        = 0.0

        for _, row in carteira.iterrows():
            ticker = row["ticker"]
            vol    = float(row["vol"])
            peso   = float(row["peso"])

            ret = _simular_trade(ticker, entrada, dias_hold, precos_acoes, vol)
            if ret is None:
                continue

            trades.append({
                "entrada":     entrada,
                "ticker":      ticker,
                "setor":       row["setor"],
                "modo":        modo,
                "risco":       row.get("risco", ""),
                "zscore":      row["zscore"],
                "zscore_peer": row.get("zscore_peer", np.nan),
                "beta":        row["beta"],
                "vol":         vol,
                "peso":        peso,
                "retorno":     ret,
            })
            retorno_ponderado += ret * peso
            peso_total        += peso

        equity[entrada] = (retorno_ponderado / peso_total) if peso_total > 0 else 0.0

    trades_df = pd.DataFrame(trades)
    equity_df = pd.Series(equity, name="retorno_semanal").sort_index()
    return trades_df, equity_df
