import time
import yfinance as yf
import pandas as pd
from config import SETORES, INDICES


def _baixar_ticker(ticker: str, periodo: str, tentativas: int = 3) -> pd.Series:
    for i in range(tentativas):
        try:
            raw = yf.download(ticker, period=periodo, interval="1d",
                              auto_adjust=True, progress=False)
            if raw.empty:
                time.sleep(1)
                continue
            close = raw["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            close = close.dropna()
            if not close.empty:
                return close
        except Exception:
            pass
        time.sleep(1)
    return pd.Series(dtype=float)


def baixar_etfs_setoriais(periodo="1y") -> pd.DataFrame:
    resultado = {}
    for nome, ticker in SETORES.items():
        serie = _baixar_ticker(ticker, periodo)
        if not serie.empty:
            resultado[nome] = serie
    return pd.DataFrame(resultado)


def baixar_indices(periodo="1y") -> pd.DataFrame:
    resultado = {}
    for nome, ticker in INDICES.items():
        serie = _baixar_ticker(ticker, periodo)
        if not serie.empty:
            resultado[nome] = serie
    return pd.DataFrame(resultado)


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
