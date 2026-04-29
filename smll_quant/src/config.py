SETORES = {
    "Financeiro":             "XLF",
    "Consumo Discricionário": "XLY",
    "Consumo Básico":         "XLP",
    "Saúde":                  "XLV",
    "Tecnologia":             "XLK",
    "Energia":                "XLE",
    "Materiais Básicos":      "XLB",
    "Utilidades":             "XLU",
    "Imobiliário":            "XLRE",
    "Industrial":             "XLI",
}

INDICES = {
    "ibov":       "^BVSP",
    "smll":       "SMAL11.SA",
    "russell":    "^RUT",
    "sp500":      "^GSPC",
    "spy":        "SPY",
    "vix":        "^VIX",
    "usdbrl":     "BRL=X",
    "dxy":        "DX-Y.NYB",
    "treasury10": "^TNX",
}

JANELA_BETA_DIAS      = 60
JANELA_MOMENTUM_DIAS  = 20
JANELA_PEER_DIAS      = 20   # janela para z-score peer-relativo

# Bull mode (mercado em alta): ação atrasada vs IBOV → reversão
ZSCORE_ENTRADA_BULL   = -1.0
ZSCORE_ENTRADA        = ZSCORE_ENTRADA_BULL

# Bear mode (mercado em queda): ação liderando o setor → força relativa
ZSCORE_PEER_BEAR      = 0.6

VIX_LIMITE            = 25
MACRO_MINIMO_ON       = 3    # quantos dos 4 indicadores macro precisam estar OK para Bull mode

N_SETORES_CARTEIRA    = 5    # quantos setores entram na carteira (os N mais fortes)
PESOS_RANK            = [0.30, 0.25, 0.20, 0.15, 0.10]  # peso por ranking de forca do setor

# Classificacao de risco por volatilidade anualizada
VOL_BAIXA             = 0.35   # < 35% a.a. → baixo risco
VOL_ALTA              = 0.65   # > 65% a.a. → alto risco
