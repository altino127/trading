# ══════════════════════════════════════════════════════════════
#  SIGMA — Configurações
#  Edite este arquivo antes de rodar o executor
# ══════════════════════════════════════════════════════════════

# ── Contrato ativo WIN ─────────────────────────────────────────
ATIVO = "WINM26"          # ajuste conforme vencimento atual

# ── Conta da corretora ─────────────────────────────────────────
CONTA = "SUA_CONTA_AQUI"  # substitua pelo número real da sua conta

# ── Quantidade de contratos ────────────────────────────────────
QUANTIDADE = 1             # minis por operação

# ── Conexão OpenFAST ───────────────────────────────────────────
OF_HOST = "localhost"
OF_PORT = 557

# ── Estratégia SIGMA-C: Queda 0.50% → COMPRA ──────────────────
SIGMA_C_ATIVO         = True
SIGMA_C_GATILHO_PCT   = 0.005    # 0.50% de queda do open
SIGMA_C_GAIN_PTS      = 400      # PF 2.00 *** nos backtests
SIGMA_C_STOP_PTS      = 400

# ── Estratégia SIGMA-V: Alta +500 pts → VENDA ─────────────────
SIGMA_V_ATIVO         = True
SIGMA_V_GATILHO_PTS   = 500      # pontos fixos acima do open
SIGMA_V_GAIN_PTS      = 200      # PF 1.36 ** nos backtests
SIGMA_V_STOP_PTS      = 100

# ── Janela de operação ─────────────────────────────────────────
HORA_INICIO  = (9,  0)    # 09:00 BRT
HORA_ENTRADA = (9, 40)    # 09:40 — após este horário não entra
HORA_SAIDA   = (10, 30)   # 10:30 — fecha posição aberta forçado

# ── Segurança ──────────────────────────────────────────────────
MAX_TRADES_DIA = 2         # máximo 1 SIGMA-C + 1 SIGMA-V por dia
SIMULACAO      = True      # True = loga ordens sem enviar | False = opera real

# ── Log ────────────────────────────────────────────────────────
LOG_DIR  = "C:/estrategia/sigma/logs"
LOG_CONSOLE = True
