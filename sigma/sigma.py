"""
╔══════════════════════════════════════════════════════════════╗
║              SIGMA — Executor Quantitativo WIN               ║
║  Estratégia de Mean-Reversion  |  Janela 09:00–10:30 BRT    ║
║  Baseado em 826 dias de backtest  |  OpenFAST v2             ║
╚══════════════════════════════════════════════════════════════╝

Sinais:
  SIGMA-C │ WIN cai  ≥ 0.50% do open de 09:00 → COMPRA OCO
  SIGMA-V │ WIN sobe ≥ 500 pts do open de 09:00 → VENDA  OCO

Uso:
  python sigma.py              (usa config.py)
  python sigma.py --sim        (força modo simulação)
  python sigma.py --real       (força modo real — cuidado)
"""
import socket
import threading
import time
import os
import sys
import logging
import argparse
from datetime import datetime, time as dtime
from enum import Enum, auto

sys.path.insert(0, os.path.dirname(__file__))
import config as CFG

# ══════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════
os.makedirs(CFG.LOG_DIR, exist_ok=True)
_log_file = os.path.join(CFG.LOG_DIR, f"sigma_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        *([ logging.StreamHandler(sys.stdout) ] if CFG.LOG_CONSOLE else []),
    ]
)
log = logging.getLogger("SIGMA")

# ══════════════════════════════════════════════════════════════
# ESTADOS
# ══════════════════════════════════════════════════════════════
class Estado(Enum):
    AGUARDANDO_OPEN  = auto()   # antes de 09:00
    MONITORANDO      = auto()   # 09:00–09:40, aguardando gatilho
    POSICAO_ABERTA   = auto()   # OCO enviada, aguardando resultado
    ENCERRADO        = auto()   # após 10:30 ou limite de trades

# ══════════════════════════════════════════════════════════════
# CONEXÃO OPENFAST
# ══════════════════════════════════════════════════════════════
SOH = '\x01'   # separador real ASCII

class OpenFastConn:
    def __init__(self, host, port, on_msg_cb):
        self._host    = host
        self._port    = port
        self._cb      = on_msg_cb
        self._sock    = None
        self._lock    = threading.Lock()
        self._running = False
        self._last_syn = time.time()

    def conectar(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(5)
        self._sock.connect((self._host, self._port))
        self._running = True
        self._enviar_raw("OPENFAST")
        ver = self._receber_linha()
        log.info(f"OpenFAST conectado — {ver}")
        threading.Thread(target=self._loop_leitura, daemon=True).start()
        threading.Thread(target=self._loop_heartbeat, daemon=True).start()

    def _enviar_raw(self, msg):
        with self._lock:
            self._sock.send((msg + '\n').encode('utf-8'))

    def cmd(self, msg):
        """Envia comando substituindo # pelo SOH real."""
        self._enviar_raw(msg.replace('#', SOH))

    def _receber_linha(self):
        buf = b''
        while True:
            c = self._sock.recv(1)
            if c in (b'\n', b''):
                break
            buf += c
        return buf.decode('utf-8', errors='replace')

    def _loop_leitura(self):
        while self._running:
            try:
                linha = self._receber_linha()
                if not linha:
                    continue
                if linha.startswith('SYN'):
                    self._last_syn = time.time()
                    continue
                self._cb(linha)
            except socket.timeout:
                continue
            except Exception as e:
                log.error(f"Erro leitura: {e}")
                break

    def _loop_heartbeat(self):
        while self._running:
            time.sleep(20)
            if time.time() - self._last_syn > 45:
                log.warning("Heartbeat ausente — conexão pode ter caído")

    def desconectar(self):
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════
# ESTRATÉGIA SIGMA
# ══════════════════════════════════════════════════════════════
class Sigma:
    def __init__(self, conn: OpenFastConn, simulacao: bool):
        self.conn      = conn
        self.sim       = simulacao
        self.estado    = Estado.AGUARDANDO_OPEN

        # preço de abertura 09:00
        self.open_0900  = None

        # controle de sinais disparados no dia
        self.sigma_c_disparado = False
        self.sigma_v_disparado = False
        self.trades_dia        = 0

        # rastreia última cotação
        self.last_price = None
        self.bid        = None
        self.ask        = None

        # ordens abertas: id → descrição
        self.ordens_abertas = {}

        log.info("="*60)
        log.info(f"  SIGMA inicializado — ativo: {CFG.ATIVO}")
        log.info(f"  SIGMA-C: queda ≥ {CFG.SIGMA_C_GATILHO_PCT*100:.1f}%  "
                 f"| GAIN {CFG.SIGMA_C_GAIN_PTS} / STOP {CFG.SIGMA_C_STOP_PTS}")
        log.info(f"  SIGMA-V: alta  ≥ +{CFG.SIGMA_V_GATILHO_PTS} pts "
                 f"| GAIN {CFG.SIGMA_V_GAIN_PTS} / STOP {CFG.SIGMA_V_STOP_PTS}")
        log.info(f"  Modo: {'SIMULAÇÃO ⚠' if simulacao else 'REAL 🔴'}")
        log.info("="*60)

    # ── Assinaturas ────────────────────────────────────────────
    def iniciar_assinaturas(self):
        ativo = CFG.ATIVO
        for campo in ['LAST','BID','ASK','OPEN','HIGH','LOW','VAR','DIF']:
            self.conn.cmd(f'on#SQT#{ativo}#{campo}')
        self.conn.cmd(f'on#TICKS#{ativo}')
        self.conn.cmd('on#SIGNORDERS')
        self.conn.cmd(f'on#POS#{CFG.CONTA}#{ativo}')
        log.info(f"Assinaturas ativas: SQT + TICKS + SIGNORDERS + POS")

    # ── Parser de mensagens ────────────────────────────────────
    def on_message(self, raw: str):
        campos = raw.replace(SOH, '|').split('|')
        if not campos:
            return

        tipo = campos[0].upper()

        if tipo == 'SQT':
            self._handle_sqt(campos)
        elif tipo == 'TICKS':
            self._handle_tick(campos)
        elif tipo == 'SIGNORDERS':
            self._handle_order(campos)
        elif tipo == 'POS':
            self._handle_pos(campos)
        elif tipo == 'BROKER_STATUS':
            log.info(f"Corretora: {raw.replace(SOH,'|')}")

    def _handle_sqt(self, c):
        if len(c) < 4:
            return
        campo = c[2].strip().upper()
        try:
            valor = float(c[3].replace(',','.'))
        except Exception:
            return

        if campo == 'LAST':
            self.last_price = valor
            self._verificar_sinais()
        elif campo == 'BID':
            self.bid = valor
        elif campo == 'ASK':
            self.ask = valor
        elif campo == 'OPEN':
            if self.open_0900 is None and valor > 0:
                self.open_0900 = valor
                log.info(f"Open 09:00 capturado: {valor:.0f}")

    def _handle_tick(self, c):
        # TICKS#ativo#hora#preco#...
        if len(c) < 4 or c[2] == 'E':
            return
        try:
            preco = float(c[3].replace(',','.'))
            self.last_price = preco
            self._verificar_sinais()
        except Exception:
            pass

    def _handle_order(self, c):
        if len(c) < 5:
            return
        order_id = c[1]
        status   = c[4] if len(c) > 4 else '?'
        ativo    = c[8] if len(c) > 8 else '?'
        lado     = c[9] if len(c) > 9 else '?'

        STATUS_NOME = {
            '0':'NOVA','1':'PARCIAL','2':'EXECUTADA',
            '4':'CANCELADA','8':'REJEITADA','R':'RECEBIDA',
        }
        nome = STATUS_NOME.get(status, status)
        log.info(f"ORDER [{order_id[:20]}] {nome} | {ativo} lado={lado}")

        if status == '2':   # FILLED
            log.info(f"  ✅ Ordem executada: {order_id[:20]}")
            if order_id in self.ordens_abertas:
                log.info(f"  Sinal encerrado: {self.ordens_abertas[order_id]}")
        elif status == '8':  # REJECTED
            log.warning(f"  ❌ Ordem rejeitada: {order_id[:20]} — {c[-1] if c else ''}")

    def _handle_pos(self, c):
        if len(c) < 7:
            return
        qtd_aberta = c[5] if len(c) > 5 else '0'
        pnl_aberto = c[7] if len(c) > 7 else '0'
        if qtd_aberta != '0':
            log.info(f"Posição: qtd={qtd_aberta} | P&L aberto={pnl_aberto}")

    # ── Verificação dos sinais ─────────────────────────────────
    def _verificar_sinais(self):
        agora = datetime.now().time()

        h_inicio  = dtime(*CFG.HORA_INICIO)
        h_entrada = dtime(*CFG.HORA_ENTRADA)
        h_saida   = dtime(*CFG.HORA_SAIDA)

        # Captura open na abertura
        if agora < h_inicio:
            self.estado = Estado.AGUARDANDO_OPEN
            return

        # Força saída após 10:30
        if agora >= h_saida:
            if self.estado == Estado.POSICAO_ABERTA:
                self._forcar_saida()
            self.estado = Estado.ENCERRADO
            return

        # Só monitora se ainda não esgotou trades
        if self.trades_dia >= CFG.MAX_TRADES_DIA:
            self.estado = Estado.ENCERRADO
            return

        if self.open_0900 is None or self.last_price is None:
            return

        self.estado = Estado.MONITORANDO

        # Dentro da janela de entrada (até 09:40)
        if agora <= h_entrada:
            self._checar_sigma_c()
            self._checar_sigma_v()

    def _checar_sigma_c(self):
        """SIGMA-C: WIN cai 0.50% do open → COMPRA OCO."""
        if not CFG.SIGMA_C_ATIVO or self.sigma_c_disparado:
            return

        gatilho = self.open_0900 * (1 - CFG.SIGMA_C_GATILHO_PCT)
        var_pct  = (self.last_price - self.open_0900) / self.open_0900 * 100

        if self.last_price <= gatilho:
            entry      = round(self.last_price)
            gain_price = entry + CFG.SIGMA_C_GAIN_PTS
            stop_price = entry - CFG.SIGMA_C_STOP_PTS

            log.info("─"*60)
            log.info(f"🔵 SIGMA-C DISPARADO — COMPRA")
            log.info(f"   Open:    {self.open_0900:.0f}")
            log.info(f"   Gatilho: {gatilho:.0f}  ({CFG.SIGMA_C_GATILHO_PCT*100:.1f}%)")
            log.info(f"   Last:    {self.last_price:.0f}  (var {var_pct:+.2f}%)")
            log.info(f"   Entry:   {entry}")
            log.info(f"   GAIN:    {gain_price}  (+{CFG.SIGMA_C_GAIN_PTS} pts = R$ {CFG.SIGMA_C_GAIN_PTS*0.20:.0f})")
            log.info(f"   STOP:    {stop_price}  (-{CFG.SIGMA_C_STOP_PTS} pts = R$ {CFG.SIGMA_C_STOP_PTS*0.20:.0f})")
            log.info("─"*60)

            self._enviar_oco(
                prefixo   = "SC",
                ativo     = CFG.ATIVO,
                qtd       = CFG.QUANTIDADE,
                lado      = 1,          # COMPRA
                gain_price= gain_price,
                stop_price= stop_price,
                rotulo    = "SIGMA-C"
            )
            self.sigma_c_disparado = True

    def _checar_sigma_v(self):
        """SIGMA-V: WIN sobe 500 pts do open → VENDA OCO."""
        if not CFG.SIGMA_V_ATIVO or self.sigma_v_disparado:
            return

        gatilho  = self.open_0900 + CFG.SIGMA_V_GATILHO_PTS
        var_pts  = self.last_price - self.open_0900

        if self.last_price >= gatilho:
            entry      = round(self.last_price)
            gain_price = entry - CFG.SIGMA_V_GAIN_PTS
            stop_price = entry + CFG.SIGMA_V_STOP_PTS

            log.info("─"*60)
            log.info(f"🔴 SIGMA-V DISPARADO — VENDA")
            log.info(f"   Open:    {self.open_0900:.0f}")
            log.info(f"   Gatilho: {gatilho:.0f}  (+{CFG.SIGMA_V_GATILHO_PTS} pts)")
            log.info(f"   Last:    {self.last_price:.0f}  (var {var_pts:+.0f} pts)")
            log.info(f"   Entry:   {entry}")
            log.info(f"   GAIN:    {gain_price}  (-{CFG.SIGMA_V_GAIN_PTS} pts = R$ {CFG.SIGMA_V_GAIN_PTS*0.20:.0f})")
            log.info(f"   STOP:    {stop_price}  (+{CFG.SIGMA_V_STOP_PTS} pts = R$ {CFG.SIGMA_V_STOP_PTS*0.20:.0f})")
            log.info("─"*60)

            self._enviar_oco(
                prefixo   = "SV",
                ativo     = CFG.ATIVO,
                qtd       = CFG.QUANTIDADE,
                lado      = 2,          # VENDA
                gain_price= gain_price,
                stop_price= stop_price,
                rotulo    = "SIGMA-V"
            )
            self.sigma_v_disparado = True

    # ── Envio de OCO ───────────────────────────────────────────
    def _enviar_oco(self, prefixo, ativo, qtd, lado,
                    gain_price, stop_price, rotulo):
        ts     = datetime.now().strftime('%H%M%S%f')[:10]
        id_gain = f"{prefixo}_G_{ts}"
        id_stop = f"{prefixo}_S_{ts}"

        # OCO: gain_price=limite da ordem gain | stop_price=disparo e limite do stop
        cmd = (
            f"on#ORDERSENDOCO"
            f"#{id_gain}#{id_stop}"
            f"#{ativo}#{qtd}"
            f"#{gain_price}#{stop_price}#{stop_price}"
            f"#{CFG.CONTA}#{lado}"
            f"#0#####{rotulo}##"
        )

        self.ordens_abertas[id_gain] = rotulo
        self.ordens_abertas[id_stop] = rotulo
        self.trades_dia += 1
        self.estado = Estado.POSICAO_ABERTA

        if self.sim:
            log.info(f"  [SIMULAÇÃO] CMD: {cmd.replace(SOH,'#')}")
        else:
            self.conn.cmd(cmd)
            log.info(f"  OCO enviada: GAIN={id_gain} | STOP={id_stop}")

    # ── Saída forçada 10:30 ────────────────────────────────────
    def _forcar_saida(self):
        log.info("⏰ 10:30 atingido — zerando posição aberta")
        if self.sim:
            log.info(f"  [SIMULAÇÃO] POSFLATTEN {CFG.CONTA} {CFG.ATIVO}")
        else:
            self.conn.cmd(f"on#POSFLATTEN#{CFG.CONTA}#{CFG.ATIVO}")
            log.info(f"  POSFLATTEN enviado: {CFG.CONTA} | {CFG.ATIVO}")

    # ── Reset diário ───────────────────────────────────────────
    def reset_diario(self):
        self.open_0900         = None
        self.sigma_c_disparado = False
        self.sigma_v_disparado = False
        self.trades_dia        = 0
        self.ordens_abertas    = {}
        self.estado            = Estado.AGUARDANDO_OPEN
        log.info("Reset diário realizado")

# ══════════════════════════════════════════════════════════════
# LOOP PRINCIPAL
# ══════════════════════════════════════════════════════════════
def main(simulacao: bool):
    conn   = OpenFastConn(CFG.OF_HOST, CFG.OF_PORT, lambda m: sigma.on_message(m))
    sigma  = Sigma(conn, simulacao)

    # Reatribui callback agora que sigma existe
    conn._cb = sigma.on_message

    try:
        conn.conectar()
    except ConnectionRefusedError:
        log.error("Não foi possível conectar na porta 557.")
        log.error("Verifique se o FastTrader está aberto e conectado.")
        sys.exit(1)

    sigma.iniciar_assinaturas()

    log.info("SIGMA ativo — aguardando 09:00 BRT...")

    dia_atual = datetime.now().date()
    try:
        while True:
            time.sleep(1)

            # Reset automático a cada novo dia
            hoje = datetime.now().date()
            if hoje != dia_atual:
                dia_atual = hoje
                sigma.reset_diario()

            # Log de status a cada 5 minutos entre 09:00 e 10:30
            agora = datetime.now()
            if (agora.second == 0 and agora.minute % 5 == 0
                    and dtime(9,0) <= agora.time() <= dtime(10,30)):
                _status_log(sigma)

    except KeyboardInterrupt:
        log.info("Sigma encerrado pelo usuário.")
    finally:
        conn.desconectar()

def _status_log(s: Sigma):
    var = ""
    if s.open_0900 and s.last_price:
        pts = s.last_price - s.open_0900
        pct = pts / s.open_0900 * 100
        var = f"var {pts:+.0f}pts ({pct:+.2f}%)"
    log.info(
        f"STATUS | {s.estado.name} | open={s.open_0900 or '?'} "
        f"last={s.last_price or '?'} | {var} | "
        f"C={'✅' if s.sigma_c_disparado else '⏳'} "
        f"V={'✅' if s.sigma_v_disparado else '⏳'} | "
        f"trades={s.trades_dia}"
    )

# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SIGMA — Executor WIN")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument('--sim',  action='store_true', help='Força modo simulação')
    grp.add_argument('--real', action='store_true', help='Força modo real')
    args = parser.parse_args()

    if args.real:
        sim = False
    elif args.sim:
        sim = True
    else:
        sim = CFG.SIMULACAO

    if not sim:
        print("\n⚠️  MODO REAL ATIVADO — ordens serão enviadas à corretora.")
        print(f"   Ativo: {CFG.ATIVO} | Conta: {CFG.CONTA} | Qtd: {CFG.QUANTIDADE}")
        resp = input("   Confirma? (sim/nao): ").strip().lower()
        if resp != 'sim':
            print("Abortado.")
            sys.exit(0)

    main(sim)
