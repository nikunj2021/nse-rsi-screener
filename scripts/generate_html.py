"""
generate_html.py
Reads the three JSON report files produced by the screeners
and writes docs/index.html (served via GitHub Pages).
"""

import json, os, shutil
from datetime import datetime

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
DOCS_DIR    = os.path.join(BASE_DIR, "docs")
os.makedirs(DOCS_DIR, exist_ok=True)

JSON_FILES = [
    ("Nifty 50",           "Nifty50_data.json"),
    ("Nifty Microcap 250", "Micro250_data.json"),
    ("NSE 500",            "NSE500_data.json"),
]

XLSX_FILES = [
    ("Nifty 50",           "Nifty50_stocks.xlsx"),
    ("Nifty Microcap 250", "Micro250_stocks.xlsx"),
    ("NSE 500",            "NSE500_stocks.xlsx"),
]

def load_json(filename):
    path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def rsi_badge(val, thresholds=((70,"#27ae60"),(60,"#2ecc71"),(50,"#f39c12"),(40,"#e67e22"),(0,"#e74c3c"))):
    if val is None: return '<span style="color:#999">N/A</span>'
    for t, color in thresholds:
        if val >= t:
            return f'<span style="color:{color};font-weight:700">{val}</span>'
    return f'<span style="color:#e74c3c">{val}</span>'


def screened_table(rows):
    if not rows:
        return '<p style="color:#888;font-style:italic">No stocks passed all filters this week.</p>'
    hdr = ["Symbol","Price","D-RSI","W-RSI","M-RSI","ADX","EMA150","EMA200","Avg Vol","MCap Cr","Chart"]
    cols = ["Symbol","Current_Price","Daily_RSI","Weekly_RSI","Monthly_RSI",
            "ADX","EMA_150","EMA_200","Avg_Volume","MarketCap_Cr"]
    html = '<table class="data-table"><thead><tr>'
    for h in hdr:
        html += f'<th>{h}</th>'
    html += '</tr></thead><tbody>'
    for r in sorted(rows, key=lambda x: x.get("Daily_RSI") or 0, reverse=True):
        sym = r.get("Symbol","")
        tv  = f"https://www.tradingview.com/chart/?symbol=NSE:{sym}"
        html += '<tr>'
        for c in cols:
            val = r.get(c,"")
            if c in ("Daily_RSI","Weekly_RSI","Monthly_RSI"):
                html += f'<td>{rsi_badge(val)}</td>'
            elif c in ("Current_Price","EMA_150","EMA_200"):
                html += f'<td>₹{val:,.2f}</td>' if isinstance(val,(int,float)) else f'<td>{val}</td>'
            elif c == "Avg_Volume":
                html += f'<td>{int(val):,}</td>' if isinstance(val,(int,float)) else f'<td>{val}</td>'
            elif c == "MarketCap_Cr":
                html += f'<td>{int(val):,}</td>' if isinstance(val,(int,float)) else f'<td>{val}</td>'
            else:
                html += f'<td>{val}</td>'
        html += f'<td><a href="{tv}" target="_blank" class="chart-btn">📈</a></td>'
        html += '</tr>'
    html += '</tbody></table>'
    return html


def rsi_summary_table(rows):
    if not rows:
        return '<p style="color:#888;font-style:italic">No data.</p>'
    html = '<table class="data-table"><thead><tr>'
    for h in ["Symbol","Price","D-RSI","W-RSI","M-RSI","Chart"]:
        html += f'<th>{h}</th>'
    html += '</tr></thead><tbody>'
    for r in sorted(rows, key=lambda x: x.get("Daily_RSI") or 0, reverse=True):
        sym   = r.get("Symbol","")
        tv    = f"https://www.tradingview.com/chart/?symbol=NSE:{sym}"
        price = r.get("Current_Price","")
        d_rsi = r.get("Daily_RSI")
        w_rsi = r.get("Weekly_RSI")
        m_rsi = r.get("Monthly_RSI")
        try:
            highlight = (m_rsi and m_rsi > 60 and w_rsi and w_rsi > 60
                         and d_rsi and 40 <= d_rsi < 45)
        except TypeError:
            highlight = False
        row_class = ' class="highlight-row"' if highlight else ''
        price_str = f'₹{price:,.2f}' if isinstance(price,(int,float)) else str(price)
        html += f'<tr{row_class}><td>{sym}</td><td>{price_str}</td>'
        html += f'<td>{rsi_badge(d_rsi)}</td><td>{rsi_badge(w_rsi)}</td><td>{rsi_badge(m_rsi)}</td>'
        html += f'<td><a href="{tv}" target="_blank" class="chart-btn">📈</a></td></tr>'
    html += '</tbody></table>'
    return html


