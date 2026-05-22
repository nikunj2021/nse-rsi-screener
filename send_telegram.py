"""
send_telegram.py
================
Reads the three JSON report files produced by the RSI screeners and sends
a formatted Telegram alert for each index.

Required environment variables (set as GitHub Secrets):
  TELEGRAM_BOT_TOKEN  – Bot token from @BotFather
  TELEGRAM_CHAT_ID    – Target chat / channel ID (e.g. -1001234567890)

Message layout per index:
  • Header with index name, run date, screened count
  • Table-style list of stocks that passed all filters
  • Watchlist setup section (M-RSI>60, W-RSI>60, 40≤D-RSI<45)
  • Footer with link to the GitHub Pages dashboard
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

BOT_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID     = os.environ.get("TELEGRAM_CHAT_ID", "")

# Your GitHub Pages URL – update if your repo name differs
DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL",
    "https://nikunj2021.github.io/nse-rsi-screener/"
)

JSON_FILES = [
    ("Nifty 50",           "Nifty50_data.json"),
    ("Nifty Microcap 250", "Micro250_data.json"),
    ("NSE 500",            "NSE500_data.json"),
]

# Telegram sendMessage endpoint
TG_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(filename):
    path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(path):
        print(f"  [SKIP] {filename} not found.")
        return None
    with open(path) as f:
        return json.load(f)


def esc(text):
    """Escape special chars for Telegram MarkdownV2."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def rsi_emoji(val):
    """Visual indicator for RSI level."""
    if val is None:
        return "⬜"
    if val >= 70:
        return "🟢"
    if val >= 60:
        return "🟡"
    if val >= 50:
        return "🟠"
    return "🔴"


def fmt_num(val, decimals=2):
    if val is None:
        return "N/A"
    if decimals == 0:
        return f"{int(val):,}"
    return f"{val:,.{decimals}f}"


def vol_str(val):
    """Compact volume: 1,234,567 → 12.3L  or  1.2Cr"""
    if val is None:
        return "N/A"
    if val >= 1_00_00_000:
        return f"{val/1_00_00_000:.1f}Cr"
    if val >= 1_00_000:
        return f"{val/1_00_000:.1f}L"
    return f"{int(val):,}"


def build_screened_block(rows, index_label):
    """Build the 'passed all filters' section (MarkdownV2)."""
    if not rows:
        return f"_No stocks passed all filters this week\\._\n"

    sorted_rows = sorted(rows, key=lambda x: x.get("Daily_RSI") or 0, reverse=True)
    lines = [f"*{esc(index_label)} — Screened Stocks* \\({len(rows)}\\)\n"]
    lines.append("`Symbol      Price    D  W  M   ADX MCap`")

    for r in sorted_rows:
        sym   = r.get("Symbol", "")
        price = fmt_num(r.get("Current_Price"), 1)
        d_rsi = r.get("Daily_RSI")
        w_rsi = r.get("Weekly_RSI")
        m_rsi = r.get("Monthly_RSI")
        adx   = fmt_num(r.get("ADX"), 0)
        mcap  = fmt_num(r.get("MarketCap_Cr"), 0)

        d_e = rsi_emoji(d_rsi)
        w_e = rsi_emoji(w_rsi)
        m_e = rsi_emoji(m_rsi)

        d_str = f"{d_rsi:.0f}" if d_rsi is not None else "–"
        w_str = f"{w_rsi:.0f}" if w_rsi is not None else "–"
        m_str = f"{m_rsi:.0f}" if m_rsi is not None else "–"

        tv_url = f"https://www.tradingview.com/chart/?symbol=NSE:{sym}"

        # One line per stock with a clickable symbol
        lines.append(
            f"[{esc(sym)}]({tv_url}) ₹{esc(price)} "
            f"{d_e}{esc(d_str)} {w_e}{esc(w_str)} {m_e}{esc(m_str)} "
            f"ADX:{esc(adx)} ₹{esc(mcap)}Cr"
        )

    return "\n".join(lines) + "\n"


def build_watchlist_block(rsi_all, index_label):
    """Watchlist setup: M-RSI>60, W-RSI>60, 40≤D-RSI<45."""
    watchlist = []
    for r in (rsi_all or []):
        d = r.get("Daily_RSI")
        w = r.get("Weekly_RSI")
        m = r.get("Monthly_RSI")
        try:
            if m and m > 60 and w and w > 60 and d and 40 <= d < 45:
                watchlist.append(r)
        except TypeError:
            pass

    if not watchlist:
        return ""

    lines = [f"\n👀 *Watchlist Setup* — {esc(index_label)} \\({len(watchlist)}\\)"]
    lines.append("_M\\>60 \\& W\\>60 \\& 40≤D\\<45_\n")
    for r in sorted(watchlist, key=lambda x: x.get("Daily_RSI") or 0):
        sym   = r.get("Symbol", "")
        d_rsi = r.get("Daily_RSI")
        w_rsi = r.get("Weekly_RSI")
        m_rsi = r.get("Monthly_RSI")
        price = r.get("Current_Price")
        tv    = f"https://www.tradingview.com/chart/?symbol=NSE:{sym}"

        d_str = f"{d_rsi:.0f}" if d_rsi is not None else "–"
        w_str = f"{w_rsi:.0f}" if w_rsi is not None else "–"
        m_str = f"{m_rsi:.0f}" if m_rsi is not None else "–"
        p_str = f"₹{price:,.1f}" if isinstance(price, (int, float)) else str(price)

        lines.append(
            f"[{esc(sym)}]({tv}) {esc(p_str)} "
            f"D:{esc(d_str)} W:{esc(w_str)} M:{esc(m_str)}"
        )

    return "\n".join(lines) + "\n"


def build_message(label, data):
    """Assemble full MarkdownV2 message for one index."""
    screened  = data.get("screened", [])
    rsi_all   = data.get("rsi_summary", [])
    generated = data.get("generated", "–")

    now_ist = datetime.now(timezone.utc).strftime("%d %b %Y")
    header = (
        f"📊 *NSE RSI Screener — {esc(label)}*\n"
        f"🗓 {esc(now_ist)}  \\|  Generated: {esc(generated)}\n\n"
    )

    screened_block  = build_screened_block(screened, label)
    watchlist_block = build_watchlist_block(rsi_all, label)

    footer = (
        f"\n🔗 [Full Dashboard]({DASHBOARD_URL})"
    )

    return header + screened_block + watchlist_block + footer


def send_message(text, parse_mode="MarkdownV2"):
    """POST a message to Telegram. Splits at 4096-char limit if needed."""
    if not BOT_TOKEN or not CHAT_ID:
        print("  [ERROR] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        sys.exit(1)

    # Telegram max message length
    MAX_LEN = 4096
    chunks = []

    # Split on newline boundaries to avoid breaking MarkdownV2 mid-entity
    if len(text) <= MAX_LEN:
        chunks = [text]
    else:
        lines = text.split("\n")
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > MAX_LEN:
                chunks.append(current)
                current = line + "\n"
            else:
                current += line + "\n"
        if current:
            chunks.append(current)

    for i, chunk in enumerate(chunks, 1):
        payload = json.dumps({
            "chat_id":                  CHAT_ID,
            "text":                     chunk,
            "parse_mode":               parse_mode,
            "disable_web_page_preview": True,
        }).encode()

        req = urllib.request.Request(
            TG_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
                if result.get("ok"):
                    print(f"  ✅  Chunk {i}/{len(chunks)} sent.")
                else:
                    print(f"  [WARN] Telegram API error: {result}")
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"  [ERROR] HTTP {e.code}: {body}")
            # Fall back to plain text if MarkdownV2 parse fails
            if parse_mode == "MarkdownV2" and e.code == 400:
                print("  Retrying as plain text …")
                send_message(chunk.replace("\\", ""), parse_mode="")
        except Exception as e:
            print(f"  [ERROR] {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        print("❌  TELEGRAM_BOT_TOKEN is not set. Exiting.")
        sys.exit(1)
    if not CHAT_ID:
        print("❌  TELEGRAM_CHAT_ID is not set. Exiting.")
        sys.exit(1)

    any_data = False
    for label, json_file in JSON_FILES:
        print(f"\n── {label} ──")
        data = load_json(json_file)
        if data is None:
            continue
        any_data = True
        msg = build_message(label, data)
        print(f"  Sending ({len(msg)} chars) …")
        send_message(msg)

    if not any_data:
        print("\nNo JSON files found — nothing sent.")
        sys.exit(1)

    print("\n✅  All Telegram alerts dispatched.")


if __name__ == "__main__":
    main()
