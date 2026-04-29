"""
Gera relatorio HTML da estrategia WDO S7/G10 1%
"""
import pandas as pd
import numpy as np
import json, sys, os, warnings
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

VALOR_PONTO = 10.0
GATILHO_PCT = 0.01
STOP_PTS    = 7
GAIN_PTS    = 10
OUT_PATH    = "C:/estrategia/results/relatorio_wdo_s7g10.html"

# ── Carrega e processa dados ───────────────────────────────────────────────────
df_raw = pd.read_csv('C:/estrategia/data/xp_wdo_m1.csv', parse_dates=['time'])
df_raw = df_raw.set_index('time').sort_index()
df_sess = df_raw.between_time('09:00', '16:30')
dias_todos = sorted(set(df_sess.index.date))

data_fim = df_sess.index.max()
data_60  = data_fim - pd.Timedelta(days=60)

def rodar(dias, df_s):
    trades = []
    for dia in dias:
        d = df_s[df_s.index.date == dia].copy()
        c0900 = d.between_time('09:00','09:00')
        if len(c0900) == 0:
            continue
        open_0900 = c0900['open'].iloc[0]
        for direcao in ('COMPRA','VENDA'):
            gatilho = open_0900*(1-GATILHO_PCT) if direcao=='COMPRA' else open_0900*(1+GATILHO_PCT)
            toque   = d[d['low']<=gatilho] if direcao=='COMPRA' else d[d['high']>=gatilho]
            if len(toque) == 0:
                continue
            entry_candle = toque.index[0]
            entry_price  = gatilho
            tp = entry_price+GAIN_PTS if direcao=='COMPRA' else entry_price-GAIN_PTS
            sl = entry_price-STOP_PTS if direcao=='COMPRA' else entry_price+STOP_PTS
            candles_after = d[d.index > entry_candle]
            resultado = exit_price = None
            for idx, row in candles_after.iterrows():
                if direcao == 'COMPRA':
                    if row['high']>=tp: resultado='GAIN'; exit_price=tp; break
                    if row['low'] <=sl: resultado='LOSS'; exit_price=sl; break
                else:
                    if row['low'] <=tp: resultado='GAIN'; exit_price=tp; break
                    if row['high']>=sl: resultado='LOSS'; exit_price=sl; break
            if resultado is None:
                if len(candles_after)==0: continue
                exit_price = candles_after.iloc[-1]['close']
                pnl_pts    = (exit_price-entry_price) if direcao=='COMPRA' else (entry_price-exit_price)
                resultado  = 'TIMEOUT'
            else:
                pnl_pts = GAIN_PTS if resultado=='GAIN' else -STOP_PTS
            trades.append({
                'date': dia, 'direcao': direcao,
                'open_0900': round(open_0900,1),
                'entry': round(entry_price,1),
                'exit':  round(exit_price,1),
                'resultado': resultado,
                'pnl_pts': round(pnl_pts,1),
                'pnl_brl': round(pnl_pts*VALOR_PONTO,2),
            })
    return pd.DataFrame(trades)

print("Processando backtest completo (826 dias)...")
df_full = rodar(dias_todos, df_sess)

print("Processando ultimos 60 dias...")
dias_60 = [d for d in dias_todos if pd.Timestamp(d) >= data_60]
df_60   = rodar(dias_60, df_sess)

def stats(df):
    if len(df) == 0:
        return {}
    n      = len(df)
    n_gain = (df['resultado']=='GAIN').sum()
    n_loss = (df['resultado']=='LOSS').sum()
    n_time = (df['resultado']=='TIMEOUT').sum()
    wr     = n_gain/n*100
    gg     = df[df['pnl_brl']>0]['pnl_brl'].sum()
    gl     = abs(df[df['pnl_brl']<0]['pnl_brl'].sum())
    pf     = gg/gl if gl>0 else 0
    pnl    = df['pnl_brl'].sum()
    eq     = df.sort_values('date')['pnl_brl'].cumsum()
    dd     = (eq - eq.cummax()).min()
    return dict(n=n, n_gain=int(n_gain), n_loss=int(n_loss), n_time=int(n_time),
                wr=round(wr,1), pf=round(pf,2), pnl=round(pnl,2), dd=round(dd,2))

s_full = stats(df_full)
s_60   = stats(df_60)

def stats_dir(df, direcao):
    s = df[df['direcao']==direcao]
    return stats(s)

sf_c = stats_dir(df_full,'COMPRA')
sf_v = stats_dir(df_full,'VENDA')
s60_c = stats_dir(df_60,'COMPRA')
s60_v = stats_dir(df_60,'VENDA')

# Curva de equity mensal (full)
df_full['date'] = pd.to_datetime(df_full['date'])
df_full_s = df_full.sort_values('date').copy()
df_full_s['equity'] = df_full_s['pnl_brl'].cumsum()
df_full_s['mes']    = df_full_s['date'].dt.to_period('M').astype(str)

equity_labels = [str(d.date()) for d in df_full_s['date']]
equity_values = df_full_s['equity'].tolist()

# P&L mensal
mensal = df_full_s.groupby('mes')['pnl_brl'].sum().reset_index()
mensal_labels = mensal['mes'].tolist()
mensal_values = mensal['pnl_brl'].tolist()
mensal_colors = ['#22c55e' if v>=0 else '#ef4444' for v in mensal_values]

# Trades 60 dias para tabela
df_60_s = df_60.sort_values('date').copy()
df_60_s['date'] = df_60_s['date'].astype(str)
df_60_s['equity'] = df_60_s['pnl_brl'].cumsum()

trades_rows = ""
for _, r in df_60_s.iterrows():
    cor_res = "#22c55e" if r['resultado']=='GAIN' else ("#ef4444" if r['resultado']=='LOSS' else "#f59e0b")
    cor_pnl = "#22c55e" if r['pnl_brl']>=0 else "#ef4444"
    dir_badge = f'<span style="background:#1d4ed8;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{r["direcao"]}</span>' if r['direcao']=='COMPRA' else f'<span style="background:#dc2626;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{r["direcao"]}</span>'
    trades_rows += f"""
    <tr>
      <td>{r['date']}</td>
      <td>{dir_badge}</td>
      <td>{r['open_0900']:.1f}</td>
      <td>{r['entry']:.1f}</td>
      <td>{r['exit']:.1f}</td>
      <td><b style="color:{cor_res}">{r['resultado']}</b></td>
      <td style="color:{cor_pnl};font-weight:bold">R$ {r['pnl_brl']:.2f}</td>
      <td style="color:{cor_pnl}">R$ {r['equity']:.2f}</td>
    </tr>"""

gerado_em = datetime.now().strftime('%d/%m/%Y %H:%M')

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatorio WDO — Mean Reversion 1% | S7/G10</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }}
  .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%); padding: 32px 40px; border-bottom: 1px solid #1e293b; }}
  .header h1 {{ font-size: 26px; font-weight: 700; color: #f1f5f9; }}
  .header p  {{ color: #94a3b8; margin-top: 6px; font-size: 14px; }}
  .badge {{ display:inline-block; background:#1e40af; color:#bfdbfe; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; margin-right:8px; margin-top:8px; }}
  .content {{ padding: 32px 40px; max-width: 1300px; margin: 0 auto; }}
  .section-title {{ font-size: 18px; font-weight: 700; color: #f1f5f9; margin: 32px 0 16px; border-left: 4px solid #3b82f6; padding-left: 12px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); gap: 16px; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }}
  .card .label {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: .05em; }}
  .card .value {{ font-size: 28px; font-weight: 800; margin-top: 6px; }}
  .card .sub   {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
  .green {{ color: #22c55e; }}
  .red   {{ color: #ef4444; }}
  .blue  {{ color: #60a5fa; }}
  .white {{ color: #f1f5f9; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .grid3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; }}
  .chart-box {{ background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155; }}
  .chart-box h3 {{ font-size: 14px; color: #94a3b8; margin-bottom: 16px; font-weight: 600; }}
  .dir-block {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }}
  .dir-block h3 {{ font-size: 15px; font-weight: 700; margin-bottom: 16px; }}
  .dir-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #0f172a; font-size: 14px; }}
  .dir-row:last-child {{ border-bottom: none; }}
  .dir-row .k {{ color: #94a3b8; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #0f172a; color: #94a3b8; padding: 10px 14px; text-align: left; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #1e293b; }}
  .table-box {{ background: #0f172a; border-radius: 12px; border: 1px solid #1e293b; overflow: hidden; }}
  .comp60 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .period-badge {{ font-size: 11px; background: #0f172a; color: #64748b; padding: 2px 8px; border-radius: 4px; margin-left: 8px; }}
  .footer {{ text-align: center; padding: 24px; color: #475569; font-size: 12px; margin-top: 32px; }}
  @media(max-width:768px) {{ .grid2,.grid3,.comp60 {{ grid-template-columns:1fr; }} .content {{ padding: 16px; }} }}
</style>
</head>
<body>

<div class="header">
  <h1>WDO — Mean Reversion 1%</h1>
  <p>Mini Dolar Futuro &nbsp;|&nbsp; Gatilho: abertura ±1% &nbsp;|&nbsp; Stop: 7 pts &nbsp;|&nbsp; Gain: 10 pts &nbsp;|&nbsp; Janela: 09:00–16:30 BRT</p>
  <span class="badge">826 dias testados</span>
  <span class="badge">Jan/2023 – Abr/2026</span>
  <span class="badge">1 pt = R$ 10,00</span>
  <span class="badge">Gerado em {gerado_em}</span>
</div>

<div class="content">

  <!-- RESUMO GERAL -->
  <div class="section-title">Resumo Geral — 826 dias</div>
  <div class="cards">
    <div class="card">
      <div class="label">Total Trades</div>
      <div class="value white">{s_full['n']}</div>
      <div class="sub">GAIN {s_full['n_gain']} &nbsp;|&nbsp; LOSS {s_full['n_loss']} &nbsp;|&nbsp; TO {s_full['n_time']}</div>
    </div>
    <div class="card">
      <div class="label">Win Rate</div>
      <div class="value {'green' if s_full['wr']>=50 else 'red'}">{s_full['wr']}%</div>
      <div class="sub">{s_full['n_gain']} acertos de {s_full['n']}</div>
    </div>
    <div class="card">
      <div class="label">Profit Factor</div>
      <div class="value {'green' if s_full['pf']>=1 else 'red'}">{s_full['pf']}</div>
      <div class="sub">Meta: acima de 1.0</div>
    </div>
    <div class="card">
      <div class="label">P&amp;L Total</div>
      <div class="value {'green' if s_full['pnl']>=0 else 'red'}">R$ {s_full['pnl']:,.2f}</div>
      <div class="sub">1 contrato mini</div>
    </div>
    <div class="card">
      <div class="label">Max Drawdown</div>
      <div class="value red">R$ {s_full['dd']:,.2f}</div>
      <div class="sub">Pior sequencia</div>
    </div>
    <div class="card">
      <div class="label">Frequencia</div>
      <div class="value blue">{s_full['n']/826*100:.1f}%</div>
      <div class="sub">dias com sinal</div>
    </div>
  </div>

  <!-- GRAFICOS -->
  <div class="section-title">Curva de Equity & P&amp;L Mensal</div>
  <div class="grid2">
    <div class="chart-box">
      <h3>Curva de Equity acumulada (R$)</h3>
      <canvas id="equityChart" height="220"></canvas>
    </div>
    <div class="chart-box">
      <h3>P&amp;L por mes (R$)</h3>
      <canvas id="mensalChart" height="220"></canvas>
    </div>
  </div>

  <!-- POR DIRECAO -->
  <div class="section-title">Resultado por Direcao — 826 dias</div>
  <div class="grid2">
    <div class="dir-block">
      <h3 class="blue">COMPRA &nbsp;<small style="color:#64748b;font-weight:400">WDO cai 1% → reverter para cima</small></h3>
      <div class="dir-row"><span class="k">Trades</span><span>{sf_c['n']}</span></div>
      <div class="dir-row"><span class="k">Win Rate</span><span class="{'green' if sf_c['wr']>=50 else 'red'}">{sf_c['wr']}%</span></div>
      <div class="dir-row"><span class="k">Profit Factor</span><span class="{'green' if sf_c['pf']>=1 else 'red'}">{sf_c['pf']}</span></div>
      <div class="dir-row"><span class="k">P&amp;L Total</span><span class="{'green' if sf_c['pnl']>=0 else 'red'}"><b>R$ {sf_c['pnl']:,.2f}</b></span></div>
      <div class="dir-row"><span class="k">Max Drawdown</span><span class="red">R$ {sf_c['dd']:,.2f}</span></div>
    </div>
    <div class="dir-block">
      <h3 style="color:#f87171">VENDA &nbsp;<small style="color:#64748b;font-weight:400">WDO sobe 1% → reverter para baixo</small></h3>
      <div class="dir-row"><span class="k">Trades</span><span>{sf_v['n']}</span></div>
      <div class="dir-row"><span class="k">Win Rate</span><span class="{'green' if sf_v['wr']>=50 else 'red'}">{sf_v['wr']}%</span></div>
      <div class="dir-row"><span class="k">Profit Factor</span><span class="{'green' if sf_v['pf']>=1 else 'red'}">{sf_v['pf']}</span></div>
      <div class="dir-row"><span class="k">P&amp;L Total</span><span class="{'green' if sf_v['pnl']>=0 else 'red'}"><b>R$ {sf_v['pnl']:,.2f}</b></span></div>
      <div class="dir-row"><span class="k">Max Drawdown</span><span class="red">R$ {sf_v['dd']:,.2f}</span></div>
    </div>
  </div>

  <!-- ULTIMOS 60 DIAS -->
  <div class="section-title">Ultimos 60 Dias <span class="period-badge">{dias_60[0]} → {dias_60[-1]} &nbsp;|&nbsp; {len(dias_60)} pregoes</span></div>
  <div class="cards" style="margin-bottom:24px">
    <div class="card">
      <div class="label">Trades</div>
      <div class="value white">{s_60['n']}</div>
    </div>
    <div class="card">
      <div class="label">Win Rate</div>
      <div class="value {'green' if s_60['wr']>=50 else 'red'}">{s_60['wr']}%</div>
    </div>
    <div class="card">
      <div class="label">Profit Factor</div>
      <div class="value {'green' if s_60.get('pf',0)>=1 else 'red'}">{s_60.get('pf','—')}</div>
    </div>
    <div class="card">
      <div class="label">P&amp;L</div>
      <div class="value {'green' if s_60['pnl']>=0 else 'red'}">R$ {s_60['pnl']:,.2f}</div>
    </div>
    <div class="card">
      <div class="label">Max DD</div>
      <div class="value red">R$ {s_60['dd']:,.2f}</div>
    </div>
    <div class="card">
      <div class="label">COMPRA</div>
      <div class="value green">R$ {s60_c.get('pnl',0):,.2f}</div>
      <div class="sub">WR {s60_c.get('wr',0)}%</div>
    </div>
  </div>

  <div class="table-box">
    <table>
      <thead>
        <tr>
          <th>Data</th><th>Direcao</th><th>Open 09:00</th><th>Entrada</th>
          <th>Saida</th><th>Resultado</th><th>P&amp;L R$</th><th>Equity R$</th>
        </tr>
      </thead>
      <tbody>{trades_rows}</tbody>
    </table>
  </div>

  <!-- PARAMETROS -->
  <div class="section-title">Parametros da Estrategia</div>
  <div class="grid3">
    <div class="dir-block">
      <h3 class="white">Configuracao</h3>
      <div class="dir-row"><span class="k">Ativo</span><span>WDO (Mini Dolar)</span></div>
      <div class="dir-row"><span class="k">Gatilho</span><span>±1.00% do open 09:00</span></div>
      <div class="dir-row"><span class="k">Stop</span><span>7 pontos (R$ 70)</span></div>
      <div class="dir-row"><span class="k">Gain</span><span>10 pontos (R$ 100)</span></div>
      <div class="dir-row"><span class="k">Janela</span><span>09:00 – 16:30 BRT</span></div>
    </div>
    <div class="dir-block">
      <h3 class="white">Logica</h3>
      <div class="dir-row"><span class="k">Timeframe dados</span><span>M1 (1 minuto)</span></div>
      <div class="dir-row"><span class="k">Referencia</span><span>Open do candle 09:00</span></div>
      <div class="dir-row"><span class="k">Entrada COMPRA</span><span>Low toca open − 1%</span></div>
      <div class="dir-row"><span class="k">Entrada VENDA</span><span>High toca open + 1%</span></div>
      <div class="dir-row"><span class="k">Saida forcada</span><span>Close 16:30</span></div>
    </div>
    <div class="dir-block">
      <h3 class="white">Dados</h3>
      <div class="dir-row"><span class="k">Fonte</span><span>XP / MetaTrader 5</span></div>
      <div class="dir-row"><span class="k">Periodo</span><span>Jan/2023 – Abr/2026</span></div>
      <div class="dir-row"><span class="k">Dias testados</span><span>826 pregoes</span></div>
      <div class="dir-row"><span class="k">Valor ponto</span><span>R$ 10,00 / mini</span></div>
      <div class="dir-row"><span class="k">Custo op.</span><span>Nao considerado</span></div>
    </div>
  </div>

</div>

<div class="footer">Gerado em {gerado_em} &nbsp;|&nbsp; Dados: XP/MT5 &nbsp;|&nbsp; Apenas para fins de estudo — nao e recomendacao de investimento</div>

<script>
const eq_labels = {json.dumps(equity_labels)};
const eq_values = {json.dumps(equity_values)};
const m_labels  = {json.dumps(mensal_labels)};
const m_values  = {json.dumps(mensal_values)};
const m_colors  = {json.dumps(mensal_colors)};

Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#1e293b';

new Chart(document.getElementById('equityChart'), {{
  type: 'line',
  data: {{
    labels: eq_labels,
    datasets: [{{
      label: 'Equity R$',
      data: eq_values,
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.08)',
      borderWidth: 1.5,
      pointRadius: 0,
      fill: true,
      tension: 0.1,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ maxTicksLimit: 8, font: {{ size: 10 }} }} }},
      y: {{ ticks: {{ callback: v => 'R$' + v.toLocaleString('pt-BR') }} }}
    }}
  }}
}});

new Chart(document.getElementById('mensalChart'), {{
  type: 'bar',
  data: {{
    labels: m_labels,
    datasets: [{{
      label: 'P&L R$',
      data: m_values,
      backgroundColor: m_colors,
      borderRadius: 4,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ font: {{ size: 10 }} }} }},
      y: {{ ticks: {{ callback: v => 'R$' + v }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Relatorio gerado: {OUT_PATH}")
