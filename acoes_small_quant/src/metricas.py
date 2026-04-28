import pandas as pd
import numpy as np


def equity_curve(retornos_semanais: pd.Series) -> pd.Series:
    return (1 + retornos_semanais.fillna(0)).cumprod()


def retorno_total(curve: pd.Series) -> float:
    return curve.iloc[-1] - 1


def retorno_anualizado(retornos_semanais: pd.Series) -> float:
    n_semanas = len(retornos_semanais)
    if n_semanas == 0:
        return 0.0
    retorno_composto = (1 + retornos_semanais.fillna(0)).prod()
    return retorno_composto ** (52 / n_semanas) - 1


def sharpe(retornos_semanais: pd.Series, rf_semanal: float = 0.0) -> float:
    excesso = retornos_semanais.fillna(0) - rf_semanal
    if excesso.std() == 0:
        return 0.0
    return (excesso.mean() / excesso.std()) * np.sqrt(52)


def max_drawdown(curve: pd.Series) -> float:
    pico = curve.cummax()
    dd = (curve - pico) / pico
    return dd.min()


def win_rate(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    return (trades["retorno"] > 0).mean()


def retorno_medio_trade(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    return trades["retorno"].mean()


def resumo_metricas(
    trades: pd.DataFrame,
    equity: pd.Series,
    benchmark_ibov: pd.Series = None,
    benchmark_smll: pd.Series = None,
) -> dict:
    curve = equity_curve(equity)

    metricas = {
        "Retorno Total":         f"{retorno_total(curve):.1%}",
        "Retorno Anualizado":    f"{retorno_anualizado(equity):.1%}",
        "Sharpe (anual)":        f"{sharpe(equity):.2f}",
        "Max Drawdown":          f"{max_drawdown(curve):.1%}",
        "Win Rate":              f"{win_rate(trades):.1%}",
        "Retorno Médio/Trade":   f"{retorno_medio_trade(trades):.2%}",
        "Total de Trades":       str(len(trades)),
        "Semanas Simuladas":     str(len(equity)),
        "Semanas com Posição":   str((equity != 0).sum()),
    }

    if benchmark_ibov is not None and not benchmark_ibov.empty:
        ret_ibov = retorno_total(equity_curve(benchmark_ibov.pct_change().dropna().resample("W").last()))
        metricas["IBOV Total"] = f"{ret_ibov:.1%}"

    if benchmark_smll is not None and not benchmark_smll.empty:
        ret_smll = retorno_total(equity_curve(benchmark_smll.pct_change().dropna().resample("W").last()))
        metricas["SMLL Total"] = f"{ret_smll:.1%}"

    return metricas


def retorno_por_setor(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    return (
        trades.groupby("setor")["retorno"]
        .agg(["mean", "count", lambda x: (x > 0).mean()])
        .rename(columns={"mean": "ret_medio", "count": "n_trades", "<lambda_0>": "win_rate"})
        .sort_values("ret_medio", ascending=False)
    )
