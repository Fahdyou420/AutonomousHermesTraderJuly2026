import os
import sys
import json
import re
import time
import subprocess
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

import requests

ROOT = Path(r"C:\Users\user\Desktop\hermes_claude")
REPORTS_DIR = ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

def _sh(cmd: str, timeout: int = 20) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=timeout)
    raw = (p.stdout + p.stderr).strip()
    return {"returncode": p.returncode, "raw": raw}


def add_result(name: str, status: str, detail: str, raw: str):
    results.append({
        "check": name,
        "status": status,
        "detail": detail,
        "raw": raw,
    })


def section(title: str):
    print(f"\n=== {title} ===")


results = []

# =============================
# A. STACK HEALTH
# =============================
section("A. STACK HEALTH")

r = _sh('docker ps --format "table {{.Names}}\t{{.Status}}"')
add_result("A. docker ps", "PASS" if r["returncode"] == 0 else "FAIL", "docker ps status summary", r["raw"])

try:
    r2 = requests.get("http://localhost:7778/health", timeout=10)
    raw2 = r2.text
    add_result("A. localhost:7778/health", "PASS" if r2.status_code == 200 else "FAIL",
               f"status_code={r2.status_code}", raw2)
except Exception as e:
    add_result("A. localhost:7778/health", "FAIL", str(e), str(e))

try:
    r3 = requests.get("http://localhost:8080/api/status", timeout=10)
    raw3 = r3.text
    add_result("A. localhost:8080/api/status", "PASS" if r3.status_code == 200 else "FAIL",
               f"status_code={r3.status_code}", raw3)
except Exception as e:
    add_result("A. localhost:8080/api/status", "FAIL", str(e), str(e))

try:
    r4 = requests.get("http://localhost:3000/api/status", timeout=10)
    raw4 = r4.text
    add_result("A. localhost:3000/api/status", "PASS" if r4.status_code == 200 else "FAIL",
               f"status_code={r4.status_code}", raw4)
except Exception as e:
    add_result("A. localhost:3000/api/status", "FAIL", str(e), str(e))

try:
    r5 = requests.post("http://localhost:7779/mcp", data="{}", headers={"Content-Type": "application/json"}, timeout=10)
    raw5 = r5.text
    status5 = "PASS"
    detail5 = f"status_code={r5.status_code}"
    if r5.status_code == 405:
        status5 = "FAIL"
        detail5 = "Still returning 405 per contract"
    add_result("A. localhost:7779/mcp POST {} 405 check", status5, detail5, raw5)
except Exception as e:
    add_result("A. localhost:7779/mcp POST {} 405 check", "FAIL", str(e), str(e))

# =============================
# B. MT5 / EA CONNECTIVITY
# =============================
section("B. MT5 CONNECTIVITY")

for port in [5555, 5556, 5557]:
    r6 = _sh(f'powershell -NoProfile -Command "Test-NetConnection localhost -Port {port} -WarningAction SilentlyContinue | Select-Object TcpTestSucceeded"')
    m = re.search(r"TcpTestSucceeded\s*:\s*(\w+)", r6["raw"], re.IGNORECASE)
    ok = m.group(1).lower() == "true" if m else False
    add_result(f"B. Test-NetConnection localhost:{port}", "PASS" if ok else "FAIL",
               f"TcpTestSucceeded={m.group(1) if m else 'UNKNOWN'}", r6["raw"])

try:
    r7 = requests.get("http://localhost:5558/health", timeout=10)
    raw7 = r7.text
    add_result("B. localhost:5558/health", "PASS" if r7.status_code == 200 else "FAIL",
               f"status_code={r7.status_code}", raw7)
except Exception as e:
    add_result("B. localhost:5558/health", "FAIL", str(e), str(e))

try:
    r8 = requests.get("http://localhost:5558/latest_bars?instrument=XAUUSD&tf=M15&n=10", timeout=10)
    raw8 = r8.text
    add_result("B. localhost:5558/latest_bars", "PASS" if r8.status_code == 200 else "FAIL",
               f"status_code={r8.status_code}", raw8)
except Exception as e:
    add_result("B. localhost:5558/latest_bars", "FAIL", str(e), str(e))

try:
    r9 = requests.get("http://localhost:5558/account_state", timeout=10)
    raw9 = r9.text
    add_result("B. localhost:5558/account_state", "PASS" if r9.status_code == 200 else "FAIL",
               f"status_code={r9.status_code}", raw9)
except Exception as e:
    add_result("B. localhost:5558/account_state", "FAIL", str(e), str(e))

# =============================
# C. BACKTESTER
# =============================
section("C. BACKTESTER")

raw_bt = ""
status_bt = "FAIL"
detail_bt = ""
parsed_bt = None
try:
    rbt = requests.post("http://localhost:5560/backtest", json={
        "strategy_id": "qa_smoke_fvg_fill",
        "name": "QA Smoke FVG Fill",
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "session_filter": [],
        "entry_logic": {"type": "fvg_fill"},
        "sl_logic": {"type": "fixed", "value": 15.0},
        "tp_logic": {"type": "fixed", "value": 30.0},
        "risk_pct": 1.0,
        "max_trades_per_day": 1,
        "spread_gate_pips": 25,
        "date_from": "2025-01-01",
        "date_to": "2026-01-01",
    }, timeout=60)
    raw_bt = rbt.text
    detail_bt = f"status_code={rbt.status_code}"
    if rbt.status_code == 200:
        parsed_bt = rbt.json()
        detail_bt += f" total_trades={parsed_bt.get('total_trades')} win_rate={parsed_bt.get('win_rate')} expectancy_r={parsed_bt.get('expectancy_r')} max_drawdown_pct={parsed_bt.get('max_drawdown_pct')}"
        status_bt = "PASS" if parsed_bt.get("total_trades") not in (None, 0) else "FAIL"
    else:
        status_bt = "FAIL"
except Exception as e:
    raw_bt = str(e)
    status_bt = "FAIL"
    detail_bt = str(e)
add_result("C. backtest /backtest", status_bt, detail_bt, raw_bt)

# =============================
# D. RISK GATEKEEPER + PAPER TRADER
# =============================
section("D. RISK/PAPER")

reject_signal = {
    "signal_id": "qa_reject_rule4",
    "timestamp": int(time.time()),
    "instrument": "XAUUSD",
    "direction": "long",
    "entry_price": 2000.0,
    "entry_type": "market",
    "sl": 1999.0,
    "tp": 2100.0,
    "lots": 50.0,
    "timeframe": "M5",
    "strategy_id": "qa_strat",
    "setup_type": "smoke",
    "session": "london",
    "mode": "paper",
    "r_ratio": 3.0,
    "confidence": "high",
    "agent_notes": "Rule 4 oversized risk smoke",
    "status": "pending",
}
status11 = "FAIL"
raw11 = ""
detail11 = ""
try:
    r11 = requests.post("http://localhost:5563/signal", json=reject_signal, timeout=20)
    raw11 = r11.text
    detail11 = f"status_code={r11.status_code}"
    j = r11.json()
    detail11 += f" reason={j.get('reason')}"
    status11 = "PASS" if "Rule 4" in (j.get("reason") or "") else "FAIL"
except Exception as e:
    raw11 = str(e)
    detail11 = str(e)
    status11 = "FAIL"
add_result("D. reject oversized risk Rule 4", status11, detail11, raw11)

valid_signal = {
    "signal_id": "qa_valid_signal_1",
    "timestamp": int(time.time()),
    "instrument": "XAUUSD",
    "direction": "long",
    "entry_price": 2000.0,
    "entry_type": "market",
    "sl": 1990.0,
    "tp": 2030.0,
    "lots": 0.1,
    "timeframe": "M5",
    "strategy_id": "qa_strat",
    "setup_type": "smoke",
    "session": "london",
    "mode": "paper",
    "r_ratio": 3.0,
    "confidence": "high",
    "agent_notes": "valid smoke",
    "status": "pending",
}
status12 = "FAIL"
raw12 = ""
detail12 = ""
trade_risk = None
parsed12 = None
try:
    r12 = requests.post("http://localhost:5563/signal", json=valid_signal, timeout=20)
    raw12 = r12.text
    detail12 = f"status_code={r12.status_code}"
    parsed12 = r12.json()
    st = parsed12.get("status")
    detail12 += f" status={st}"
    status12 = "PASS" if st == "approved" else "FAIL"
    trade_risk = abs(valid_signal["entry_price"] - valid_signal["sl"]) * valid_signal["lots"]
    detail12 += f" trade_risk={trade_risk}"
except Exception as e:
    raw12 = str(e)
    detail12 = str(e)
    status12 = "FAIL"
add_result("D. valid signal approval", status12, detail12, raw12)

status13 = "FAIL"
raw13 = ""
detail13 = ""
try:
    r13 = requests.post("http://localhost:5563/signal", json=valid_signal, timeout=20)
    raw13 = r13.text
    detail13 = f"status_code={r13.status_code}"
    j13 = r13.json()
    detail13 += f" status={j13.get('status')}"
    status13 = "PASS" if j13.get("status") == "duplicate" else "FAIL"
except Exception as e:
    raw13 = str(e)
    detail13 = str(e)
    status13 = "FAIL"
add_result("D. duplicate signal idempotency", status13, detail13, raw13)

status14 = "FAIL"
raw14 = ""
detail14 = ""
pos_id = (parsed12 or {}).get("position_id") or (parsed12 or {}).get("signal", {}).get("signal_id") if parsed12 else None
if pos_id:
    try:
        r14 = requests.post(f"http://localhost:5561/close/{pos_id}", timeout=20)
        raw14 = r14.text
        detail14 = f"status_code={r14.status_code} position_id={pos_id}"
        j14 = r14.json()
        detail14 += f" close_status={j14.get('status')}"
        status14 = "PASS" if j14.get("status") in ("closed", "already_closed") else "FAIL"
    except Exception as e:
        raw14 = str(e)
        detail14 = str(e)
        status14 = "FAIL"
else:
    raw14 = "No position_id available from approved signal"
    detail14 = raw14
    status14 = "FAIL"
add_result("D. close position", status14, detail14, raw14)

# =============================
# E. KILL SWITCH
# =============================
section("E. KILL SWITCH")

status15 = "FAIL"
raw15 = ""
detail15 = ""
try:
    r15 = requests.post("http://localhost:5563/kill?flatten=true", timeout=20)
    raw15 = r15.text
    detail15 = f"status_code={r15.status_code}"
    j15 = r15.json()
    detail15 += f" kill_switch_active={j15.get('kill_switch_active')} status={j15.get('status')}"
    status15 = "PASS" if j15.get("kill_switch_active") is True else "FAIL"
except Exception as e:
    raw15 = str(e)
    detail15 = str(e)
    status15 = "FAIL"
add_result("E. kill?flatten=true", status15, detail15, raw15)

post_kill_signal = {
    "signal_id": "qa_post_kill_1",
    "timestamp": int(time.time()),
    "instrument": "XAUUSD",
    "direction": "long",
    "entry_price": 2000.0,
    "entry_type": "market",
    "sl": 1990.0,
    "tp": 2030.0,
    "lots": 0.01,
    "timeframe": "M5",
    "strategy_id": "qa_strat",
    "setup_type": "smoke",
    "session": "london",
    "mode": "paper",
    "r_ratio": 3.0,
    "confidence": "high",
    "agent_notes": "post kill smoke",
    "status": "pending",
}
status16 = "FAIL"
raw16 = ""
detail16 = ""
try:
    r16 = requests.post("http://localhost:5563/signal", json=post_kill_signal, timeout=20)
    raw16 = r16.text
    detail16 = f"status_code={r16.status_code}"
    j16 = r16.json()
    detail16 += f" status={j16.get('status')} reason={j16.get('reason')}"
    status16 = "PASS" if j16.get("status") == "rejected" and "kill switch" in (j16.get("reason") or "").lower() else "FAIL"
except Exception as e:
    raw16 = str(e)
    detail16 = str(e)
    status16 = "FAIL"
add_result("E. new signal while killed", status16, detail16, raw16)

status17 = "FAIL"
raw17 = ""
detail17 = ""
try:
    r17 = requests.post("http://localhost:5563/resume", timeout=20)
    raw17 = r17.text
    detail17 = f"status_code={r17.status_code}"
    j17 = r17.json()
    detail17 += f" kill_switch_active={j17.get('kill_switch_active')} status={j17.get('status')}"
    status17 = "PASS" if j17.get("kill_switch_active") is False else "FAIL"
except Exception as e:
    raw17 = str(e)
    detail17 = str(e)
    status17 = "FAIL"
add_result("E. resume", status17, detail17, raw17)

