import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from metricas import equity_curve, max_drawdown

VERDE = "#00C896"
VERMELHO = "#FF4B4B"
AMARELO = "#FFD700"
AZUL = "#4B8BFF"
CINZA = "#8B8B8B"
BG = "#0E1117"
BG2 = "#1C1C2E"


def grafico_equity(
    equity: pd.Series,
    ibov: pd.Series = None,
    smll: pd.Series = None,
) -> go.Figure:
    curve = equity_curve(equity)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=curve.index, y=(curve * 100 - 100).round(2),
        mode="lines", name="SmallQuant",
        line=dict(color=VERDE, width=2.5),
    ))

    if ibov is not None:
        ibov_w = ibov.resample("W").last().pct_change().dropna()
        ibov_curve = (equity_curve(ibov_w) * 100 - 100)
        ibov_curve = ibov_curve.reindex(curve.index, method="ffill")
        fig.add_trace(go.Scatter(
            x=ibov_curve.index, y=ibov_curve.round(2),
            mode="lines", name="IBOV",
            line=dict(color=CINZA, width=1.5, dash="dot"),
        ))

    if smll is not None:
        smll_w = smll.resample("W").last().pct_change().dropna()
        smll_curve = (equity_curve(smll_w) * 100 - 100)
        smll_curve = smll_curve.reindex(curve.index, method="ffill")
        fig.add_trace(go.Scatter(
            x=smll_curve.index, y=smll_curve.round(2),
            mode="lines", name="SMLL",
            line=dict(color=AMARELO, width=1.5, dash="dot"),
        ))

    fig.add_hline(y=0, line_color=CINZA, line_dash="dash")
    fig.update_layout(
        title="Equity Curve — SmallQuant vs Benchmarks",
        yaxis=dict(title="Retorno Acumulado (%)"),
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color="white"),
        legend=dict(bgcolor=BG2),
        height=380,
        margin=dict(t=40, b=20, l=60, r=20),
    )
    return fig


def grafico_drawdown(equity: pd.Series) -> go.Figure:
    curve = equity_curve(equity)
    pico = curve.cummax()
    dd = ((curve - pico) / pico * 100).round(2)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        mode="lines", name="Drawdown",
        fill="tozeroy",
        line=dict(color=VERMELHO, width=1.5),
        fillcolor="rgba(255,75,75,0.2)",
    ))
    fig.update_layout(
        title="Drawdown (%)",
        yaxis=dict(title="Drawdown (%)"),
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color="white"),
        height=250,
        margin=dict(t=40, b=20, l=60, r=20),
    )
    return fig


def grafico_retorno_semanal(equity: pd.Series) -> go.Figure:
    cores = [VERDE if v >= 0 else VERMELHO for v in equity.values]

    fig = go.Figure(go.Bar(
        x=equity.index,
        y=(equity * 100).round(2),
        marker_color=cores,
        name="Retorno semanal",
    ))
    fig.update_layout(
        title="Retorno Semanal da Carteira (%)",
        yaxis=dict(title="Retorno (%)"),
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color="white"),
        height=280,
        margin=dict(t=40, b=20, l=60, r=20),
    )
    return fig


def grafico_retorno_por_setor(por_setor: pd.DataFrame) -> go.Figure:
    if por_setor.empty:
        return go.Figure()

    df = por_setor.sort_values("ret_medio")
    cores = [VERDE if v >= 0 else VERMELHO for v in df["ret_medio"].values]

    fig = go.Figure(go.Bar(
        x=(df["ret_medio"] * 100).round(2),
        y=df.index,
        orientation="h",
        marker_color=cores,
        text=[f"{v:.1%}  ({int(n)} trades)" for v, n in zip(df["ret_medio"], df["n_trades"])],
        textposition="outside",
    ))
    fig.update_layout(
        title="Retorno Médio por Setor",
        xaxis=dict(title="Retorno Médio (%)"),
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color="white"),
        height=380,
        margin=dict(t=40, b=20, l=180, r=120),
    )
    return fig


def grafico_distribuicao_trades(trades: pd.DataFrame) -> go.Figure:
    if trades.empty:
        return go.Figure()

    rets = trades["retorno"] * 100

    fig = go.Figure(go.Histogram(
        x=rets.round(2),
        nbinsx=30,
        marker_color=AZUL,
        opacity=0.8,
        name="Trades",
    ))
    fig.add_vline(x=0, line_color=CINZA, line_dash="dash")
    fig.add_vline(x=rets.mean(), line_color=VERDE, line_dash="dot",
                  annotation_text=f"Média: {rets.mean():.2f}%")
    fig.update_layout(
        title="Distribuição dos Retornos por Trade (%)",
        xaxis=dict(title="Retorno (%)"),
        yaxis=dict(title="Frequência"),
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color="white"),
        height=300,
        margin=dict(t=40, b=20, l=60, r=20),
    )
    return fig
