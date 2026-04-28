import yfinance as yf
import pandas as pd
from config import SETORES, INDICES


def baixar_etfs_setoriais(periodo="1y") -> pd.DataFrame:
    tickers = list(SETORES.values())
    data = yf.download(tickers, period=periodo, interval="1d", auto_adjust=True, progress=False)["Close"]
    data.columns = {v: k for k, v in SETORES.items()}[data.columns] if len(tickers) == 1 else data.rename(
        columns={v: k for k, v in SETORES.items()}
    )
    return data


def baixar_indices(periodo="1y") -> pd.DataFrame:
    tickers = list(INDICES.values())
    data = yf.download(tickers, period=periodo, interval="1d", auto_adjust=True, progress=False)["Close"]
    data = data.rename(columns={v: k for k, v in INDICES.items()})
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
