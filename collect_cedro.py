"""
Coleta histórico de candles do WIN via Cedro OpenFAST v2.
FastTrader deve estar aberto e conectado antes de rodar.

Uso:
    python collect_cedro.py                    # M1, 2000 candles, WINM26
    python collect_cedro.py --ativo WINFUT --periodo M5 --qtd 5000
    python collect_cedro.py --dump             # modo debug: loga tudo que chega
"""

import socket
import threading
import time
import csv
import argparse
import logging
import os
import sys
from datetime import datetime

# ── Configuração ──────────────────────────────────────────────────────────────
HOST    = "localhost"
PORT    = 557
SOH     = '\x01'
OUT_DIR = "C:/estrategia/dados_cedro"
os.makedirs(OUT_DIR, exist_ok=True)

_dump_log = os.path.join(OUT_DIR, f"dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_dump_log, encoding="utf-8"),
    ],
)
# Força stdout a usar utf-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
log = logging.getLogger("CEDRO")

# ── Conexão base ──────────────────────────────────────────────────────────────
class OpenFastConn:
    def __init__(self, on_msg_cb):
        self._sock    = None
        self._cb      = on_msg_cb
        self._lock    = threading.Lock()
        self._running = False

    def conectar(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(10)
        self._sock.connect((HOST, PORT))
        self._running = True
        self._enviar_raw("OPENFAST")
        ver = self._receber_linha()
        log.info(f"Conectado: {ver.replace(SOH,'|')}")
        threading.Thread(target=self._loop_leitura, daemon=True).start()

    def cmd(self, msg):
        raw = msg.replace('#', SOH)
        with self._lock:
            self._sock.send((raw + '\n').encode('utf-8'))
        log.debug(f"CMD -> {msg}")

    def _enviar_raw(self, msg):
        with self._lock:
            self._sock.send((msg + '\n').encode('utf-8'))

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
                if linha and not linha.startswith('SYN'):
                    self._cb(linha)
            except socket.timeout:
                continue
            except Exception as e:
                log.error(f"Leitura: {e}")
                break

    def desconectar(self):
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass


# ── Coletor de candles ────────────────────────────────────────────────────────
class CandleCollector:
    """
    Tenta os comandos de histórico conhecidos da Cedro OpenFAST v2
    e salva o que vier em CSV.
    """

    # Formatos de período que a Cedro costuma aceitar
    PERIODOS_ALIAS = {
        'M1': ['M1', '1', '1m', 'MINUTE1', 'MIN1'],
        'M5': ['M5', '5', '5m', 'MINUTE5', 'MIN5'],
        'M15':['M15','15','15m'],
        'M30':['M30','30','30m'],
        'H1': ['H1', '60', '1h', 'HOUR1'],
        'D':  ['D',  'D1', 'DAY', 'DAILY'],
    }

    def __init__(self, ativo, periodo, qtd, dump_mode=False):
        self.ativo     = ativo
        self.periodo   = periodo
        self.qtd       = qtd
        self.dump      = dump_mode
        self.candles   = []
        self.done      = threading.Event()
        self.conn      = OpenFastConn(self._on_msg)
        self._tentativa = 0

    def coletar(self):
        self.conn.conectar()
        time.sleep(0.5)

        if self.dump:
            log.info("Modo DUMP - enviando comandos exploratorios...")
            self._enviar_cmds_exploratorios()
        else:
            self._tentar_proxima_variante()

        # Aguarda até 60 segundos por dados
        self.done.wait(timeout=60)
        self.conn.desconectar()

        if self.candles:
            self._salvar()
        else:
            log.warning("Nenhum candle recebido. Tente --dump para ver o que o servidor retorna.")

    # ── Variantes de comando ───────────────────────────────────────────────────
    def _variantes(self):
        a = self.ativo
        q = self.qtd
        aliases = self.PERIODOS_ALIAS.get(self.periodo, [self.periodo])
        cmds = []
        for p in aliases:
            cmds += [
                f"on#GCH#{a}#{p}#{q}",
                f"on#CANDLE#{a}#{p}#{q}",
                f"on#CHARTHISTORY#{a}#{p}#{q}",
                f"on#HISTORY#{a}#{p}#{q}",
                f"GCH#{a}#{p}#{q}",
                f"on#GCH#{a}#{p}#{q}#0",          # com flag extra
                f"on#GCH#{a}#{p}#{q}##",
            ]
        return cmds

    def _tentar_proxima_variante(self):
        variantes = self._variantes()
        if self._tentativa < len(variantes):
            cmd = variantes[self._tentativa]
            self._tentativa += 1
            log.info(f"Tentativa {self._tentativa}: {cmd}")
            self.conn.cmd(cmd)
            # Se não vier nada em 5s, tenta a próxima
            threading.Timer(5.0, self._tentar_proxima_variante).start()
        else:
            log.warning("Esgotadas todas as variantes de comando.")
            self.done.set()

    def _enviar_cmds_exploratorios(self):
        """Modo dump: envia vários comandos e loga todas as respostas."""
        cmds = [
            f"on#SQT#{self.ativo}#LAST",
            f"on#GCH#{self.ativo}#M1#10",
            f"on#GCH#{self.ativo}#1#10",
            f"on#GCH#{self.ativo}#D#10",
            f"on#GQH#{self.ativo}#M1#10",
            f"on#GQH#{self.ativo}#1#10",
            f"on#SQTHIST#{self.ativo}#10",
            f"on#CANDLE#{self.ativo}#M1#10",
            f"on#CHARTHISTORY#{self.ativo}#M1#10",
            f"on#HISTORY#{self.ativo}#M1#10",
            f"GCH#{self.ativo}#M1#10",
            f"GQH#{self.ativo}#M1#10",
        ]
        for c in cmds:
            self.conn.cmd(c)
            time.sleep(0.3)
        # Em modo dump fica ouvindo por 30s
        threading.Timer(30.0, self.done.set).start()

    # ── Parser de mensagens ────────────────────────────────────────────────────
    def _on_msg(self, raw: str):
        legivel = raw.replace(SOH, '|')

        if self.dump:
            log.info(f"RX: {legivel}")
            return

        log.debug(f"RX: {legivel}")
        campos = legivel.split('|')
        tipo   = campos[0].upper()

        # Formatos comuns de resposta de candle na Cedro
        if tipo in ('GCH', 'CANDLE', 'CHARTHISTORY', 'HISTORY', 'C'):
            self._parse_candle(campos, raw)
        elif tipo == 'SQT':
            pass  # cotação em tempo real, ignorar
        elif tipo in ('ERROR', 'ERR'):
            log.warning(f"Erro do servidor: {legivel}")
        else:
            # Logar tipos desconhecidos — pode ser o candle num formato inesperado
            log.info(f"MSG desconhecida [{tipo}]: {legivel}")

    def _parse_candle(self, campos, raw):
        """
        Tenta extrair OHLCV da mensagem.
        Cedro costuma enviar: TIPO|ATIVO|DATA|HORA|OPEN|HIGH|LOW|CLOSE|VOL|...
        """
        try:
            # Descobre a posição dos valores numéricos
            nums = []
            for c in campos:
                try:
                    nums.append(float(c.replace(',', '.')))
                except Exception:
                    nums.append(None)

            # Pega data/hora (campos que têm formato de data)
            data_hora = None
            for c in campos[1:4]:
                if len(c) >= 8 and c[:2].isdigit():
                    data_hora = c
                    break

            # Busca 4 valores consecutivos não-nulos (OHLCV)
            floats = [(i, v) for i, v in enumerate(nums) if v is not None and v > 0]
            if len(floats) >= 4:
                vals = [v for _, v in floats[:5]]
                candle = {
                    'datetime': data_hora or '',
                    'open':  vals[0],
                    'high':  vals[1],
                    'low':   vals[2],
                    'close': vals[3],
                    'volume':vals[4] if len(vals) > 4 else 0,
                    'raw':   raw.replace(SOH, '|'),
                }
                self.candles.append(candle)

                if len(self.candles) % 100 == 0:
                    log.info(f"{len(self.candles)} candles recebidos...")

                # Se recebeu a quantidade solicitada, encerra
                if len(self.candles) >= self.qtd:
                    log.info(f"Coleta completa: {len(self.candles)} candles")
                    self.done.set()
        except Exception as e:
            log.debug(f"Parse falhou: {e} | {raw.replace(SOH,'|')}")

    def _salvar(self):
        ts   = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(OUT_DIR, f"{self.ativo}_{self.periodo}_{ts}.csv")
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['datetime','open','high','low','close','volume','raw'])
            writer.writeheader()
            writer.writerows(self.candles)
        log.info(f"Salvo: {path}  ({len(self.candles)} candles)")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta historico WIN via Cedro OpenFAST")
    parser.add_argument('--ativo',   default='WINM26', help='Ativo (ex: WINM26, WINFUT)')
    parser.add_argument('--periodo', default='M1',     help='Periodo (M1, M5, M15, H1, D)')
    parser.add_argument('--qtd',     default=2000, type=int, help='Quantidade de candles')
    parser.add_argument('--dump',    action='store_true',    help='Modo debug: loga tudo')
    args = parser.parse_args()

    log.info(f"Log salvo em: {_dump_log}")
    log.info(f"Ativo={args.ativo} | Periodo={args.periodo} | Qtd={args.qtd} | Dump={args.dump}")
    coletor = CandleCollector(args.ativo, args.periodo, args.qtd, args.dump)
    coletor.coletar()
