import os, json, requests, redis
from flask import Blueprint, request, Response, jsonify

chat_bp = Blueprint('chat', __name__)

HERMES_RPC_URL = os.getenv("HERMES_RPC_URL", "http://host.docker.internal:7778")
OLLAMA_URL     = os.getenv("OLLAMA_URL",      "http://host.docker.internal:11434")
REDIS_URL      = os.getenv("REDIS_URL",       "redis://redis:6379")
# LLM fallback chain: hermes_rpc (Nous→Gemini→Ollama) → direct Nous → direct Ollama
NOUS_API_KEY   = os.getenv("NOUS_API_KEY", "")
NOUS_MODEL     = os.getenv("NOUS_MODEL", "stepfun/step-3.7-flash:free")
NOUS_BASE_URL  = "https://inference-api.nousresearch.com/v1"

SYSTEM_PROMPT = """You are Hermes, an autonomous SMC/ICT trading agent for XAUUSD and BTCUSD.
Use Smart Money Concepts: BOS, CHoCH, Order Blocks, FVGs, liquidity sweeps.
Be precise with price levels. Max 1% risk per trade. Staged trust: hypothesis->backtest->paper->live.
CRITICAL INSTRUCTION: You MUST use tools to fetch real prices before answering ANY market or price-related questions. 
Do NOT guess or use your training data for current prices.
To use a tool, you must output exactly this format and wait for the response:
[TOOL: read_market_bars] {"instrument": "XAUUSD", "timeframe": "M15", "n": 1} [/TOOL]"""


def _discover_model():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.ok:
            models = [m["name"] for m in r.json().get("models", [])]
            for kw in ["hermes", "llama3.1", "llama3", "mistral", "qwen"]:
                for m in models:
                    if kw in m.lower():
                        return m
            if models: return models[0]
    except Exception:
        pass
    return "hermes3:latest"


def _save_history(role, content):
    try:
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        r.rpush("chat_history", json.dumps({"role": role, "content": content}))
        r.ltrim("chat_history", -50, -1)
    except Exception:
        pass


def _stream_rpc(message, history):
    """Primary path: stream through hermes_rpc (has tool-calling)."""
    try:
        r = requests.post(f"{HERMES_RPC_URL}/chat",
                          json={"message": message, "task_type": "analysis",
                                "context": {"history": history[-10:]}},
                          stream=True, timeout=180)
        if r.status_code != 200:
            yield f"data: {json.dumps({'type': 'token', 'content': f'RPC error {r.status_code}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'content': ''})}\n\n"
            return
        accumulated = ""
        for line in r.iter_lines():
            if not line: continue
            decoded = line.decode("utf-8") if isinstance(line, bytes) else line
            if decoded.startswith("data:"): decoded = decoded[5:].strip()
            try:
                obj = json.loads(decoded)
                if obj.get("type") == "token" and obj.get("content"):
                    accumulated += obj["content"]
                yield f"data: {json.dumps(obj)}\n\n"
                if obj.get("type") == "done": break
            except json.JSONDecodeError:
                if decoded and decoded != "[DONE]":
                    accumulated += decoded
                    yield f"data: {json.dumps({'type':'token','content':decoded})}\n\n"
        if accumulated.strip(): _save_history("assistant", accumulated)
        yield f"data: {json.dumps({'type':'done','content':''})}\n\n"
    except requests.exceptions.ConnectionError:
        yield from _stream_nous_direct(message, history)
    except Exception as e:
        yield f"data: {json.dumps({'type':'token','content':f'Error: {e}'})}\n\n"
        yield f"data: {json.dumps({'type':'done','content':''})}\n\n"


def _stream_nous_direct(message, history):
    """Tier-2 fallback: direct Nous Portal call when hermes_rpc is unavailable."""
    if not NOUS_API_KEY:
        yield from _stream_ollama_direct(message, history)
        return

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-10:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": message})

    try:
        r = requests.post(
            f"{NOUS_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {NOUS_API_KEY}", "Content-Type": "application/json"},
            json={"model": NOUS_MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        if r.status_code == 200:
            text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if text:
                _save_history("assistant", text)
                yield f"data: {json.dumps({'type':'token','content':text})}\n\n"
                yield f"data: {json.dumps({'type':'done','content':''})}\n\n"
                return
    except Exception:
        pass
    # Nous failed — fall through to Ollama
    yield from _stream_ollama_direct(message, history)


def _stream_ollama_direct(message, history):
    """Fallback: direct Ollama call when hermes_rpc is unavailable."""
    model = _discover_model()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-10:]:
        messages.append({"role": h.get("role","user"), "content": h.get("content","")})
    messages.append({"role": "user", "content": message})
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat",
                          json={"model": model, "messages": messages, "stream": True},
                          stream=True, timeout=180)
        if not r.ok:
            yield f"data: {json.dumps({'type':'token','content':f'Ollama {r.status_code}: {r.text[:200]}'})}\n\n"
            yield f"data: {json.dumps({'type':'done','content':''})}\n\n"
            return
        accumulated = ""
        for line in r.iter_lines():
            if not line: continue
            try:
                obj = json.loads(line)
                token = obj.get("message", {}).get("content", "")
                if token:
                    accumulated += token
                    yield f"data: {json.dumps({'type':'token','content':token})}\n\n"
                if obj.get("done"): break
            except json.JSONDecodeError:
                pass
        if accumulated.strip(): _save_history("assistant", accumulated)
        yield f"data: {json.dumps({'type':'done','content':''})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type':'token','content':f'Ollama unreachable: {e}'})}\n\n"
        yield f"data: {json.dumps({'type':'done','content':''})}\n\n"


@chat_bp.route('/send', methods=['POST'])
def send_message():
    data    = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message: return jsonify({"error": "No message"}), 400
    _save_history("user", message)
    history = []
    try:
        rc = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        history = [json.loads(h) for h in rc.lrange("chat_history", 0, -1)]
    except Exception: pass
    return Response(_stream_rpc(message, history), mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})


@chat_bp.route('/history', methods=['GET'])
def get_history():
    try:
        rc = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        return jsonify([json.loads(h) for h in rc.lrange("chat_history", 0, -1)])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/models', methods=['GET'])
def get_models():
    ollama_models = []
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.ok:
            ollama_models = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return jsonify({
        "llm_chain": ["hermes_rpc (Nous→Gemini→Ollama)", "direct-Nous", "direct-Ollama"],
        "active_model": NOUS_MODEL if NOUS_API_KEY else _discover_model(),
        "nous": {"model": NOUS_MODEL, "configured": bool(NOUS_API_KEY)},
        "ollama": {"models": ollama_models, "selected": _discover_model()},
    })
