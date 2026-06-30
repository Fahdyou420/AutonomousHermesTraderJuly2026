import os
import uuid
import time
import json
from flask import Blueprint, request, jsonify

rnd_bp = Blueprint('rnd', __name__)

RND_DATA_DIR = os.getenv("RND_DATA_DIR", "/data/rnd")
QUEUE_FILEPATH = os.path.join(RND_DATA_DIR, "queue.json")
RESULTS_DIR = os.path.join(RND_DATA_DIR, "results")

# Ensure base folders exist
os.makedirs(RND_DATA_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

def load_queue():
    if not os.path.exists(QUEUE_FILEPATH):
        return []
    try:
        with open(QUEUE_FILEPATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed loading R&D Queue: {e}")
        return []


def save_queue(queue_data):
    try:
        with open(QUEUE_FILEPATH, 'w', encoding='utf-8') as f:
            json.dump(queue_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed saving R&D Queue: {e}")
        return False


@rnd_bp.route('/queue', methods=['GET'])
def get_queue():
    queue = load_queue()
    return jsonify(queue)


@rnd_bp.route('/add', methods=['POST'])
def add_to_queue():
    data = request.get_json() or {}
    hypothesis = data.get("hypothesis", "").strip()
    
    if not hypothesis:
        return jsonify({"error": "Hypothesis string is required."}), 400
        
    queue = load_queue()
    new_item = {
        "id": f"rnd_hyp_{str(uuid.uuid4())[:8]}",
        "hypothesis": hypothesis,
        "status": "pending",
        "timestamp": int(time.time())
    }
    
    queue.append(new_item)
    if save_queue(queue):
        return jsonify(new_item), 201
    return jsonify({"error": "Failed to store hypothesis item to queue."}), 500


@rnd_bp.route('/results', methods=['GET'])
def get_results():
    results = []
    try:
        for root, dirs, files in os.walk(RESULTS_DIR):
            for file in files:
                if file.endswith('.json') or file.endswith('.md'):
                    filepath = os.path.join(root, file)
                    mtime = os.path.getmtime(filepath)
                    results.append({
                        "id": os.path.splitext(file)[0],
                        "filename": file,
                        "last_modified": mtime
                    })
                    
        results.sort(key=lambda x: x["last_modified"], reverse=True)
    except Exception as e:
        return jsonify({"error": f"Failed compiling R&D achievements: {str(e)}"}), 500
        
    return jsonify(results)


@rnd_bp.route('/result/<result_id>', methods=['GET'])
@rnd_bp.route('/result', methods=['GET'])
def get_result_detail(result_id=None):
    if not result_id:
        result_id = request.args.get('id', '').strip()
        
    if not result_id:
        return jsonify({"error": "Result ID is required."}), 400
        
    target_json = os.path.join(RESULTS_DIR, f"{result_id}.json")
    target_md = os.path.join(RESULTS_DIR, f"{result_id}.md")
    
    try:
        if os.path.exists(target_json) and os.path.isfile(target_json):
            with open(target_json, 'r', encoding='utf-8') as f:
                content = json.load(f)
            return jsonify({
                "id": result_id,
                "type": "json",
                "content": content
            })
        elif os.path.exists(target_md) and os.path.isfile(target_md):
            with open(target_md, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({
                "id": result_id,
                "type": "markdown",
                "content": content
            })
        else:
            # Check custom filenames without strict standard extension
            all_files = os.listdir(RESULTS_DIR)
            for f in all_files:
                if os.path.splitext(f)[0] == result_id:
                    full_p = os.path.join(RESULTS_DIR, f)
                    if f.endswith('.json'):
                        with open(full_p, 'r', encoding='utf-8') as fh:
                            return jsonify({"id": result_id, "type": "json", "content": json.load(fh)})
                    else:
                        with open(full_p, 'r', encoding='utf-8') as fh:
                            return jsonify({"id": result_id, "type": "text", "content": fh.read()})
                            
            return jsonify({"error": f"Research result {result_id} not found."}), 404
            
    except Exception as e:
        return jsonify({"error": f"Failed reading result record: {str(e)}"}), 500
