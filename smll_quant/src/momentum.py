import pandas as pd
from config import SETORES, JANELA_MOMENTUM_DIAS, VIX_LIMITE, MACRO_MINIMO_ON


def momentum_positivo(precos: pd.Series, janela: int = JANELA_MOMENTUM_DIAS) -> bool:
    if len(precos.dropna()) < janela:
        return False
    return bool(precos.iloc[-1] > precos.rolling(janela).mean().iloc[-1])


def regime_macro_ok(indices: pd.DataFrame) -> dict:
    return {
        "ibov_ok":    momentum_positivo(indices["ibov"]),
        "smll_ok":    momentum_positivo(indices["smll"]),
        "russell_ok": momentum_positivo(indices["russell"]),
        "vix_ok":     bool(indices["vix"].iloc[-1] < VIX_LIMITE),
        "usdbrl_ok":  not momentum_positivo(indices["usdbrl"]),
    }


def modo_mercado(regime: dict) -> str:
    """
    'bull' se >= MACRO_MINIMO_ON indicadores estão OK.
    'bear' caso contrário — usa força relativa de setor vs SPY.
    """
    chaves = ["ibov_ok", "smll_ok", "russell_ok", "vix_ok"]
    n_ok = sum(regime[k] for k in chaves)
    return "bull" if n_ok >= MACRO_MINIMO_ON else "bear"


def forca_relativa_setor(etfs: pd.DataFrame, spy: pd.Series, janela: int = JANELA_MOMENTUM_DIAS) -> dict:
    """
    Retorna dict {setor: float} com retorno relativo do ETF vs SPY na janela.
    Positivo = setor superando o mercado amplo (mesmo em queda).
    """
    ret_spy = spy.pct_change(janela).iloc[-1]
    resultado = {}
    for setor in SETORES:
        if setor not in etfs.columns:
            resultado[setor] = 0.0
            continue
        ret_etf = etfs[setor].pct_change(janela).iloc[-1]
        resultado[setor] = float(ret_etf - ret_spy)
    return resultado


def setores_ativos(etfs: pd.DataFrame, regime: dict, spy: pd.Series = None) -> dict:
    """
    Bull mode: setor ativo se ETF > MA20 + macro ok.
    Bear mode: setor ativo se ETF superando SPY nos últimos JANELA_MOMENTUM_DIAS.
    """
    modo = modo_mercado(regime)
    resultado = {}

    if modo == "bull":
        macro_base_ok = regime["ibov_ok"] and regime["smll_ok"] and regime["vix_ok"]
        for setor in SETORES:
            if setor not in etfs.columns:
                resultado[setor] = False
                continue
            etf_ok = momentum_positivo(etfs[setor])
            resultado[setor] = macro_base_ok and etf_ok and regime["russell_ok"]

    else:  # bear mode
        if spy is None:
            return {s: False for s in SETORES}
        fr = forca_relativa_setor(etfs, spy)
        for setor in SETORES:
            resultado[setor] = fr.get(setor, 0.0) > 0.0

    return resultado


def resumo_regime(regime: dict, setores: dict, modo: str = "") -> None:
    label = f"[{modo.upper()} MODE]" if modo else ""
    print(f"\n=== REGIME MACRO {label} ===")
    for k, v in regime.items():
        status = "OK" if v else "OFF"
        print(f"  {k:<15} {status}")

    print("\n=== SETORES ATIVOS ===")
    for setor, ativo in setores.items():
        status = "ATIVO" if ativo else "inativo"
        print(f"  {setor:<30} {status}")
