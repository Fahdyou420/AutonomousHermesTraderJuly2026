import os
import re
import yaml
import json
import requests
from flask import Blueprint, request, Response, jsonify

strategy_bp = Blueprint('strategy', __name__)

OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "/data/obsidian")
BACKTESTER_URL = os.getenv("BACKTESTER_URL", "http://backtester:5560")

def load_all_strategy_files():
    strategies_dir = os.path.join(OBSIDIAN_VAULT_PATH, "02_STRATEGIES")
    os.makedirs(strategies_dir, exist_ok=True)
    
    strategy_files = []
    for root, dirs, files in os.walk(strategies_dir):
        for f in files:
            if f.endswith('.md'):
                strategy_files.append(os.path.join(root, f))
    return strategy_files


def parse_strategy_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        return None

    frontmatter = {}
    content = text
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if match:
        fm_text = match.group(1)
        content = text[match.end():]
        try:
            frontmatter = yaml.safe_load(fm_text) or {}
        except Exception:
            for line in fm_text.split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    frontmatter[k.strip()] = v.strip().strip('"').strip("'")
                    
    # Locate embedded JSON configs if available
    json_config = {}
    json_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if json_match:
        try:
            json_config = json.loads(json_match.group(1))
        except Exception:
            pass
            
    strat_id = frontmatter.get('id') or frontmatter.get('strategy_id') or os.path.splitext(os.path.basename(filepath))[0]
    return {
        "id": strat_id,
        "filepath": filepath,
        "name": frontmatter.get('name', os.path.splitext(os.path.basename(filepath))[0]),
        "status": frontmatter.get('status', 'hypothesis'),
        "instrument": frontmatter.get('instrument', 'XAUUSD'),
        "timeframe": frontmatter.get('timeframe', 'M15'),
        "date_created": frontmatter.get('date_created', ''),
        "frontmatter": frontmatter,
        "rules": json_config,
        "content": content
    }


@strategy_bp.route('/list', methods=['GET'])
def list_strategies():
    strategies = []
    try:
        strategy_files = load_all_strategy_files()
        for filepath in strategy_files:
            strat = parse_strategy_file(filepath)
            if strat:
                strategies.append({
                    "id": strat["id"],
                    "name": strat["name"],
                    "status": strat["status"],
                    "instrument": strat["instrument"],
                    "timeframe": strat["timeframe"],
                    "date_created": strat["date_created"],
                    "rules": strat["rules"],
                    "tags": strat["frontmatter"].get("tags", [])
                })
    except Exception as e:
        return jsonify({"error": f"Failed listing strategies: {str(e)}"}), 500
    return jsonify(strategies)


@strategy_bp.route('/<strategy_id>', methods=['GET'])
@strategy_bp.route('', methods=['GET'])
def get_strategy(strategy_id=None):
    # Support both /api/strategy/id and /api/strategy?id=id
    if not strategy_id:
        strategy_id = request.args.get('id', '').strip()
        
    if not strategy_id:
        return jsonify({"error": "Strategy ID is required"}), 400
        
    try:
        strategy_files = load_all_strategy_files()
        for filepath in strategy_files:
            strat = parse_strategy_file(filepath)
            if strat and (strat["id"] == strategy_id or os.path.splitext(os.path.basename(filepath))[0] == strategy_id):
                return jsonify(strat)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    return jsonify({"error": f"Strategy card not found for: {strategy_id}"}), 404


@strategy_bp.route('/backtest', methods=['POST'])
def run_strategy_backtest():
    config = request.get_json() or {}
    strategy_id = config.get("strategy_id", "unknown_strat")
    
    def live_stream():
        yield f"data: {json.dumps({'status': 'initializing', 'message': f'Initializing backtest setup for {strategy_id}', 'progress': 5})}\n\n"
        
        try:
            # POST request simulation to backtester container on port 5560
            url = f"{BACKTESTER_URL}/backtest"
            response = requests.post(url, json=config, stream=True, timeout=180)
            
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8').strip()
                    if decoded.startswith("data:"):
                        yield f"{decoded}\n\n"
                    else:
                        try:
                            # If it's a raw json, wrap it as progress or report chunk
                            parsed = json.loads(decoded)
                            yield f"data: {decoded}\n\n"
                        except json.JSONDecodeError:
                            yield f"data: {json.dumps({'status': 'running', 'message': decoded})}\n\n"
                            
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'Backtester service is offline or unreachable: {str(e)}', 'progress': 0})}\n\n"
        
        yield f"data: {json.dumps({'status': 'done', 'progress': 100})}\n\n"
        
    return Response(live_stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })


@strategy_bp.route('/promote', methods=['POST'])
def promote_strategy_phase():
    data = request.get_json() or {}
    strategy_id = data.get("strategy_id", "").strip()
    from_status = data.get("from_status", "").strip()
    to_status = data.get("to_status", "").strip()
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip() or data.get("confirmation_token", "").strip()
    
    if not strategy_id or not from_status or not to_status:
        return jsonify({"error": "Missing promotion properties (strategy_id, from_status, to_status)"}), 400
        
    if not token:
        return jsonify({"error": "Promotion requires an authoritative Confirmation Token."}), 400
        
    try:
        strategy_files = load_all_strategy_files()
        target_strat = None
        for filepath in strategy_files:
            strat = parse_strategy_file(filepath)
            if strat and strat["id"] == strategy_id:
                target_strat = strat
                break
                
        if not target_strat:
            return jsonify({"error": f"Strategy {strategy_id} not found."}), 404
            
        current_status = target_strat["status"]
        if current_status != from_status:
            return jsonify({"error": f"State mismatch. Expected current state '{from_status}', found '{current_status}'"}), 409
            
        # Perform frontmatter update in the markdown note
        filepath = target_strat["filepath"]
        
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
            
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
        if match:
            fm_text = match.group(1)
            content = text[match.end():]
            
            try:
                fm = yaml.safe_load(fm_text) or {}
            except Exception:
                # manual parsed fallback dictionary
                fm = {}
                for line in fm_text.split('\n'):
                    if ':' in line:
                        k, v = line.split(':', 1)
                        fm[k.strip()] = v.strip().strip('"').strip("'")
                        
            fm["status"] = to_status
            new_fm_text = yaml.safe_dump(fm, default_flow_style=False)
            new_text = f"---\n{new_fm_text}---\n{content}"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_text)
                
            return jsonify({
                "success": True,
                "strategy_id": strategy_id,
                "previous_status": from_status,
                "new_status": to_status,
                "message": f"Strategy {strategy_id} successfully promoted to '{to_status}'."
            })
        else:
            return jsonify({"error": "Note is missing structured frontmatter YAML blocks."}), 422
            
    except Exception as e:
        return jsonify({"error": f"Failed promoting strategy card: {str(e)}"}), 500