def build_html():
    now = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")

    tab_buttons = ""
    tab_contents = ""

    for i, (label, json_file) in enumerate(JSON_FILES):
        data      = load_json(json_file)
        screened  = data.get("screened", [])  if data else []
        rsi_all   = data.get("rsi_summary", []) if data else []
        generated = data.get("generated", "–")  if data else "–"
        xlsx_name = XLSX_FILES[i][1]
        active    = "active" if i == 0 else ""
        idx       = i

        # Copy xlsx into docs/ so GitHub Pages can serve the download
        src_xlsx = os.path.join(REPORTS_DIR, xlsx_name)
        dst_xlsx = os.path.join(DOCS_DIR, xlsx_name)
        if os.path.exists(src_xlsx):
            shutil.copy2(src_xlsx, dst_xlsx)
            print(f"  Copied {xlsx_name} -> docs/")
        else:
            print(f"  Warning: {xlsx_name} not found in reports/")

        tab_buttons += f'<button class="tab-btn {active}" onclick="switchTab({idx})">{label} <span class="badge">{len(screened)}</span></button>\n'

        tab_contents += f'''
<div class="tab-content {"active" if i==0 else ""}" id="tab-{idx}">
  <div class="section-header">
    <div>
      <h2>{label} — Screener Results</h2>
      <p class="meta">Generated: {generated} &nbsp;|&nbsp; {len(screened)} stock(s) passed filters</p>
    </div>
    <a href="{xlsx_name}" class="dl-btn" download>⬇ Download Excel</a>
  </div>
  {screened_table(screened)}

  <h2 style="margin-top:2rem">{label} — RSI Summary <span style="font-size:.85rem;font-weight:400;color:#888">({len(rsi_all)} stocks)</span></h2>
  <p class="legend">🟢 Light-green row = M-RSI &gt; 60 &amp; W-RSI &gt; 60 &amp; 40 ≤ D-RSI &lt; 45 (watchlist setup)</p>
  {rsi_summary_table(rsi_all)}
</div>
'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NSE RSI Screener Dashboard</title>
<style>
  :root{{--blue:#1F4E79;--accent:#2563eb;--green:#16a34a;--bg:#f8fafc;--card:#fff;--border:#e2e8f0}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',Arial,sans-serif;background:var(--bg);color:#1e293b;min-height:100vh}}

  /* ── Header ── */
  header{{background:var(--blue);color:#fff;padding:1.2rem 2rem;display:flex;align-items:center;gap:1rem}}
  header h1{{font-size:1.4rem;font-weight:700}}
  header .sub{{font-size:.85rem;opacity:.75;margin-top:.2rem}}
  .run-time{{margin-left:auto;font-size:.8rem;opacity:.7;text-align:right}}

  /* ── Tabs ── */
  .tabs{{display:flex;gap:.5rem;padding:1.2rem 2rem .4rem;background:#fff;border-bottom:1px solid var(--border)}}
  .tab-btn{{padding:.55rem 1.2rem;border:2px solid var(--border);border-radius:8px;background:#fff;
            cursor:pointer;font-size:.9rem;font-weight:600;color:#475569;transition:all .2s}}
  .tab-btn:hover{{border-color:var(--accent);color:var(--accent)}}
  .tab-btn.active{{background:var(--accent);border-color:var(--accent);color:#fff}}
  .badge{{background:rgba(255,255,255,.25);border-radius:99px;padding:.1rem .45rem;font-size:.75rem;margin-left:.3rem}}
  .tab-btn:not(.active) .badge{{background:#e0e7ff;color:var(--accent)}}

  /* ── Content ── */
  .tab-content{{display:none;padding:1.5rem 2rem 3rem}}
  .tab-content.active{{display:block}}

  /* ── Section header ── */
  .section-header{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:1rem}}
  .section-header h2{{font-size:1.15rem;font-weight:700;color:var(--blue)}}
  .meta{{font-size:.8rem;color:#94a3b8;margin-top:.25rem}}

  /* ── Download button ── */
  .dl-btn{{background:var(--green);color:#fff;padding:.5rem 1rem;border-radius:8px;text-decoration:none;
           font-size:.85rem;font-weight:600;white-space:nowrap;flex-shrink:0;margin-left:1rem}}
  .dl-btn:hover{{opacity:.85}}

  /* ── Table ── */
  .data-table{{width:100%;border-collapse:collapse;font-size:.85rem;background:var(--card);
               border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
  .data-table th{{background:var(--blue);color:#fff;padding:.65rem .8rem;text-align:center;font-weight:600;font-size:.8rem}}
  .data-table td{{padding:.55rem .8rem;text-align:center;border-bottom:1px solid var(--border)}}
  .data-table tr:last-child td{{border-bottom:none}}
  .data-table tr:hover td{{background:#f1f5f9}}
  .data-table td:first-child{{text-align:left;font-weight:600}}
  .highlight-row td{{background:#f0fdf4!important}}
  .highlight-row:hover td{{background:#dcfce7!important}}
  .chart-btn{{font-size:1.1rem;text-decoration:none}}

  .legend{{font-size:.78rem;color:#64748b;margin-bottom:.7rem;background:#f0fdf4;
           padding:.4rem .7rem;border-radius:6px;display:inline-block}}

  /* ── Responsive ── */
  @media(max-width:768px){{
    .tabs{{overflow-x:auto;padding:.8rem 1rem .3rem}}
    .tab-content{{padding:1rem 1rem 2rem}}
    .section-header{{flex-direction:column;gap:.6rem}}
    .data-table{{font-size:.75rem}}
    .data-table th,.data-table td{{padding:.45rem .5rem}}
  }}
</style>
</head>
<body>

<header>
  <div>
    <h1>📊 NSE RSI Screener Dashboard</h1>
    <div class="sub">Multi-timeframe RSI · EMA · ADX · Volume · MarketCap filters</div>
  </div>
  <div class="run-time">Last page build<br>{now}</div>
</header>

<div class="tabs">
{tab_buttons}
</div>

{tab_contents}

<script>
function switchTab(idx) {{
  document.querySelectorAll('.tab-btn').forEach((b,i) => b.classList.toggle('active', i===idx));
  document.querySelectorAll('.tab-content').forEach((c,i) => c.classList.toggle('active', i===idx));
}}
</script>
</body>
</html>
'''
    out = os.path.join(DOCS_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ HTML report written to: {out}")


if __name__ == "__main__":
    build_html()
