import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path

from coleta import baixar_etfs_setoriais, baixar_indices, baixar_acoes_smll
from smll_composicao import todos_os_tickers, SMLL_COMPOSICAO
from beta import calcular_retornos, beta_todos
from distorcao import calcular_distorcoes, calcular_zscore_peer, calcular_volatilidade, snapshot_atual
from momentum import regime_macro_ok, setores_ativos, modo_mercado
from scanner import rodar_scanner
from backteste import rodar_backteste
from metricas import resumo_metricas, retorno_por_setor, equity_curve
from graficos_bt import (
    grafico_equity,
    grafico_drawdown,
    grafico_retorno_semanal,
    grafico_retorno_por_setor,
    grafico_distribuicao_trades,
)
from graficos import (
    grafico_regime,
    grafico_setores,
    grafico_correlacao_rolling,
    grafico_zscore_acao,
    grafico_desempenho_etfs,
    grafico_carteira,
    grafico_ordens,
)
from ordens import gerar_ordens
from config import JANELA_BETA_DIAS, JANELA_MOMENTUM_DIAS, ZSCORE_ENTRADA_BULL

DATA_DIR = Path(__file__).parent.parent / "data"
REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


st.set_page_config(
    page_title="SmallQuant BR",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .metric-label { font-size: 0.85rem; }
    h1, h2, h3 { color: #FFFFFF; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def carregar_dados(periodo):
    etfs = baixar_etfs_setoriais(periodo=periodo)
    indices = baixar_indices(periodo=periodo)
    tickers = todos_os_tickers()
    acoes = baixar_acoes_smll(tickers, periodo=periodo)
    return etfs, indices, acoes


@st.cache_data(ttl=3600)
def calcular_tudo(periodo):
    etfs, indices, acoes = carregar_dados(periodo)

    ret_acoes   = calcular_retornos(acoes)
    ret_indices = calcular_retornos(indices)
    ret_ibov    = ret_indices["ibov"].dropna()

    betas        = beta_todos(ret_acoes, ret_ibov)
    zscores      = calcular_distorcoes(ret_acoes, ret_ibov, betas)
    zscores_peer = calcular_zscore_peer(ret_acoes, SMLL_COMPOSICAO)
    vols         = calcular_volatilidade(ret_acoes).iloc[-1].dropna()

    spy     = indices["spy"].dropna() if "spy" in indices.columns else None
    regime  = regime_macro_ok(indices)
    setores = setores_ativos(etfs, regime, spy)
    modo    = modo_mercado(regime)

    carteira, _ = rodar_scanner(acoes, indices, etfs)

    return etfs, indices, acoes, betas, zscores, zscores_peer, regime, setores, modo, carteira


# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("SmallQuant BR")
    st.caption("Carteira semanal — Small Caps B3")
    st.divider()

    periodo = st.selectbox("Período de dados", ["6mo", "1y", "2y"], index=1)
    janela_corr = st.slider("Janela correlação (dias)", 10, 60, JANELA_MOMENTUM_DIAS)

    st.divider()
    st.subheader("Backteste")
    bt_inicio = st.text_input("Início", value="2023-01-01")
    bt_fim    = st.text_input("Fim",    value=str(date.today()))
    bt_hold   = st.slider("Dias de holding", 3, 10, 5)
    rodar_bt  = st.button("Rodar Backteste", use_container_width=True)

    st.divider()
    atualizar = st.button("Atualizar dados", use_container_width=True)
    if atualizar:
        st.cache_data.clear()
        st.rerun()

    st.divider()
    semana = date.today().isocalendar()
    st.caption(f"Semana {semana.week}/{semana.year}")
    st.caption(f"Hoje: {date.today().strftime('%d/%m/%Y')}")


# ── Carregamento ─────────────────────────────────────────────────────────────
with st.spinner("Baixando e calculando dados..."):
    etfs, indices, acoes, betas, zscores, zscores_peer, regime, setores, modo, carteira = calcular_tudo(periodo)


# ── Header ───────────────────────────────────────────────────────────────────
st.title("SmallQuant BR — Carteira Semanal")
st.caption(f"Semana {semana.week}/{semana.year}  |  Modo: {modo.upper()}  |  Z-score bull: {ZSCORE_ENTRADA_BULL}  |  Beta janela: {JANELA_BETA_DIAS}d")
st.divider()


# ── Métricas rápidas ─────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    ibov = indices["ibov"].dropna()
    ret_ibov = (ibov.iloc[-1] / ibov.iloc[-22] - 1) * 100
    st.metric("IBOV (22d)", f"{ret_ibov:.1f}%", delta=f"{ret_ibov:.1f}%")

with col2:
    smll = indices["smll"].dropna()
    ret_smll = (smll.iloc[-1] / smll.iloc[-22] - 1) * 100
    st.metric("SMLL (22d)", f"{ret_smll:.1f}%", delta=f"{ret_smll:.1f}%")

with col3:
    rut = indices["russell"].dropna()
    ret_rut = (rut.iloc[-1] / rut.iloc[-22] - 1) * 100
    st.metric("Russell 2000 (22d)", f"{ret_rut:.1f}%", delta=f"{ret_rut:.1f}%")

with col4:
    vix_val = indices["vix"].iloc[-1]
    st.metric("VIX", f"{vix_val:.1f}", delta=f"{'OK' if vix_val < 25 else 'ALTO'}")

with col5:
    n_ativos = sum(v for v in setores.values())
    n_carteira = len(carteira) if not carteira.empty else 0
    st.metric("Setores ativos", f"{n_ativos}/11", delta=f"{n_carteira} posicoes")


st.divider()


# ── Carteira da semana ────────────────────────────────────────────────────────
modo_label = "BEAR MODE — Forca Relativa" if modo == "bear" else "BULL MODE — Reversao a Media"
st.subheader(f"Carteira da Semana  [{modo_label}]")

if carteira.empty:
    st.warning("Nenhuma posicao gerada.")
else:
    # Contadores de risco
    if "risco" in carteira.columns:
        c_baixo  = (carteira["risco"].str.contains("baixo")).sum()
        c_medio  = (carteira["risco"].str.contains("medio")).sum()
        c_alto   = (carteira["risco"].str.contains("alto")).sum()
        rb, rm, ra = st.columns(3)
        rb.metric("Baixo risco",  f"{c_baixo} posicao(oes)",  delta="Baixa Volatilidade")
        rm.metric("Medio risco",  f"{c_medio} posicao(oes)",  delta="Media Volatilidade")
        ra.metric("Alto risco",   f"{c_alto} posicao(oes)",   delta="Alta Volatilidade")
        st.markdown("")

    st.plotly_chart(grafico_carteira(carteira), use_container_width=True)

    csv = carteira.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Exportar carteira (.csv)",
        data=csv,
        file_name=f"carteira_{semana.year}_W{semana.week:02d}.csv",
        mime="text/csv",
    )


st.divider()


# ── Ordens da Semana ─────────────────────────────────────────────────────────
st.subheader("Ordens da Semana — Como Operar")

if not carteira.empty:
    ordens = gerar_ordens(carteira, acoes, dias_hold=5)
    st.plotly_chart(grafico_ordens(ordens), use_container_width=True)

    csv_ordens = ordens.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Exportar ordens (.csv)",
        data=csv_ordens,
        file_name=f"ordens_{semana.year}_W{semana.week:02d}.csv",
        mime="text/csv",
    )
