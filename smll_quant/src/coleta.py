import yfinance as yf
import pandas as pd
from config import SETORES, INDICES

INDICES_CRITICOS = ["ibov", "smll", "russell", "vix"]


def _baixar_grupo(tickers: list, periodo: str) -> pd.DataFrame:
    data = yf.download(tickers, period=periodo, interval="1d", auto_adjust=True, progress=False)["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame(name=tickers[0])
    return data.dropna(axis=1, how="all")


def baixar_etfs_setoriais(periodo="1y") -> pd.DataFrame:
    tickers = list(SETORES.values())
    data = _baixar_grupo(tickers, periodo)
    return data.rename(columns={v: k for k, v in SETORES.items()})


def baixar_indices(periodo="1y") -> pd.DataFrame:
    ticker_para_nome = {v: k for k, v in INDICES.items()}
    tickers = list(INDICES.values())
    data = _baixar_grupo(tickers, periodo)
    data = data.rename(columns=ticker_para_nome)

    # Retry individual para indices criticos ausentes
    faltando = [n for n in INDICES_CRITICOS if n not in data.columns]
    for nome in faltando:
        ticker = INDICES[nome]
        try:
            serie = yf.download(ticker, period=periodo, interval="1d", auto_adjust=True, progress=False)["Close"]
            if not serie.empty:
                data[nome] = serie
        except Exception:
            pass

    return data


def baixar_acoes_smll(tickers: list[str], periodo="1y") -> pd.DataFrame:
    tickers_sa = [t if t.endswith(".SA") else t + ".SA" for t in tickers]
    data = yf.download(tickers_sa, period=periodo, interval="1d", auto_adjust=True, progress=False)["Close"]
    return data


if __name__ == "__main__":
    print("Baixando ETFs setoriais EUA...")
    etfs = baixar_etfs_setoriais()
    print(etfs.tail())

    print("\nBaixando índices...")
    indices = baixar_indices()
    print(indices.tail())
