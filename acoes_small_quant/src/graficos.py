import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


VERDE = "#00C896"
VERMELHO = "#FF4B4B"
AMARELO = "#FFD700"
AZUL = "#4B8BFF"
CINZA = "#8B8B8B"
BG = "#0E1117"
BG2 = "#1C1C2E"


def grafico_regime(regime: dict) -> go.Figure:
    labels = list(regime.keys())
    valores = [1 if v else 0 for v in regime.values()]
    cores = [VERDE if v else VERMELHO for v in regime.values()]

    fig = go.Figure(go.Bar(
        x=labels,
        y=valores,
        marker_color=cores,
        text=["OK" if v else "OFF" for v in regime.values()],
        textposition="inside",
    ))
    fig.update_layout(
        title="Regime Macro",
        yaxis=dict(visible=False, range=[0, 1.3]),
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color="white"),
        height=250,
        margin=dict(t=40, b=20, l=20, r=20),
    )
    return fig


def grafico_setores(setores: dict) -> go.Figure:
    df = pd.DataFrame([
        {"Setor": k, "Ativo": 1 if v else 0, "Status": "ATIVO" if v else "inativo"}
        for k, v in setores.items()
    ])
    df = df.sort_values("Ativo", ascending=True)

    fig = go.Figure(go.Bar(
        x=df["Ativo"],
        y=df["Setor"],
        orientation="h",
        marker_color=[VERDE if v else CINZA for v in df["Ativo"]],
        text=df["Status"],
        textposition="inside",
    ))
    fig.update_layout(
        title="Setores com Fator Global Ativo",
        xaxis=dict(visible=False, range=[0, 1.4]),
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color="white"),
        height=380,
        margin=dict(t=40, b=20, l=180, r=20),
    )
    return fig


def grafico_correlacao_rolling(
    precos_smll: pd.Series,
    precos_russell: pd.Series,
    janela: int = 20,
) -> go.Figure:
    ret_smll = precos_smll.pct_change().dropna()
    ret_rut = precos_russell.pct_change().dropna()
    idx = ret_smll.index.intersection(ret_rut.index)
    corr = ret_smll.loc[idx].rolling(janela).corr(ret_rut.loc[idx]).dropna()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=corr.index, y=corr.values,
        mode="lines", name="Correlação",
        line=dict(color=AZUL, width=2),
        fill="tozeroy",
        fillcolor="rgba(75,139,255,0.15)",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=CINZA)
    fig.add_hline(y=0.5, line_dash="dot", line_color=AMARELO, annotation_text="0.5")
    fig.update_layout(
        title=f"Correlação Rolling {janela}d — SMLL vs Russell 2000",
        yaxis=dict(range=[-1, 1], title="Correlação"),
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color="white"),
        height=300,
        margin=dict(t=40, b=20, l=60, r=20),
    )
    return fig


def grafico_zscore_acao(
    zscores: pd.DataFrame,
    ticker: str,
    zscore_limite: float = -1.0,
) -> go.Figure:
    if ticker not in zscores.columns:
        return go.Figure()

    serie = zscores[ticker].dropna()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=serie.index, y=serie.values,
        mode="lines", name="Z-score",
        line=dict(color=AZUL, width=2),
    ))
    fig.add_hline(y=zscore_limite, line_dash="dash", line_color=VERMELHO,
                  annotation_text=f"Entrada ({zscore_limite})")
    fig.add_hline(y=0, line_dash="dot", line_color=CINZA)
    fig.update_layout(
        title=f"Z-score Distorção — {ticker}",
        yaxis=dict(title="Z-score"),
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color="white"),
        height=300,
        margin=dict(t=40, b=20, l=60, r=20),
    )
    return fig


def grafico_desempenho_etfs(precos_etfs: pd.DataFrame, janela: int = 20) -> go.Figure:
    retornos = precos_etfs.pct_change(janela).iloc[-1].dropna().sort_values()

    cores = [VERDE if v > 0 else VERMELHO for v in retornos.values]

    fig = go.Figure(go.Bar(
        x=retornos.index,
        y=(retornos.values * 100).round(2),
        marker_color=cores,
        text=[f"{v:.1f}%" for v in retornos.values * 100],
        textposition="outside",
    ))
    fig.update_layout(
        title=f"Retorno {janela}d — ETFs Setoriais EUA",
        yaxis=dict(title="Retorno (%)"),
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color="white"),
        height=350,
        margin=dict(t=40, b=40, l=60, r=20),
    )
    return fig


def grafico_carteira(carteira: pd.DataFrame) -> go.Figure:
    if carteira.empty:
        return go.Figure()

    fig = go.Figure(go.Table(
        header=dict(
            values=["Ticker", "Setor", "Z-score", "Beta"],
            fill_color="#2B2B3B",
            font=dict(color="white", size=13),
            align="left",
            height=36,
        ),
        cells=dict(
            values=[
                carteira["ticker"],
                carteira["setor"],
                carteira["zscore"].round(2),
                carteira["beta"].round(2),
            ],
            fill_color=BG2,
            font=dict(color=[
                [VERDE if z < -1.5 else AMARELO for z in carteira["zscore"]],
                ["white"] * len(carteira),
                [VERDE if z < -1.5 else AMARELO for z in carteira["zscore"]],
                ["white"] * len(carteira),
            ], size=12),
            align="left",
            height=32,
        ),
    ))
    fig.update_layout(
        paper_bgcolor=BG,
        margin=dict(t=10, b=10, l=10, r=10),
        height=60 + len(carteira) * 34,
    )
    return fig
