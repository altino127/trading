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


RISCO_COR = {
    "Baixa Volatilidade - baixo risco":  VERDE,
    "Media Volatilidade - medio risco":  AMARELO,
    "Alta Volatilidade - alto risco":    VERMELHO,
}

RISCO_EMOJI = {
    "Baixa Volatilidade - baixo risco":  "Baixo risco",
    "Media Volatilidade - medio risco":  "Medio risco",
    "Alta Volatilidade - alto risco":    "Alto risco",
}

RISCO_BG = {
    "Baixa Volatilidade - baixo risco":  "rgba(0,200,150,0.12)",
    "Media Volatilidade - medio risco":  "rgba(255,215,0,0.10)",
    "Alta Volatilidade - alto risco":    "rgba(255,75,75,0.12)",
}


def grafico_carteira(carteira: pd.DataFrame) -> go.Figure:
    if carteira.empty:
        return go.Figure()

    tem_risco    = "risco" in carteira.columns
    tem_peer     = "zscore_peer" in carteira.columns
    tem_vol      = "vol" in carteira.columns
    tem_modo     = "modo" in carteira.columns
    tem_peso     = "peso" in carteira.columns

    def _cor_risco(r):
        return RISCO_COR.get(r, CINZA) if tem_risco else CINZA

    def _label_risco(r):
        return RISCO_EMOJI.get(r, r) if tem_risco else ""

    def _bg_risco(r):
        return RISCO_BG.get(r, BG2) if tem_risco else BG2

    riscos    = carteira["risco"].tolist() if tem_risco else [""] * len(carteira)
    cor_risco = [_cor_risco(r) for r in riscos]
    bg_risco  = [_bg_risco(r) for r in riscos]
    lbl_risco = [_label_risco(r) for r in riscos]

    zpeer_vals = (
        [f"{v:+.2f}" if not pd.isna(v) else "n/a"
         for v in carteira["zscore_peer"]]
        if tem_peer else ["n/a"] * len(carteira)
    )
    vol_vals = (
        [f"{v:.0%}" if not pd.isna(v) else "n/a"
         for v in carteira["vol"]]
        if tem_vol else ["n/a"] * len(carteira)
    )
    modo_vals = carteira["modo"].str.upper().tolist() if tem_modo else [""] * len(carteira)
    peso_vals = (
        [f"{v:.0%}" for v in carteira["peso"]]
        if tem_peso else ["n/a"] * len(carteira)
    )

    headers = ["Ticker", "Setor", "Modo", "Peso", "Z-IBOV", "Z-Peer", "Vol", "Risco"]
    valores  = [
        carteira["ticker"],
        carteira["setor"],
        modo_vals,
        peso_vals,
        carteira["zscore"].round(2),
        zpeer_vals,
        vol_vals,
        lbl_risco,
    ]

    fig = go.Figure(go.Table(
        columnwidth=[90, 160, 60, 60, 70, 70, 60, 130],
        header=dict(
            values=headers,
            fill_color="#2B2B3B",
            font=dict(color="white", size=12),
            align="left",
            height=38,
        ),
        cells=dict(
            values=valores,
            fill_color=[
                [BG2] * len(carteira),
                [BG2] * len(carteira),
                [BG2] * len(carteira),
                [BG2] * len(carteira),
                [BG2] * len(carteira),
                [BG2] * len(carteira),
                [BG2] * len(carteira),
                bg_risco,
            ],
            font=dict(
                color=[
                    ["white"] * len(carteira),
                    ["white"] * len(carteira),
                    [AZUL] * len(carteira),
                    [AMARELO] * len(carteira),
                    ["white"] * len(carteira),
                    ["white"] * len(carteira),
                    ["white"] * len(carteira),
                    cor_risco,
                ],
                size=12,
            ),
            align="left",
            height=34,
        ),
    ))
    fig.update_layout(
        paper_bgcolor=BG,
        margin=dict(t=10, b=10, l=10, r=10),
        height=70 + len(carteira) * 36,
    )
    return fig


def grafico_ordens(ordens: pd.DataFrame) -> go.Figure:
    if ordens.empty:
        return go.Figure()

    riscos    = ordens["risco"].tolist()
    cor_risco = [RISCO_COR.get(r, CINZA) for r in riscos]
    bg_risco  = [RISCO_BG.get(r, BG2)   for r in riscos]
    lbl_risco = [RISCO_EMOJI.get(r, r)   for r in riscos]

    def fmt_preco(v):
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if not pd.isna(v) else "n/a"

    entradas = [fmt_preco(v) for v in ordens["preco_entrada"]]
    stops_r  = [f"{v:.1%}" for v in ordens["stop_pct"]]
    stops_p  = [fmt_preco(v) for v in ordens["stop_preco"]]
    alvos_r  = [f"+{v:.1%}" for v in ordens["alvo_pct"]]
    alvos_p  = [fmt_preco(v) for v in ordens["alvo_preco"]]
    rr_vals  = [f"{v:.1f}x" for v in ordens["risco_retorno"]]

    headers = ["Ticker", "Setor", "Modo", "Operacao", "Entrada", "Stop %", "Stop R$", "Alvo %", "Alvo R$", "R/R", "Saida", "Risco"]
    valores  = [
        ordens["ticker"],
        ordens["setor"],
        ordens["modo"],
        ordens["operacao"],
        entradas,
        stops_r,
        stops_p,
        alvos_r,
        alvos_p,
        rr_vals,
        ordens["dt_saida"],
        lbl_risco,
    ]

    n = len(ordens)

    fig = go.Figure(go.Table(
        columnwidth=[80, 140, 55, 80, 90, 60, 90, 60, 90, 45, 90, 120],
        header=dict(
            values=headers,
            fill_color="#2B2B3B",
            font=dict(color="white", size=11),
            align="center",
            height=38,
        ),
        cells=dict(
            values=valores,
            fill_color=[
                [BG2] * n,
                [BG2] * n,
                [BG2] * n,
                ["rgba(0,200,150,0.15)"] * n,
                [BG2] * n,
                ["rgba(255,75,75,0.12)"] * n,
                ["rgba(255,75,75,0.12)"] * n,
                ["rgba(0,200,150,0.12)"] * n,
                ["rgba(0,200,150,0.12)"] * n,
                [BG2] * n,
                [BG2] * n,
                bg_risco,
            ],
            font=dict(
                color=[
                    ["white"] * n,
                    ["white"] * n,
                    [AZUL] * n,
                    [VERDE] * n,
                    ["white"] * n,
                    [VERMELHO] * n,
                    [VERMELHO] * n,
                    [VERDE] * n,
                    [VERDE] * n,
                    [AMARELO] * n,
                    ["white"] * n,
                    cor_risco,
                ],
                size=11,
            ),
            align="center",
            height=34,
        ),
    ))
    fig.update_layout(
        paper_bgcolor=BG,
        margin=dict(t=10, b=10, l=10, r=10),
        height=70 + n * 36,
    )
    return fig