else:
    st.info("Nenhuma ordem gerada — carteira vazia.")


st.divider()


# ── Regime e Setores ──────────────────────────────────────────────────────────
col_a, col_b = st.columns([1, 1.6])

with col_a:
    st.plotly_chart(grafico_regime(regime), use_container_width=True)

with col_b:
    st.plotly_chart(grafico_setores(setores), use_container_width=True)


st.divider()


# ── ETFs Setoriais ────────────────────────────────────────────────────────────
st.subheader("Desempenho ETFs Setoriais EUA")
st.plotly_chart(grafico_desempenho_etfs(etfs, janela=JANELA_MOMENTUM_DIAS), use_container_width=True)


st.divider()


# ── Correlação SMLL vs Russell ────────────────────────────────────────────────
st.subheader("Correlação SMLL × Russell 2000")
st.plotly_chart(
    grafico_correlacao_rolling(indices["smll"], indices["russell"], janela=janela_corr),
    use_container_width=True,
)


st.divider()


# ── Análise por ação ──────────────────────────────────────────────────────────
st.subheader("Análise Individual — Z-score por Ação")

tickers_disponíveis = sorted(zscores.columns.tolist())
ticker_sel = st.selectbox("Selecione a ação", tickers_disponíveis)

if ticker_sel:
    snap_acao = zscores[ticker_sel].dropna()
    peer_acao = zscores_peer[ticker_sel].dropna() if ticker_sel in zscores_peer.columns else pd.Series()
    beta_acao = betas[ticker_sel].dropna() if ticker_sel in betas.columns else pd.Series()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if not snap_acao.empty:
            st.metric("Z-score vs IBOV", f"{snap_acao.iloc[-1]:.2f}")
    with c2:
        if not peer_acao.empty:
            st.metric("Z-score vs Peers", f"{peer_acao.iloc[-1]:.2f}")
    with c3:
        if not beta_acao.empty:
            st.metric("Beta (vs IBOV)", f"{beta_acao.iloc[-1]:.2f}")
    with c4:
        if not carteira.empty and "ticker" in carteira.columns:
            match = carteira[carteira["ticker"] == ticker_sel]
            if not match.empty and "risco" in match.columns:
                risco_label = match.iloc[0]["risco"].split(" - ")[-1]
                st.metric("Risco", risco_label)

    st.plotly_chart(
        grafico_zscore_acao(zscores, ticker_sel, ZSCORE_ENTRADA_BULL),
        use_container_width=True,
    )


st.divider()


# ── Backteste ─────────────────────────────────────────────────────────────────
st.subheader("Backteste Walk-Forward")

if rodar_bt:
    with st.spinner("Rodando backteste... (pode levar 30–60s)"):
        trades_bt, equity_bt = rodar_backteste(
            acoes, indices, etfs,
            inicio=bt_inicio,
            fim=bt_fim,
            dias_hold=bt_hold,
        )

    st.session_state["trades_bt"] = trades_bt
    st.session_state["equity_bt"] = equity_bt

if "equity_bt" in st.session_state and not st.session_state["equity_bt"].empty:
    trades_bt = st.session_state["trades_bt"]
    equity_bt = st.session_state["equity_bt"]

    metricas = resumo_metricas(trades_bt, equity_bt, indices["ibov"], indices["smll"])

    cols = st.columns(4)
    chaves = list(metricas.keys())
    for i, col in enumerate(cols):
        for j in range(i, len(chaves), 4):
            col.metric(chaves[j], metricas[chaves[j]])

    st.divider()

    st.plotly_chart(grafico_equity(equity_bt, indices["ibov"], indices["smll"]), use_container_width=True)

    col_dd, col_wk = st.columns(2)
    with col_dd:
        st.plotly_chart(grafico_drawdown(equity_bt), use_container_width=True)
    with col_wk:
        st.plotly_chart(grafico_retorno_semanal(equity_bt), use_container_width=True)

    st.divider()

    col_set, col_dist = st.columns(2)
    with col_set:
        por_setor = retorno_por_setor(trades_bt)
        st.plotly_chart(grafico_retorno_por_setor(por_setor), use_container_width=True)
    with col_dist:
        st.plotly_chart(grafico_distribuicao_trades(trades_bt), use_container_width=True)

    st.divider()
    st.subheader("Todos os Trades")
    st.dataframe(
        trades_bt.style.format({
            "retorno": "{:.2%}",
            "zscore": "{:.2f}",
            "beta": "{:.2f}",
        }),
        use_container_width=True,
        height=400,
    )

    csv_trades = trades_bt.to_csv(index=False).encode("utf-8")
    st.download_button("Exportar trades (.csv)", csv_trades, "trades_backteste.csv", "text/csv")
else:
    st.info("Configure o período na sidebar e clique em 'Rodar Backteste'.")
