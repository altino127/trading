"""
Composição do índice SMLL (Small Cap B3) — 110 ações.
Fonte: B3 — atualizar trimestralmente.
Setor Comunicações removido (universo pequeno e baixa liquidez).
"""

SMLL_COMPOSICAO = {
    # ── Financeiro (6) ───────────────────────────────────────────
    "ABCB4":  "Financeiro",   # Banco ABC Brasil
    "BRBI11": "Financeiro",   # BR Advisory Partners
    "BRSR6":  "Financeiro",   # Banrisul
    "CASH3":  "Financeiro",   # Méliuz (fintech)
    "IRBR3":  "Financeiro",   # IRB Brasil RE
    "RIAA3":  "Financeiro",   # Rio Alto

    # ── Consumo Discricionário (24) ───────────────────────────────
    "ALPA4":  "Consumo Discricionário",   # Alpargatas
    "ALOS3":  "Consumo Discricionário",   # Allos (shoppings)
    "ANIM3":  "Consumo Discricionário",   # Anima Educação
    "AUAU3":  "Consumo Discricionário",   # Petlove
    "AZZA3":  "Consumo Discricionário",   # AZZA (Arezzo+Soma)
    "BHIA3":  "Consumo Discricionário",   # Casas Bahia
    "CEAB3":  "Consumo Discricionário",   # C&A Brasil
    "COGN3":  "Consumo Discricionário",   # Cogna
    "CVCB3":  "Consumo Discricionário",   # CVC Brasil
    "GRND3":  "Consumo Discricionário",   # Grendene
    "IGTI11": "Consumo Discricionário",   # Iguatemi
    "LJQQ3":  "Consumo Discricionário",   # Lojas Quero-Quero
    "LREN3":  "Consumo Discricionário",   # Lojas Renner
    "MGLU3":  "Consumo Discricionário",   # Magazine Luiza
    "MULT3":  "Consumo Discricionário",   # Multiplan
    "NATU3":  "Consumo Discricionário",   # Natura
    "SBFG3":  "Consumo Discricionário",   # SBF Group (Centauro)
    "SEER3":  "Consumo Discricionário",   # Ser Educacional
    "SMFT3":  "Consumo Discricionário",   # Smart Fit
    "SYNE3":  "Consumo Discricionário",   # Synergia Educacional
    "TFCO4":  "Consumo Discricionário",   # Technos
    "VIVA3":  "Consumo Discricionário",   # Vivara
    "VULC3":  "Consumo Discricionário",   # Vulcabras
    "YDUQ3":  "Consumo Discricionário",   # Yduqs

    # ── Consumo Básico (10) ───────────────────────────────────────
    "AGRO3":  "Consumo Básico",   # BrasilAgro
    "ASAI3":  "Consumo Básico",   # Assaí Atacadista
    "BEEF3":  "Consumo Básico",   # Minerva Foods
    "CAML3":  "Consumo Básico",   # Camil Alimentos
    "GMAT3":  "Consumo Básico",   # Grupo Mateus
    "MDIA3":  "Consumo Básico",   # M. Dias Branco
    "SLCE3":  "Consumo Básico",   # SLC Agrícola
    "SMTO3":  "Consumo Básico",   # São Martinho
    "SOJA3":  "Consumo Básico",   # Boa Safra
    "TTEN3":  "Consumo Básico",   # 3tentos

    # ── Saúde (9) ─────────────────────────────────────────────────
    "BLAU3":  "Saúde",   # Blau Farmacêutica
    "FLRY3":  "Saúde",   # Fleury
    "HAPV3":  "Saúde",   # Hapvida
    "HYPE3":  "Saúde",   # Hypera
    "ODPV3":  "Saúde",   # Odontoprev
    "ONCO3":  "Saúde",   # Oncoclínicas
    "PGMN3":  "Saúde",   # Pague Menos
    "PNVL3":  "Saúde",   # Panvel
    "QUAL3":  "Saúde",   # Qualicorp

    # ── Tecnologia (7) ────────────────────────────────────────────
    "AMOB3":  "Tecnologia",   # Americanas / Bemobi
    "BMOB3":  "Tecnologia",   # Bemobi Mobile
    "DESK3":  "Tecnologia",   # Desk.net
    "INTB3":  "Tecnologia",   # Intelbras
    "LWSA3":  "Tecnologia",   # Locaweb
    "POSI3":  "Tecnologia",   # Positivo
    "VLID3":  "Tecnologia",   # Valid

    # ── Energia (3) ───────────────────────────────────────────────
    "BRAV3":  "Energia",   # Brava Energia
    "CSAN3":  "Energia",   # Cosan
    "RECV3":  "Energia",   # PetroRecôncavo

    # ── Materiais Básicos (10) ────────────────────────────────────
    "BRAP4":  "Materiais Básicos",   # Bradespar
    "BRKM5":  "Materiais Básicos",   # Braskem
    "CBAV3":  "Materiais Básicos",   # CBA (alumínio)
    "CSNA3":  "Materiais Básicos",   # CSN
    "DXCO3":  "Materiais Básicos",   # Dexco
    "FESA4":  "Materiais Básicos",   # Ferbasa
    "GOAU4":  "Materiais Básicos",   # Gerdau Metalúrgica
    "RANI3":  "Materiais Básicos",   # Irani
    "UNIP6":  "Materiais Básicos",   # Unipar
    "USIM5":  "Materiais Básicos",   # Usiminas

    # ── Utilidades (5) ────────────────────────────────────────────
    "ALUP11": "Utilidades",   # Alupar
    "AURE3":  "Utilidades",   # Auren Energia
    "CSMG3":  "Utilidades",   # Copasa
    "SAPR11": "Utilidades",   # Sanepar
    "TAEE11": "Utilidades",   # Taesa

    # ── Imobiliário (15) ──────────────────────────────────────────
    "CURY3":  "Imobiliário",   # Cury
    "CYRE3":  "Imobiliário",   # Cyrela
    "CYRE4":  "Imobiliário",   # Cyrela PN
    "DIRR3":  "Imobiliário",   # Direcional
    "EVEN3":  "Imobiliário",   # Even
    "EZTC3":  "Imobiliário",   # EZTec
    "GFSA3":  "Imobiliário",   # Gafisa
    "HBOR3":  "Imobiliário",   # Helbor
    "JHSF3":  "Imobiliário",   # JHSF
    "LAVV3":  "Imobiliário",   # Lavvi
    "LOGG3":  "Imobiliário",   # Log Commercial
    "MDNE3":  "Imobiliário",   # Moura Dubeux
    "MRVE3":  "Imobiliário",   # MRV
    "PLPL3":  "Imobiliário",   # Plano & Plano
    "TEND3":  "Imobiliário",   # Tenda

    # ── Industrial (21) ───────────────────────────────────────────
    "ARML3":  "Industrial",   # Armac
    "ECOR3":  "Industrial",   # Ecorodovias
    "FRAS3":  "Industrial",   # Fras-le
    "GGPS3":  "Industrial",   # GPS Participações
    "HBSA3":  "Industrial",   # Hidrovias do Brasil
    "JSLG3":  "Industrial",   # JSL
    "KEPL3":  "Industrial",   # Kepler Weber
    "LEVE3":  "Industrial",   # Metal Leve
    "MILS3":  "Industrial",   # Mills
    "MOVI3":  "Industrial",   # Movida
    "MYPK3":  "Industrial",   # Iochpe-Maxion
    "ORVR3":  "Industrial",   # Orizon
    "POMO4":  "Industrial",   # Marcopolo
    "PRNR3":  "Industrial",   # Priner
    "RAPT4":  "Industrial",   # Randon
    "RCSL3":  "Industrial",   # Recrusul
    "RCSL4":  "Industrial",   # Recrusul PN
    "SIMH3":  "Industrial",   # Simpar
    "TGMA3":  "Industrial",   # Tegma
    "TUPY3":  "Industrial",   # Tupy
    "VAMO3":  "Industrial",   # Vamos
}


def acoes_por_setor(setor: str) -> list[str]:
    return [ticker for ticker, s in SMLL_COMPOSICAO.items() if s == setor]


def todos_os_tickers() -> list[str]:
    return list(SMLL_COMPOSICAO.keys())
