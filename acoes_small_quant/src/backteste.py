import pandas as pd
import numpy as np
from beta import calcular_retornos, beta_todos
from distorcao import calcular_distorcoes, calcular_zscore_peer, calcular_volatilidade, classificar_risco
from config import JANELA_BETA_DIAS, JANELA_MOMENTUM_DIAS, ZSCORE_ENTRADA_BULL, ZSCORE_PEER_BEAR, SETORES, MACRO_MINIMO_ON
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

    # modo: bull se >= MACRO_MINIMO_ON indicadores OK
    macro_cols = ["ibov_ok", "smll_ok", "russell_ok", "vix_ok"]
    sinais["n_macro_ok"] = sinais[macro_cols].sum(axis=1)
    sinais["modo_bull"]  = (sinais["n_macro_ok"] >= MACRO_MINIMO_ON).astype(int)

    spy = precos_indices.get("spy", None)

    for setor in SETORES:
        if setor not in precos_etfs.columns:
            sinais[f"bull_{setor}"] = 0
            sinais[f"bear_{setor}"] = 0
            continue

        # bull: ETF acima da MA
        sinais[f"bull_{setor}"] = _momentum_serie(precos_etfs[setor], j)

        # bear: ETF superando SPY
        if spy is not None:
            rel = _ret_relativo_serie(precos_etfs[setor], spy, j)
            sinais[f"bear_{setor}"] = (rel > 0).astype(int)
        else:
            sinais[f"bear_{setor}"] = 0

    return sinais


def _setor_ativo_em(data: pd.Timestamp, sinais: pd.DataFrame, modo: str) -> dict:
    if data not in sinais.index:
        return {s: False for s in SETORES}
    row = sinais.loc[data]
    resultado = {}
    for setor in SETORES:
        if modo == "bull":
            macro_ok = bool(row["ibov_ok"]) and bool(row["smll_ok"]) and bool(row["vix_ok"]) and bool(row["russell_ok"])
            resultado[setor] = macro_ok and bool(row.get(f"bull_{setor}", 0))
        else:
            resultado[setor] = bool(row.get(f"bear_{setor}", 0))
    return resultado


def _selecionar_carteira(
    data: pd.Timestamp,
    snap_zscore: pd.DataFrame,
    snap_beta: pd.DataFrame,
    snap_peer: pd.DataFrame,
    snap_vols: pd.DataFrame,
    sinais: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    if data not in snap_zscore.index:
        return pd.DataFrame(), "bull"

    modo       = "bull" if sinais.loc[data, "modo_bull"] == 1 else "bear"
    z          = snap_zscore.loc[data].dropna()
    b          = snap_beta.loc[data].dropna()
    zp         = snap_peer.loc[data].dropna() if data in snap_peer.index else pd.Series()
    vols_hoje  = snap_vols.loc[data].dropna() if data in snap_vols.index else pd.Series()
    setores_ok = _setor_ativo_em(data, sinais, modo)

    registros = []
    for ticker in z.index:
        nome       = ticker.replace(".SA", "")
        setor      = SMLL_COMPOSICAO.get(nome, "Desconhecido")
        ativo      = setores_ok.get(setor, False)
        vol_val    = float(vols_hoje.get(ticker, 0.5))
        zpeer_val  = zp.get(ticker, np.nan)

        registros.append({
            "ticker":      ticker,
            "setor":       setor,
            "zscore":      z[ticker],
            "zscore_peer": zpeer_val,
            "beta":        b.get(ticker, np.nan),
            "vol":         vol_val,
            "risco":       classificar_risco(vol_val, ativo),
            "modo":        modo,
        })

    if not registros:
        return pd.DataFrame(), modo

    df       = pd.DataFrame(registros)
    sort_col = "zscore" if modo == "bull" else "zscore_peer"
    asc      = modo == "bull"

    carteira = (
        df.sort_values(sort_col, ascending=asc)
        .groupby("setor", group_keys=False)
        .apply(lambda g: g.nsmallest(1, sort_col) if asc else g.nlargest(1, sort_col))
        .reset_index(drop=True)
    )
    return carteira, modo


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

    print("Pre-calculando sinais bull/bear...")
    sinais = _pre_calcular_sinais(precos_indices, precos_etfs)

    idx = precos_acoes.index
    if inicio:
        idx = idx[idx >= pd.Timestamp(inicio)]
    if fim:
        idx = idx[idx <= pd.Timestamp(fim)]

    segundas = [d for d in idx if d.weekday() == 0]
    trades   = []
    equity   = {}

    print(f"Simulando {len(segundas)} semanas...")

    for entrada in segundas:
        pos_sinal = zscores_full.index[zscores_full.index < entrada]
        if len(pos_sinal) == 0:
            continue
        data_sinal = pos_sinal[-1]

        carteira, modo = _selecionar_carteira(
            data_sinal, zscores_full, betas_full, peer_full, vols_full, sinais
        )
        if carteira.empty:
            equity[entrada] = 0.0
            continue

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
            p_in  = precos_acoes.loc[entrada, ticker]
            p_out = precos_acoes.loc[saida, ticker]
            if pd.isna(p_in) or pd.isna(p_out) or p_in == 0:
                continue
            ret = (p_out / p_in) - 1
            trades.append({
                "entrada":     entrada,
                "saida":       saida,
                "ticker":      ticker,
                "setor":       row["setor"],
                "modo":        modo,
                "risco":       row.get("risco", ""),
                "zscore":      row["zscore"],
                "zscore_peer": row.get("zscore_peer", np.nan),
                "beta":        row["beta"],
                "vol":         row.get("vol", np.nan),
                "retorno":     ret,
            })
            retornos_semana.append(ret)

        equity[entrada] = float(np.mean(retornos_semana)) if retornos_semana else 0.0

    trades_df  = pd.DataFrame(trades)
    equity_df  = pd.Series(equity, name="retorno_semanal").sort_index()
    return trades_df, equity_df
