# ══════════════════════════════════════════════════════════════
#  FUCSIA DOLAR — Configuracoes
#  Edite este arquivo antes de rodar o executor
# ══════════════════════════════════════════════════════════════

# ── Contrato ativo WDO ─────────────────────────────────────────
ATIVO = "WDOM26"          # ajuste conforme vencimento atual

# ── Conta da corretora ─────────────────────────────────────────
CONTA = "SUA_CONTA_AQUI"  # substitua pelo numero real da sua conta

# ── Quantidade de contratos ────────────────────────────────────
QUANTIDADE = 1             # minis por operacao

# ── Conexao OpenFAST ───────────────────────────────────────────
OF_HOST = "localhost"
OF_PORT = 557

# ── Gatilho: 1% do open 09:00 ─────────────────────────────────
GATILHO_PCT = 0.01         # 1.00% do preco de abertura

# ── Parametros da operacao ─────────────────────────────────────
STOP_PTS  = 7              # 7 pontos = R$ 70 por mini
GAIN_PTS  = 10             # 10 pontos = R$ 100 por mini

# ── Lados ativos ───────────────────────────────────────────────
FUCSIA_C_ATIVO = True      # COMPRA se WDO cair 1%
FUCSIA_V_ATIVO = True      # VENDA  se WDO subir 1%

# ── Janela de operacao ─────────────────────────────────────────
HORA_INICIO = (9,  0)      # 09:00 BRT — captura open e começa monitorar
HORA_SAIDA  = (16, 30)     # 16:30 — fecha posicao aberta e encerra

# ── Seguranca ──────────────────────────────────────────────────
MAX_TRADES_DIA = 2         # maximo 1 COMPRA + 1 VENDA por dia
SIMULACAO      = True      # True = loga ordens sem enviar | False = opera real

# ── Log ────────────────────────────────────────────────────────
LOG_DIR     = "C:/estrategia/fucsia/logs"
LOG_CONSOLE = True
