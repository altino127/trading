import pandas as pd
import numpy as np


def proxima_segunda() -> pd.Timestamp:
    hoje = pd.Timestamp.today().normalize()
    dias = (7 - hoje.weekday()) % 7
    return hoje + pd.Timedelta(days=dias if dias > 0 else 7)


def data_saida(dias_hold: int = 5) -> pd.Timestamp:
    return proxima_segunda() + pd.offsets.BDay(dias_hold - 1)


def gerar_ordens(
    carteira: pd.DataFrame,
    precos_acoes: pd.DataFrame,
    dias_hold: int = 5,
) -> pd.DataFrame:
    if carteira.empty:
        return pd.DataFrame()

    dt_entrada = proxima_segunda()
    dt_saida   = data_saida(dias_hold)

    ordens = []
    for _, row in carteira.iterrows():
        ticker = row["ticker"]
        modo   = row.get("modo", "bear")
        risco  = row.get("risco", "")
        vol    = float(row["vol"]) if not pd.isna(row.get("vol", np.nan)) else 0.45

        # Preco de referencia (ultimo fechamento)
        if ticker in precos_acoes.columns:
            preco = float(precos_acoes[ticker].dropna().iloc[-1])
        else:
            preco = np.nan

        # Volatilidade do periodo de holding
        daily_vol   = vol / np.sqrt(252)
        holding_vol = daily_vol * np.sqrt(dias_hold)

        # Stop: 2 desvios do periodo de holding (minimo 2%, maximo 15%)
        stop_pct = float(np.clip(-2.0 * holding_vol, -0.15, -0.02))

        # Alvo: magnitude do z-score × vol do periodo (minimo risco/retorno 1.5:1)
        if modo == "bull":
            z_mag = abs(float(row.get("zscore", 1.0)))
        else:
            zpeer = row.get("zscore_peer", np.nan)
            z_mag = abs(float(zpeer)) if not pd.isna(zpeer) else 1.0

        alvo_pct = float(np.clip(z_mag * holding_vol, abs(stop_pct) * 1.5, 0.25))

        rr = round(alvo_pct / abs(stop_pct), 1)

        ordens.append({
            "ticker":        ticker,
            "setor":         row.get("setor", ""),
            "operacao":      "COMPRAR",
            "modo":          modo.upper(),
            "preco_entrada": round(preco, 2) if not pd.isna(preco) else np.nan,
            "stop_pct":      stop_pct,
            "stop_preco":    round(preco * (1 + stop_pct), 2) if not pd.isna(preco) else np.nan,
            "alvo_pct":      alvo_pct,
            "alvo_preco":    round(preco * (1 + alvo_pct), 2) if not pd.isna(preco) else np.nan,
            "risco_retorno": rr,
            "dt_entrada":    dt_entrada.strftime("%d/%m/%Y"),
            "dt_saida":      dt_saida.strftime("%d/%m/%Y"),
            "risco":         risco,
        })

    return pd.DataFrame(ordens)
