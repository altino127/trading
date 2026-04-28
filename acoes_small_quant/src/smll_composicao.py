"""
Composição manual do índice SMLL (Small Cap B3).
Fonte: B3 — atualizar trimestralmente.
Mapeamento setor B3 → setor estratégia.
"""

SMLL_COMPOSICAO = {
    # Financeiro
    "BMGB4":  "Financeiro",
    "IRBR3":  "Financeiro",
    "BPAC11": "Financeiro",
    "WIZC3":  "Financeiro",
    "APER3":  "Financeiro",

    # Consumo Discricionário
    "SOMA3":  "Consumo Discricionário",
    "VIVA3":  "Consumo Discricionário",
    "SBFG3":  "Consumo Discricionário",
    "CEAB3":  "Consumo Discricionário",
    "TFCO4":  "Consumo Discricionário",

    # Consumo Básico
    "SMFT3":  "Consumo Básico",
    "MDIA3":  "Consumo Básico",
    "PCAR3":  "Consumo Básico",

    # Saúde
    "HAPV3":  "Saúde",
    "ONCO3":  "Saúde",
    "MATD3":  "Saúde",
    "CMIN3":  "Saúde",

    # Tecnologia
    "TOTVS3": "Tecnologia",
    "LWSA3":  "Tecnologia",
    "DESK3":  "Tecnologia",
    "BRIT3":  "Tecnologia",

    # Energia
    "CGAS5":  "Energia",
    "EGIE3":  "Energia",
    "ENGI11": "Energia",

    # Materiais Básicos
    "AURA33": "Materiais Básicos",
    "MBLY3":  "Materiais Básicos",
    "RECV3":  "Materiais Básicos",

    # Utilidades
    "SAPR11": "Utilidades",
    "CSMG3":  "Utilidades",
    "ENBR3":  "Utilidades",
    "CPFE3":  "Utilidades",

    # Imobiliário
    "CYRE3":  "Imobiliário",
    "EVEN3":  "Imobiliário",
    "TEND3":  "Imobiliário",
    "JHSF3":  "Imobiliário",

    # Comunicações
    "TIMS3":  "Comunicações",
    "LVTC3":  "Comunicações",

    # Industrial
    "RAIL3":  "Industrial",
    "POMO4":  "Industrial",
    "FRAS3":  "Industrial",
    "TUPY3":  "Industrial",
}


def acoes_por_setor(setor: str) -> list[str]:
    return [ticker for ticker, s in SMLL_COMPOSICAO.items() if s == setor]


def todos_os_tickers() -> list[str]:
    return list(SMLL_COMPOSICAO.keys())
