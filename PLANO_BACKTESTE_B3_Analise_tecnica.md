# Plano: Sistema de Backteste B3 (WIN/WDO)

## Status: PLANEJADO — não implementado ainda

---

## Objetivo
Backend para plataforma web de backteste de estratégias com médias móveis e indicadores técnicos para Mini Índice (WIN) e Mini Dólar (WDO) na B3.  
Frontend será feito no **Lovable** e integrado via REST API.

---

## Decisões Tomadas

| Item | Decisão |
|------|---------|
| Backend | FastAPI (Python) |
| Banco de dados | PostgreSQL + TimescaleDB |
| Fila de tarefas | Redis + Celery |
| Dados históricos | MetaTrader 5 Python API |
| Período de dados | 2023 a 2026 |
| Timeframes | 5, 15, 30 e 60 minutos |
| Instrumentos | WIN (Mini Índice) e WDO (Mini Dólar) |
| Usuários | Múltiplos (até 100) |
| Autenticação | JWT (Bearer Token) |
| Deploy | VPS própria Windows (MT5 já instalado) |
| Frontend | Lovable (React) — integração via OpenAPI/Swagger |
| Execução de ordens | NÃO — apenas backteste |

---

## Funcionalidades do Backteste

### Configurações do Usuário
- Instrumento: WIN ou WDO
- Timeframe: 5, 15, 30 ou 60 min
- Período: data início e fim (dentro de 2023-2026)
- Média Móvel 1: tipo (SMA/EMA/WMA) + período (8 a 220)
- Média Móvel 2: tipo (SMA/EMA/WMA) + período (8 a 220)
- Sinal: cruzamento das médias (MA1 cruza acima = Compra / abaixo = Venda)
- Gain: pontos de take profit
- Loss: pontos de stop loss
- Número de contratos

### Indicadores Técnicos Opcionais (filtros)
- RSI (período configurável, níveis de sobrecompra/sobrevenda)
- MACD (12/26/9)
- Bandas de Bollinger (período + desvio padrão)
- Estocástico (14/3/3)
- ATR (período configurável)
- VWAP
- ADX (período configurável)
- Ichimoku

### Métricas de Resultado
- Total de operações
- Win Rate (%)
- Profit Factor
- Resultado financeiro total (R$)
- Resultado por contrato
- Drawdown máximo
- Sharpe Ratio
- Equity curve (array para gráfico)
- Lista completa de operações (entrada, saída, resultado, data)

---

## Estrutura do Projeto

```
backteste-api/
├── app/
│   ├── main.py                   # FastAPI entry point
│   ├── config.py                 # variáveis de ambiente
│   ├── database.py               # conexão PostgreSQL
│   ├── models/
│   │   ├── user.py               # tabela users
│   │   ├── ohlcv.py              # tabela preços históricos
│   │   └── backtest.py           # tabela backtestes e resultados
│   ├── schemas/
│   │   ├── user.py               # schemas Pydantic
│   │   ├── backtest.py
│   │   └── result.py
│   ├── api/v1/
│   │   ├── auth.py               # login, register, refresh token
│   │   ├── backtest.py           # criar/consultar backtestes
│   │   ├── data.py               # info dos dados disponíveis
│   │   └── users.py              # gerenciar usuários
│   ├── core/
│   │   ├── auth.py               # lógica JWT
│   │   └── security.py           # hash de senha
│   ├── services/
│   │   ├── mt5_collector.py      # coleta dados do MT5
│   │   ├── indicators.py         # cálculo de indicadores
│   │   ├── backtest_engine.py    # motor do backteste
│   │   └── data_service.py       # leitura de OHLCV do banco
│   └── workers/
│       ├── celery_app.py         # configuração Celery
│       └── tasks.py              # tarefas async (backteste)
├── migrations/                   # Alembic
├── scripts/
│   └── collect_history.py        # script inicial de coleta de dados
├── requirements.txt
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Endpoints da API

```
POST   /api/v1/auth/register          criar conta
POST   /api/v1/auth/login             login → retorna JWT
POST   /api/v1/auth/refresh           renovar token

GET    /api/v1/data/instruments       lista WIN, WDO
GET    /api/v1/data/timeframes        lista 5,15,30,60
GET    /api/v1/data/available-range   período disponível no banco

POST   /api/v1/backtest/run           criar e enfileirar backteste
GET    /api/v1/backtest/              listar backtestes do usuário
GET    /api/v1/backtest/{id}          status e resultado de um backteste
DELETE /api/v1/backtest/{id}          deletar backteste

GET    /api/v1/users/me               dados do usuário logado
```

---

## Banco de Dados — Tabelas Principais

### users
| Campo | Tipo |
|-------|------|
| id | UUID |
| email | VARCHAR (único) |
| name | VARCHAR |
| hashed_password | VARCHAR |
| is_active | BOOLEAN |
| created_at | TIMESTAMP |

### ohlcv_data
| Campo | Tipo |
|-------|------|
| id | BIGINT |
| instrument | VARCHAR (WIN/WDO) |
| timeframe | VARCHAR (5m/15m/30m/60m) |
| timestamp | TIMESTAMP |
| open | FLOAT |
| high | FLOAT |
| low | FLOAT |
| close | FLOAT |
| volume | BIGINT |

### backtests
| Campo | Tipo |
|-------|------|
| id | UUID |
| user_id | UUID (FK) |
| config | JSONB |
| status | ENUM (pending/running/done/error) |
| created_at | TIMESTAMP |
| completed_at | TIMESTAMP |

### backtest_results
| Campo | Tipo |
|-------|------|
| id | UUID |
| backtest_id | UUID (FK) |
| metrics | JSONB |
| trades | JSONB |
| equity_curve | JSONB |

---

## Lógica do Motor de Backteste

```
1. Buscar OHLCV do banco para instrumento/timeframe/período
2. Calcular MA1 e MA2 (SMA/EMA/WMA)
3. Calcular indicadores opcionais (RSI, MACD, etc.)
4. Gerar sinais:
   - COMPRA: MA1 cruza acima de MA2
   - VENDA:  MA1 cruza abaixo de MA2
5. Para cada sinal:
   - Entrada = close do candle do sinal
   - TP = entrada + gain_pontos (compra) / entrada - gain_pontos (venda)
   - SL = entrada - loss_pontos (compra) / entrada + loss_pontos (venda)
   - Varrer candles futuros até atingir TP ou SL
6. Calcular métricas finais
7. Salvar resultado no banco
```

---

## Valor por Ponto

| Instrumento | Valor por ponto (mini) |
|-------------|----------------------|
| WIN (Mini Índice) | R$ 0,20 por contrato |
| WDO (Mini Dólar) | R$ 10,00 por contrato |

---

## Requisitos da VPS

- Windows Server (MT5 instalado e logado)
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Porta 8000 aberta (API)
- Domínio ou IP público (para o Lovable acessar)

---

## Integração com Lovable

1. Subir a API na VPS: `https://seudominio.com`
2. No Lovable: Add API → colar a URL
3. O Lovable lê `/openapi.json` automaticamente
4. Conectar os componentes do frontend aos endpoints

---

## Próximos Passos (quando for implementar)

- [ ] Criar projeto na VPS com estrutura acima
- [ ] Configurar PostgreSQL + Redis
- [ ] Instalar dependências Python
- [ ] Rodar script de coleta de dados históricos do MT5
- [ ] Testar endpoints com Swagger UI
- [ ] Compartilhar URL com o Lovable
- [ ] Configurar domínio + HTTPS (Nginx + Let's Encrypt)