post_resume_signal = {
    "signal_id": "qa_post_resume_1",
    "timestamp": int(time.time()),
    "instrument": "XAUUSD",
    "direction": "long",
    "entry_price": 2000.0,
    "entry_type": "market",
    "sl": 1990.0,
    "tp": 2030.0,
    "lots": 0.01,
    "timeframe": "M5",
    "strategy_id": "qa_strat",
    "setup_type": "smoke",
    "session": "london",
    "mode": "paper",
    "r_ratio": 3.0,
    "confidence": "high",
    "agent_notes": "post resume smoke",
    "status": "pending",
}
status18 = "FAIL"
raw18 = ""
detail18 = ""
try:
    r18 = requests.post("http://localhost:5563/signal", json=post_resume_signal, timeout=20)
    raw18 = r18.text
    detail18 = f"status_code={r18.status_code}"
    j18 = r18.json()
    detail18 += f" status={j18.get('status')}"
    status18 = "PASS" if j18.get("status") == "approved" else "FAIL"
except Exception as e:
    raw18 = str(e)
    detail18 = str(e)
    status18 = "FAIL"
add_result("E. submit post-resume signal", status18, detail18, raw18)

# =============================
# F. FILE EXISTENCE
# =============================
section("F. FILE EXISTENCE")
paths = {
    "HermesStructure.mq5": ROOT / "ea" / "HermesStructure.mq5",
    "HermesSignals.mq5": ROOT / "ea" / "HermesSignals.mq5",
    "builtin.py": ROOT / "services" / "backtester" / "strategies" / "builtin.py",
    "strategy_loader.py": ROOT / "services" / "backtester" / "strategy_loader.py",
    "parse_ea_reports.py": ROOT / "scripts" / "parse_ea_reports.py",
    "obsidian_vault": ROOT.parent / "AppData" / "Local" / "hermes" / "obsidian",
}
for name, p in paths.items():
    st = "PASS" if p.exists() else "FAIL"
    detail = f"exists={p.exists()} path={p}"
    add_result(f"F. Test-Path {name}", st, detail, str(p))

# =============================
# G. HERMES HOME DIR + DASHBOARD
# =============================
section("G. HERMES HOME + DASHBOARD")

hermes_home = Path(r"C:\Users\user\.hermes")
add_result("G. hermes_home C:\\Users\\user\\.hermes exists", "PASS" if hermes_home.exists() else "FAIL",
           f"exists={hermes_home.exists()}", str(hermes_home))

junction = Path(r"C:\Users\user\AppData\Local\hermes\.Hermes")
status_junction = "FAIL"
raw_junction = ""
try:
    out = subprocess.check_output(
        f'powershell -NoProfile -Command "Get-Item -LiteralPath \'{junction}\' | Select-Object LinkType, Target | ConvertTo-Json -Compress"',
        shell=True, text=True, timeout=15
    ).strip()
    raw_junction = out
    status_junction = "PASS" if "Junction" in out or "SymbolicLink" in out else "FAIL"
except Exception as e:
    raw_junction = str(e)
    status_junction = "FAIL"
add_result("G. AppData .Hermes junction/symlink", status_junction, f"status={status_junction}", raw_junction)

r_dash = _sh('docker ps --filter "name=hermes_dashboard" --format "table {{.Names}}\t{{.Status}}"')
add_result("G. dashboard container ps", "PASS" if r_dash["returncode"] == 0 else "FAIL", "container status", r_dash["raw"])

r_logs = _sh('docker logs hermes_dashboard --tail 50')
add_result("G. dashboard logs tail 50", "PASS" if r_dash["returncode"] == 0 else "FAIL", "recent container logs", r_logs["raw"])

# =============================
# WRITE REPORT
# =============================
section("REPORT WRITE")
passed = sum(1 for r in results if r["status"] == "PASS")
failed = sum(1 for r in results if r["status"] == "FAIL")
now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
report_path = REPORTS_DIR / f"qa_report_{now}.md"

lines = []
lines.append("# QA Report")
lines.append("")
lines.append(f"- generated_utc: `{datetime.utcnow().isoformat()}Z`")
lines.append(f"- total_checks: `{len(results)}`")
lines.append(f"- passed: `{passed}`")
lines.append(f"- failed: `{failed}`")
lines.append("")
lines.append("| # | Check | Status | Detail | Raw Output |")
lines.append("| --- | --- | --- | --- | --- |")
for idx, r in enumerate(results, 1):
    safe_raw = r["raw"].replace("|", "\\|").replace("\n", " ")
    safe_detail = r["detail"].replace("|", "\\|").replace("\n", " ")
    lines.append(f"| {idx} | {r['check']} | {r['status']} | {safe_detail} | {safe_raw} |")
lines.append("")

report_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote report: {report_path}")
print(f"Passed: {passed} | Failed: {failed}")
