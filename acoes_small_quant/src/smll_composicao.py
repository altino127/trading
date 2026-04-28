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
    "BBSE3":  "Financeiro",

    # Consumo Discricionário
    "VIVA3":  "Consumo Discricionário",
    "SBFG3":  "Consumo Discricionário",
    "CEAB3":  "Consumo Discricionário",
    "TFCO4":  "Consumo Discricionário",
    "ALPA4":  "Consumo Discricionário",

    # Consumo Básico
    "SMFT3":  "Consumo Básico",
    "MDIA3":  "Consumo Básico",
    "PCAR3":  "Consumo Básico",

    # Saúde
    "HAPV3":  "Saúde",
    "ONCO3":  "Saúde",
    "MATD3":  "Saúde",
    "FLRY3":  "Saúde",

    # Tecnologia
    "TOTS3":  "Tecnologia",
    "LWSA3":  "Tecnologia",
    "DESK3":  "Tecnologia",
    "POSI3":  "Tecnologia",

    # Energia
    "CGAS5":  "Energia",
    "EGIE3":  "Energia",
    "ENGI11": "Energia",

    # Materiais Básicos
    "AURA33": "Materiais Básicos",
    "CMIN3":  "Materiais Básicos",
    "RECV3":  "Materiais Básicos",

    # Utilidades
    "SAPR11": "Utilidades",
    "CSMG3":  "Utilidades",
    "CPFE3":  "Utilidades",
    "CASN3":  "Utilidades",

    # Imobiliário
    "CYRE3":  "Imobiliário",
    "EVEN3":  "Imobiliário",
    "TEND3":  "Imobiliário",
    "JHSF3":  "Imobiliário",

    # Comunicações
    "TIMS3":  "Comunicações",
    "OIBR3":  "Comunicações",

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
