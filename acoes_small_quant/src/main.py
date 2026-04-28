import pandas as pd
from coleta import baixar_etfs_setoriais, baixar_indices, baixar_acoes_smll
from smll_composicao import todos_os_tickers
from scanner import rodar_scanner
from datetime import date


def fase1_coleta(periodo="1y"):
    print("=== FASE 1: Coleta de Dados ===\n")

    print("[1/3] ETFs setoriais EUA...")
    etfs = baixar_etfs_setoriais(periodo=periodo)
    etfs.to_parquet("../data/etfs_setoriais.parquet")
    print(f"      {etfs.shape[1]} ETFs | {etfs.shape[0]} dias\n")

    print("[2/3] Índices (IBOV, SMLL, Russell, VIX...)...")
    indices = baixar_indices(periodo=periodo)
    indices.to_parquet("../data/indices.parquet")
    print(f"      {indices.shape[1]} índices | {indices.shape[0]} dias\n")

    print("[3/3] Ações do SMLL...")
    tickers = todos_os_tickers()
    acoes = baixar_acoes_smll(tickers, periodo=periodo)
    acoes.to_parquet("../data/acoes_smll.parquet")
    print(f"      {acoes.shape[1]} ações | {acoes.shape[0]} dias\n")

    return etfs, indices, acoes


def fase2_scanner(etfs, indices, acoes):
    print("\n=== FASE 2: Scanner de Distorções ===\n")
    carteira = rodar_scanner(acoes, indices, etfs)

    if not carteira.empty:
        semana = date.today().isocalendar()
        nome = f"../reports/carteira_{semana.year}_W{semana.week:02d}.csv"
        carteira.to_csv(nome, index=False)
        print(f"\nCarteira salva em: {nome}")

    return carteira


def main():
    etfs, indices, acoes = fase1_coleta(periodo="1y")
    carteira = fase2_scanner(etfs, indices, acoes)
    return carteira


if __name__ == "__main__":
    main()
