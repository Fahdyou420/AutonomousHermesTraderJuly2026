import os
import json
import requests
import redis
from flask import Blueprint, request, Response, jsonify

trades_bp = Blueprint('trades', __name__)

PAPER_TRADER_URL = os.getenv("PAPER_TRADER_URL", "http://paper_trader:5561")
MT5_BRIDGE_URL    = os.getenv("MT5_BRIDGE_URL", "http://mt5_bridge:5558")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
TRADES_DATA_DIR = os.getenv("TRADES_DATA_DIR", "/data/trades")

# Auto-ensure directories exist
os.makedirs(TRADES_DATA_DIR, exist_ok=True)

def read_last_lines_jsonl(filepath, limit=50):
    if not os.path.exists(filepath):
        return []
        
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        take_lines = lines[-limit:] if len(lines) > limit else lines
        for line in take_lines:
            line_str = line.strip()
            if line_str:
                try:
                    records.append(json.loads(line_str))
                except Exception:
                    pass
    except Exception as e:
        print(f"Failed parsing jsonl log {filepath}: {e}")
        
    # Return reverse list (most recent first)
    records.reverse()
    return records


@trades_bp.route('/positions', methods=['GET'])
def get_positions():
    """Returns paper trades AND real MT5 positions, tagged by source."""
    combined = []
    try:
        res = requests.get(f"{PAPER_TRADER_URL}/positions", timeout=5)
        paper = res.json() if res.ok else []
        for p in paper:
            p["source"] = "paper"
        combined.extend(paper)
    except Exception as e:
        print(f"Paper Trader offline: {e}")

    try:
        res = requests.get(f"{MT5_BRIDGE_URL}/positions", timeout=5)
        live = res.json() if res.ok else []
        for p in live:
            p["source"] = "mt5_live"
        combined.extend(live)
    except Exception as e:
        print(f"MT5 bridge positions unavailable: {e}")

    return jsonify(combined)

@trades_bp.route('/account', methods=['GET'])
def get_account():
    """Real MT5 account state: balance, equity, margin, profit."""
    try:
        res = requests.get(f"{MT5_BRIDGE_URL}/account_state", timeout=5)
        return jsonify(res.json() if res.ok else {})
    except Exception as e:
        print(f"MT5 bridge account_state unavailable: {e}")
        return jsonify({"balance": 0, "equity": 0, "margin": 0, "profit": 0})

@trades_bp.route('/history', methods=['GET'])
def get_history():
    try:
        url = f"{PAPER_TRADER_URL}/history"
        res = requests.get(url, timeout=10)
        return jsonify(res.json())
    except Exception as e:
        print(f"Paper Trader offline: {e}")
        return jsonify([])

@trades_bp.route('/stats', methods=['GET'])
def get_stats():
    stats = {
        "balance": 0.0, "equity": 0.0, "win_rate": 0.0,
        "total_trades": 0, "profit_factor": 0.0,
        "max_drawdown_percent": 0.0, "net_profit": 0.0, "net_r": 0.0
    }
    try:
        res = requests.get(f"{PAPER_TRADER_URL}/stats", timeout=10)
        if res.ok:
            stats.update(res.json())
    except Exception as e:
        print(f"Paper Trader offline: {e}")

    # Overlay real account balance/equity from MT5 — this is what actually matters
    try:
        res = requests.get(f"{MT5_BRIDGE_URL}/account_state", timeout=5)
        if res.ok:
            acc = res.json()
            if acc.get("balance"):
                stats["balance"] = acc["balance"]
            if acc.get("equity"):
                stats["equity"] = acc["equity"]
    except Exception as e:
        print(f"MT5 bridge account_state unavailable: {e}")

    return jsonify(stats)

@trades_bp.route('/signals/approved', methods=['GET'])
def get_approved_signals():
    filepath = os.path.join(TRADES_DATA_DIR, "approved_signals.jsonl")
    records = read_last_lines_jsonl(filepath, limit=50)
    return jsonify(records)

@trades_bp.route('/signals/rejected', methods=['GET'])
def get_rejected_signals():
    filepath = os.path.join(TRADES_DATA_DIR, "rejected_signals.jsonl")
    records = read_last_lines_jsonl(filepath, limit=50)
    return jsonify(records)

@trades_bp.route('/candidates', methods=['GET'])
def get_candidates():
    try:
        url = f"{PAPER_TRADER_URL}/promotion_candidates"
        res = requests.get(url, timeout=10)
        return jsonify(res.json())
    except Exception as e:
        print(f"Paper Trader offline: {e}")
        return jsonify([])


EXECUTION_URL = os.getenv("EXECUTION_URL", "http://execution:5563")

@trades_bp.route('/kill', methods=['POST'])
def trigger_kill():
    flatten = request.args.get('flatten', 'false').lower() == 'true'
    try:
        res = requests.post(f"{EXECUTION_URL}/kill?flatten={str(flatten).lower()}", timeout=10)
        return jsonify(res.json() if res.ok else {"error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@trades_bp.route('/resume', methods=['POST'])
def trigger_resume():
    try:
        res = requests.post(f"{EXECUTION_URL}/resume", timeout=10)
        return jsonify(res.json() if res.ok else {"error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@trades_bp.route('/reset', methods=['POST'])
def trigger_reset():
    try:
        res = requests.post(f"{PAPER_TRADER_URL}/reset", timeout=10)
        return jsonify(res.json() if res.ok else {"error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@trades_bp.route('/pending', methods=['GET'])
def get_pending_signals():
    try:
        res = requests.get(f"{EXECUTION_URL}/pending_signals", timeout=10)
        return jsonify(res.json() if res.ok else []), res.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@trades_bp.route('/pending/<signal_id>/approve', methods=['POST'])
def approve_signal(signal_id):
    try:
        res = requests.post(f"{EXECUTION_URL}/signal/{signal_id}/approve", timeout=15)
        return jsonify(res.json() if res.ok else {"error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@trades_bp.route('/pending/<signal_id>/reject', methods=['POST'])
def reject_signal(signal_id):
    try:
        res = requests.post(f"{EXECUTION_URL}/signal/{signal_id}/reject", timeout=15)
        return jsonify(res.json() if res.ok else {"error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@trades_bp.route('/stream', methods=['GET'])
def stream_trades():
    def event_generator():
        # Redis Pub-Sub Listener Channel Integration
        pubsub = None
        try:
            r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            pubsub = r.pubsub()
            pubsub.subscribe("PAPER_TRADE_UPDATE", "TRADE_OPENED", "TRADE_CLOSED")
            
            # Send initial subscription status token
            yield f"data: {json.dumps({'event': 'connected', 'message': 'Subscribed to Hermes trade event broker'})}\n\n"
            
            # Non-blocking listen check
            for message in pubsub.listen():
                if message and message['type'] == 'message':
                    channel_name = message['channel']
                    payload = message['data']
                    
                    try:
                        parsed_data = json.loads(payload)
                        wrapped_payload = {
                            "event": channel_name,
                            "data": parsed_data
                        }
                        yield f"data: {json.dumps(wrapped_payload)}\n\n"
                    except Exception:
                        wrapped_payload = {
                            "event": channel_name,
                            "data": payload
                        }
                        yield f"data: {json.dumps(wrapped_payload)}\n\n"
                        
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': f'Redis pubsub exception: {str(e)}'})}\n\n"
        finally:
            if pubsub:
                try:
                    pubsub.unsubscribe()
                except Exception:
                    pass
                    
    return Response(event_generator(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })
