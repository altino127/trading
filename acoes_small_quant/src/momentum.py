import pandas as pd
from config import SETORES, JANELA_MOMENTUM_DIAS, VIX_LIMITE


def momentum_positivo(precos: pd.Series, janela: int = JANELA_MOMENTUM_DIAS) -> bool:
    if len(precos.dropna()) < janela:
        return False
    return precos.iloc[-1] > precos.rolling(janela).mean().iloc[-1]


def regime_macro_ok(indices: pd.DataFrame) -> dict:
    return {
        "ibov_ok":    momentum_positivo(indices["ibov"]),
        "smll_ok":    momentum_positivo(indices["smll"]),
        "russell_ok": momentum_positivo(indices["russell"]),
        "vix_ok":     indices["vix"].iloc[-1] < VIX_LIMITE,
        "usdbrl_ok":  not momentum_positivo(indices["usdbrl"]),  # dólar caindo favorece small BR
    }


def setores_ativos(etfs: pd.DataFrame, regime: dict) -> dict:
    """
    Retorna dict {setor: True/False} indicando quais setores
    têm fator global ativo (ETF EUA em momentum + regime macro ok).
    """
    macro_base_ok = regime["ibov_ok"] and regime["smll_ok"] and regime["vix_ok"]

    resultado = {}
    for setor, etf_ticker in SETORES.items():
        if etf_ticker not in etfs.columns:
            resultado[setor] = False
            continue
        etf_ok = momentum_positivo(etfs[etf_ticker])
        resultado[setor] = macro_base_ok and etf_ok and regime["russell_ok"]

    return resultado


def resumo_regime(regime: dict, setores: dict) -> None:
    print("\n=== REGIME MACRO ===")
    for k, v in regime.items():
        status = "OK" if v else "OFF"
        print(f"  {k:<15} {status}")

    print("\n=== SETORES ATIVOS ===")
    for setor, ativo in setores.items():
        status = "ATIVO" if ativo else "inativo"
        print(f"  {setor:<30} {status}")
