import os
import sys
import json
import requests
import redis as redis_lib
from flask import Flask, Response, redirect, jsonify, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv(override=True)  # override=True ensures .env wins over stale system/user env vars

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routes.chat import chat_bp
from routes.vault import vault_bp
from routes.strategy import strategy_bp
from routes.trades import trades_bp
from routes.rnd import rnd_bp

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app, resources={r"/*": {"origins": "*"}})

app.register_blueprint(chat_bp, url_prefix='/api/chat')
app.register_blueprint(vault_bp, url_prefix='/api/vault')
app.register_blueprint(strategy_bp, url_prefix='/api/strategy')
app.register_blueprint(trades_bp, url_prefix='/api/trades')
app.register_blueprint(rnd_bp, url_prefix='/api/rnd')

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MT5_BRIDGE_URL = os.getenv("MT5_BRIDGE_URL", "http://mt5_bridge:5558")
PREPROCESSOR_URL = os.getenv("PREPROCESSOR_URL", "http://preprocessor:5559")
PAPER_TRADER_URL = os.getenv("PAPER_TRADER_URL", "http://paper_trader:5561")
HERMES_RPC_URL = os.getenv("HERMES_RPC_URL", "http://host.docker.internal:7778")
CHROMADB_URL = os.getenv("CHROMADB_URL", "http://chromadb:8000")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")


def _get(url: str, timeout: int = 5):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "hermes-dashboard"}), 200


@app.route('/api/status', methods=['GET'])
def system_status():
    """Real service health checks for all components."""
    def check(url, timeout=2):
        try:
            r = requests.get(url, timeout=timeout)
            return r.status_code == 200
        except Exception:
            return False

    ollama_ok = check(f"{OLLAMA_URL}/api/tags")
    rpc_ok = check(f"{HERMES_RPC_URL}/health")

    # mt5_ok reflects real EA connectivity (last ZMQ message received recently),
    # not just whether the mt5_bridge container/web server is up.
    mt5_ok = False
    try:
        r = requests.get(f"{MT5_BRIDGE_URL}/health", timeout=2)
        if r.status_code == 200:
            mt5_ok = bool(r.json().get("ea_connected", False))
    except Exception:
        pass

    redis_ok = False
    try:
        r = redis_lib.Redis.from_url(REDIS_URL, socket_connect_timeout=2)
        r.ping()
        redis_ok = True
        r.close()
    except Exception:
        pass
    chroma_ok = check(f"{CHROMADB_URL}/api/v1/heartbeat") or check(f"{CHROMADB_URL}/api/v2/auth")
    obsidian_ok = os.path.exists("/data/obsidian")

    status = lambda ok: "connected" if ok else "disconnected"
    mt5_status = status(mt5_ok)

    return jsonify({
        "ollama": status(ollama_ok),
        "hermesRpc": status(rpc_ok),
        "mt5Zmq": {"data": mt5_status, "draw": mt5_status, "order": mt5_status},
        "redis": status(redis_ok),
        "chromaDb": status(chroma_ok),
        "obsidian": status(obsidian_ok)
    })


@app.route('/api/market/price', methods=['GET'])
def get_market_price():
    """Live price from MT5 bridge."""
    data = _get(f"{MT5_BRIDGE_URL}/latest_bars?instrument=XAUUSD&tf=M15&n=1", timeout=5)
    if data and isinstance(data, list) and len(data) > 0:
        return jsonify({"price": data[-1].get("close", 0.0)})
    return jsonify({"price": 0.0})


@app.route('/api/errors', methods=['GET'])
def get_errors():
    """Return recent errors from the centralized Redis error bus."""
    try:
        from services.shared.error_bus import get_recent_errors
        n = int(request.args.get('n', 100))
        return jsonify(get_recent_errors(n))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Template views
@app.route('/terminal')
def view_terminal():
    return render_template('terminal.html', active_page='terminal')

@app.route('/knowledge')
def view_knowledge():
    return render_template('knowledge.html', active_page='knowledge')

@app.route('/strategy')
def view_strategy():
    return render_template('strategy.html', active_page='strategy')

@app.route('/trades')
def view_trades():
    return render_template('trades.html', active_page='trades')

@app.route('/rnd')
def view_rnd():
    return render_template('rnd.html', active_page='rnd')

@app.route('/logs')
def view_logs():
    return render_template('logs.html', active_page='logs')

@app.route('/')
def home_redirect():
    return redirect('/terminal')

@app.route('/api/llm/status', methods=['GET'])
def llm_status():
    try:
        r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
        data = r.get("LLM_ACTIVE_STATUS")
        if data:
            return jsonify(json.loads(data))
    except Exception:
        pass
    return jsonify({"tier": "none", "model": "none"})

@app.route('/api/logs/stream', methods=['GET'])
def stream_system_logs():
    def event_generator():
        pubsub = None
        try:
            r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
            pubsub = r.pubsub()
            pubsub.subscribe("SYSTEM_LOGS")
            yield f"data: {json.dumps({'event': 'connected', 'message': 'SSE Log stream established'})}\n\n"
            for message in pubsub.listen():
                if message and message['type'] == 'message':
                    yield f"data: {message['data']}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
        finally:
            if pubsub:
                try: pubsub.unsubscribe()
                except: pass
    return Response(event_generator(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "detail": str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
