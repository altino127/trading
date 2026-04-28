"""
╔══════════════════════════════════════════════════════════════╗
║           FUCSIA DOLAR — Executor Quantitativo WDO           ║
║  Estrategia de Mean-Reversion  |  Janela 09:00-16:30 BRT    ║
║  Baseado em 826 dias de backtest  |  OpenFAST v2             ║
╚══════════════════════════════════════════════════════════════╝

Sinais:
  FUCSIA-C | WDO cai  >= 1% do open 09:00 -> COMPRA OCO
  FUCSIA-V | WDO sobe >= 1% do open 09:00 -> VENDA  OCO

Parametros: Stop 7 pts (R$ 70) | Gain 10 pts (R$ 100)

Uso:
  python fucsia.py              (usa config.py)
  python fucsia.py --sim        (forca modo simulacao)
  python fucsia.py --real       (forca modo real -- cuidado)
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

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(CFG.LOG_DIR, exist_ok=True)
_log_file = os.path.join(CFG.LOG_DIR, f"fucsia_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        *([ logging.StreamHandler(sys.stdout) ] if CFG.LOG_CONSOLE else []),
    ]
)
if CFG.LOG_CONSOLE and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

log = logging.getLogger("FUCSIA")

# ── Estados ───────────────────────────────────────────────────────────────────
class Estado(Enum):
    AGUARDANDO_OPEN = auto()   # antes de 09:00
    MONITORANDO     = auto()   # 09:00-16:30, aguardando gatilho
    POSICAO_ABERTA  = auto()   # OCO enviada, aguardando resultado
    ENCERRADO       = auto()   # apos 16:30 ou limite de trades

# ── Conexao OpenFAST ──────────────────────────────────────────────────────────
SOH = '\x01'

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
        log.info(f"OpenFAST conectado: {ver.replace(SOH,'|').strip()}")
        threading.Thread(target=self._loop_leitura,   daemon=True).start()
        threading.Thread(target=self._loop_heartbeat, daemon=True).start()

    def _enviar_raw(self, msg):
        with self._lock:
            self._sock.send((msg + '\n').encode('utf-8'))

    def cmd(self, msg):
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
                log.warning("Heartbeat ausente - conexao pode ter caido")

    def desconectar(self):
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass

# ── Estrategia FUCSIA ─────────────────────────────────────────────────────────
class Fucsia:
    def __init__(self, conn: OpenFastConn, simulacao: bool):
        self.conn = conn
        self.sim  = simulacao
        self.estado = Estado.AGUARDANDO_OPEN

        self.open_0900    = None
        self.last_price   = None
        self.bid          = None
        self.ask          = None

        self.fucsia_c_disparado = False
        self.fucsia_v_disparado = False
        self.trades_dia         = 0
        self.ordens_abertas     = {}

        # Pre-calculo dos gatilhos (atualizado quando open_0900 for capturado)
        self._gatilho_c = None   # open * 0.99
        self._gatilho_v = None   # open * 1.01

        log.info("=" * 60)
        log.info(f"  FUCSIA DOLAR inicializado")
        log.info(f"  Ativo:    {CFG.ATIVO}")
        log.info(f"  Gatilho:  +-{CFG.GATILHO_PCT*100:.2f}% do open 09:00")
        log.info(f"  Stop:     {CFG.STOP_PTS} pts  (R$ {CFG.STOP_PTS*10:.0f})")
        log.info(f"  Gain:     {CFG.GAIN_PTS} pts  (R$ {CFG.GAIN_PTS*10:.0f})")
        log.info(f"  Janela:   09:00 - 16:30 BRT")
        log.info(f"  Modo:     {'SIMULACAO' if simulacao else 'REAL'}")
        log.info("=" * 60)

    # ── Assinaturas ───────────────────────────────────────────────────────────
    def iniciar_assinaturas(self):
        ativo = CFG.ATIVO
        for campo in ['LAST', 'BID', 'ASK', 'OPEN', 'HIGH', 'LOW', 'VAR', 'DIF']:
            self.conn.cmd(f'on#SQT#{ativo}#{campo}')
        self.conn.cmd(f'on#TICKS#{ativo}')
        self.conn.cmd('on#SIGNORDERS')
        self.conn.cmd(f'on#POS#{CFG.CONTA}#{ativo}')
        log.info(f"Assinaturas ativas: SQT + TICKS + SIGNORDERS + POS")

    # ── Parser de mensagens ───────────────────────────────────────────────────
    def on_message(self, raw: str):
        campos = raw.replace(SOH, '|').split('|')
        if not campos:
            return
        tipo = campos[0].strip().upper()

        if tipo == 'SQT':
            self._handle_sqt(campos)
        elif tipo == 'TICKS':
            self._handle_tick(campos)
        elif tipo == 'SIGNORDERS':
            self._handle_order(campos)
        elif tipo == 'POS':
            self._handle_pos(campos)
        elif tipo == 'BROKER_STATUS':
            log.info(f"Corretora: {raw.replace(SOH,'|').strip()}")

    def _handle_sqt(self, c):
        if len(c) < 4:
            return
        campo = c[2].strip().upper()
        try:
            valor = float(c[3].replace(',', '.'))
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
            self._capturar_open(valor)

    def _handle_tick(self, c):
        if len(c) < 4 or c[2] == 'E':
            return
        try:
            preco = float(c[3].replace(',', '.'))
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
            '0': 'NOVA', '1': 'PARCIAL', '2': 'EXECUTADA',
            '4': 'CANCELADA', '8': 'REJEITADA', 'R': 'RECEBIDA',
        }
        nome = STATUS_NOME.get(status, status)
        log.info(f"ORDER [{order_id[:20]}] {nome} | {ativo} lado={lado}")

        if status == '2':
            log.info(f"  Ordem executada: {order_id[:20]}")
            if order_id in self.ordens_abertas:
                log.info(f"  Sinal encerrado: {self.ordens_abertas[order_id]}")
                self.ordens_abertas.pop(order_id, None)
        elif status == '8':
            log.warning(f"  Ordem rejeitada: {order_id[:20]} | {c[-1] if c else ''}")

    def _handle_pos(self, c):
        if len(c) < 6:
            return
        qtd_aberta = c[5] if len(c) > 5 else '0'
        pnl_aberto = c[7] if len(c) > 7 else '0'
        if qtd_aberta != '0':
            log.info(f"Posicao: qtd={qtd_aberta} | P&L aberto={pnl_aberto}")

    # ── Open 09:00 ────────────────────────────────────────────────────────────
    def _capturar_open(self, valor):
        if valor <= 0:
            return
        agora = datetime.now().time()
        h_inicio = dtime(*CFG.HORA_INICIO)
        if self.open_0900 is None and agora >= h_inicio:
            self.open_0900  = valor
            self._gatilho_c = round(valor * (1 - CFG.GATILHO_PCT), 1)
            self._gatilho_v = round(valor * (1 + CFG.GATILHO_PCT), 1)
            log.info(f"Open 09:00 capturado: {valor:.1f}")
            log.info(f"  Gatilho COMPRA (queda 1%): <= {self._gatilho_c:.1f}")
            log.info(f"  Gatilho VENDA  (alta  1%): >= {self._gatilho_v:.1f}")

    # ── Verificacao dos sinais ─────────────────────────────────────────────────
    def _verificar_sinais(self):
        agora    = datetime.now().time()
        h_inicio = dtime(*CFG.HORA_INICIO)
        h_saida  = dtime(*CFG.HORA_SAIDA)

        if agora < h_inicio:
            self.estado = Estado.AGUARDANDO_OPEN
            return

        if agora >= h_saida:
            if self.estado == Estado.POSICAO_ABERTA:
                self._forcar_saida()
            self.estado = Estado.ENCERRADO
            return

        if self.trades_dia >= CFG.MAX_TRADES_DIA:
            self.estado = Estado.ENCERRADO
            return

        if self.open_0900 is None or self.last_price is None:
            return

        self.estado = Estado.MONITORANDO
        self._checar_fucsia_c()
        self._checar_fucsia_v()

    def _checar_fucsia_c(self):
        """FUCSIA-C: WDO cai 1% do open -> COMPRA OCO."""
        if not CFG.FUCSIA_C_ATIVO or self.fucsia_c_disparado:
            return
        if self.last_price > self._gatilho_c:
            return

        var_pct = (self.last_price - self.open_0900) / self.open_0900 * 100
        entry   = round(self.last_price, 1)
        gain_p  = round(entry + CFG.GAIN_PTS, 1)
        stop_p  = round(entry - CFG.STOP_PTS, 1)

        log.info("-" * 60)
        log.info(f"FUCSIA-C DISPARADO - COMPRA")
        log.info(f"  Open:    {self.open_0900:.1f}")
        log.info(f"  Gatilho: {self._gatilho_c:.1f}  (-{CFG.GATILHO_PCT*100:.2f}%)")
        log.info(f"  Last:    {self.last_price:.1f}  (var {var_pct:+.2f}%)")
        log.info(f"  Entry:   {entry}")
        log.info(f"  GAIN:    {gain_p}  (+{CFG.GAIN_PTS} pts = R$ {CFG.GAIN_PTS*10:.0f})")
        log.info(f"  STOP:    {stop_p}  (-{CFG.STOP_PTS} pts = R$ {CFG.STOP_PTS*10:.0f})")
        log.info("-" * 60)

        self._enviar_oco(
            prefixo    = "FC",
            ativo      = CFG.ATIVO,
            qtd        = CFG.QUANTIDADE,
            lado       = 1,           # COMPRA
            gain_price = gain_p,
            stop_price = stop_p,
            rotulo     = "FUCSIA-C",
        )
        self.fucsia_c_disparado = True

    def _checar_fucsia_v(self):
        """FUCSIA-V: WDO sobe 1% do open -> VENDA OCO."""
        if not CFG.FUCSIA_V_ATIVO or self.fucsia_v_disparado:
            return
        if self.last_price < self._gatilho_v:
            return

        var_pct = (self.last_price - self.open_0900) / self.open_0900 * 100
        entry   = round(self.last_price, 1)
        gain_p  = round(entry - CFG.GAIN_PTS, 1)
        stop_p  = round(entry + CFG.STOP_PTS, 1)

        log.info("-" * 60)
        log.info(f"FUCSIA-V DISPARADO - VENDA")
        log.info(f"  Open:    {self.open_0900:.1f}")
        log.info(f"  Gatilho: {self._gatilho_v:.1f}  (+{CFG.GATILHO_PCT*100:.2f}%)")
        log.info(f"  Last:    {self.last_price:.1f}  (var {var_pct:+.2f}%)")
        log.info(f"  Entry:   {entry}")
        log.info(f"  GAIN:    {gain_p}  (-{CFG.GAIN_PTS} pts = R$ {CFG.GAIN_PTS*10:.0f})")
        log.info(f"  STOP:    {stop_p}  (+{CFG.STOP_PTS} pts = R$ {CFG.STOP_PTS*10:.0f})")
        log.info("-" * 60)

        self._enviar_oco(
            prefixo    = "FV",
            ativo      = CFG.ATIVO,
            qtd        = CFG.QUANTIDADE,
            lado       = 2,           # VENDA
            gain_price = gain_p,
            stop_price = stop_p,
            rotulo     = "FUCSIA-V",
        )
        self.fucsia_v_disparado = True

    # ── Envio de OCO ──────────────────────────────────────────────────────────
    def _enviar_oco(self, prefixo, ativo, qtd, lado,
                    gain_price, stop_price, rotulo):
        ts      = datetime.now().strftime('%H%M%S%f')[:10]
        id_gain = f"{prefixo}_G_{ts}"
        id_stop = f"{prefixo}_S_{ts}"

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
            log.info(f"  [SIMULACAO] CMD: {cmd.replace(SOH,'#')}")
        else:
            self.conn.cmd(cmd)
            log.info(f"  OCO enviada: GAIN={id_gain} | STOP={id_stop}")

    # ── Saida forcada 16:30 ───────────────────────────────────────────────────
    def _forcar_saida(self):
        log.info("16:30 atingido - zerando posicao aberta")
        if self.sim:
            log.info(f"  [SIMULACAO] POSFLATTEN {CFG.CONTA} {CFG.ATIVO}")
        else:
            self.conn.cmd(f"on#POSFLATTEN#{CFG.CONTA}#{CFG.ATIVO}")
            log.info(f"  POSFLATTEN enviado: {CFG.CONTA} | {CFG.ATIVO}")

    # ── Reset diario ──────────────────────────────────────────────────────────
    def reset_diario(self):
        self.open_0900          = None
        self._gatilho_c         = None
        self._gatilho_v         = None
        self.fucsia_c_disparado = False
        self.fucsia_v_disparado = False
        self.trades_dia         = 0
        self.ordens_abertas     = {}
        self.estado             = Estado.AGUARDANDO_OPEN
        log.info("Reset diario realizado")

# ── Status log ────────────────────────────────────────────────────────────────
def _status_log(f: Fucsia):
    var = ""
    if f.open_0900 and f.last_price:
        pts = f.last_price - f.open_0900
        pct = pts / f.open_0900 * 100
        var = f"var {pts:+.1f}pts ({pct:+.2f}%)"
        if f._gatilho_c:
            dist_c = f.last_price - f._gatilho_c
            dist_v = f._gatilho_v - f.last_price
            var += f" | dist_C={dist_c:+.1f} dist_V={dist_v:+.1f}"
    log.info(
        f"STATUS | {f.estado.name} | open={f.open_0900 or '?'} "
        f"last={f.last_price or '?'} | {var} | "
        f"C={'OK' if f.fucsia_c_disparado else 'aguard'} "
        f"V={'OK' if f.fucsia_v_disparado else 'aguard'} | "
        f"trades={f.trades_dia}"
    )

# ── Loop principal ────────────────────────────────────────────────────────────
def main(simulacao: bool):
    conn   = OpenFastConn(CFG.OF_HOST, CFG.OF_PORT, lambda m: None)
    fucsia = Fucsia(conn, simulacao)
    conn._cb = fucsia.on_message

    try:
        conn.conectar()
    except ConnectionRefusedError:
        log.error("Nao foi possivel conectar na porta 557.")
        log.error("Verifique se o FastTrader esta aberto e conectado.")
        sys.exit(1)

    fucsia.iniciar_assinaturas()
    log.info("FUCSIA DOLAR ativo - aguardando 09:00 BRT...")

    dia_atual = datetime.now().date()
    try:
        while True:
            time.sleep(1)

            hoje = datetime.now().date()
            if hoje != dia_atual:
                dia_atual = hoje
                fucsia.reset_diario()

            agora = datetime.now()
            if (agora.second == 0 and agora.minute % 5 == 0
                    and dtime(9, 0) <= agora.time() <= dtime(16, 30)):
                _status_log(fucsia)

    except KeyboardInterrupt:
        log.info("Fucsia Dolar encerrado pelo usuario.")
    finally:
        conn.desconectar()

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FUCSIA DOLAR - Executor WDO")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument('--sim',  action='store_true', help='Forca modo simulacao')
    grp.add_argument('--real', action='store_true', help='Forca modo real')
    args = parser.parse_args()

    if args.real:
        sim = False
    elif args.sim:
        sim = True
    else:
        sim = CFG.SIMULACAO

    if not sim:
        print("\nMODO REAL ATIVADO - ordens serao enviadas a corretora.")
        print(f"  Ativo:      {CFG.ATIVO}")
        print(f"  Conta:      {CFG.CONTA}")
        print(f"  Quantidade: {CFG.QUANTIDADE}")
        print(f"  Gatilho:    +-{CFG.GATILHO_PCT*100:.2f}%")
        print(f"  Stop/Gain:  {CFG.STOP_PTS}/{CFG.GAIN_PTS} pts")
        resp = input("  Confirma? (sim/nao): ").strip().lower()
        if resp != 'sim':
            print("Abortado.")
            sys.exit(0)

    main(sim)
