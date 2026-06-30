import os
import re
import yaml
from flask import Blueprint, request, jsonify

vault_bp = Blueprint('vault', __name__)

OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "/data/obsidian")

# Auto-ensure root paths and basic schema for development sanity
if not os.path.exists(OBSIDIAN_VAULT_PATH):
    try:
        os.makedirs(os.path.join(OBSIDIAN_VAULT_PATH, "01_MARKET_STUDIES/XAUUSD/M15"), exist_ok=True)
        os.makedirs(os.path.join(OBSIDIAN_VAULT_PATH, "02_STRATEGIES/XAUUSD"), exist_ok=True)
        os.makedirs(os.path.join(OBSIDIAN_VAULT_PATH, "03_TRADE_JOURNAL/weekly_reviews"), exist_ok=True)
        os.makedirs(os.path.join(OBSIDIAN_VAULT_PATH, "04_BACKTEST_REPORTS/XAUUSD"), exist_ok=True)
    except Exception as e:
        print(f"Failed to auto-setup mock Obsidian structure: {e}")


def safe_resolve_path(rel_path):
    """Safely resolves parent relative paths to prevent path traversal attacks"""
    cleaned_rel = rel_path.strip().lstrip('/').lstrip('\\')
    absolute_target = os.path.abspath(os.path.join(OBSIDIAN_VAULT_PATH, cleaned_rel))
    absolute_base = os.path.abspath(OBSIDIAN_VAULT_PATH)
    
    if os.path.commonpath([absolute_base, absolute_target]) == absolute_base:
        return absolute_target
    raise ValueError("Path traversal violation detected")


def parse_note(filepath, rel_path):
    """Parses a markdown note extracting any yaml frontmatter blocks"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        return {
            "path": rel_path,
            "title": os.path.basename(filepath),
            "content": f"Error reading note: {str(e)}",
            "frontmatter": {}
        }
        
    frontmatter = {}
    content = text
    
    # Matches markdown triple-dash yaml headers
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if match:
        fm_text = match.group(1)
        content = text[match.end():]
        try:
            frontmatter = yaml.safe_load(fm_text) or {}
        except Exception:
            # Simple manual fallback parsing if pyyaml chokes
            for line in fm_text.split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    frontmatter[k.strip()] = v.strip().strip('"').strip("'")
                    
    title = frontmatter.get('title') or frontmatter.get('name') or os.path.splitext(os.path.basename(filepath))[0]
    tags = frontmatter.get('tags', [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',')]
        
    return {
        "path": rel_path.replace("\\", "/"),
        "title": title,
        "content": content,
        "frontmatter": frontmatter,
        "tags": tags
    }


@vault_bp.route('/search', methods=['GET'])
def search_vault():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
        
    results = []
    query_lower = query.lower()
    
    try:
        for root, dirs, files in os.walk(OBSIDIAN_VAULT_PATH):
            for file in files:
                if file.endswith('.md'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, OBSIDIAN_VAULT_PATH)
                    
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        if query_lower in content.lower() or query_lower in file.lower():
                            note_data = parse_note(full_path, rel_path)
                            
                            # Build quick matching context excerpt
                            excerpt = ""
                            match_idx = content.lower().find(query_lower)
                            if match_idx != -1:
                                start = max(0, match_idx - 40)
                                end = min(len(content), match_idx + len(query) + 80)
                                excerpt = ("..." if start > 0 else "") + content[start:end].replace('\n', ' ') + ("..." if end < len(content) else "")
                            else:
                                excerpt = content[:150].replace('\n', ' ') + "..."
                                
                            results.append({
                                "path": note_data["path"],
                                "title": note_data["title"],
                                "excerpt": excerpt,
                                "tags": note_data["tags"]
                            })
                    except Exception:
                        continue
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500
        
    return jsonify(results)


@vault_bp.route('/note', methods=['GET'])
def get_note():
    rel_path = request.args.get('path', '').strip()
    if not rel_path:
        return jsonify({"error": "Path parameter is required"}), 400
        
    try:
        filepath = safe_resolve_path(rel_path)
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            return jsonify({"error": f"Note not found: {rel_path}"}), 404
            
        note_data = parse_note(filepath, rel_path)
        return jsonify(note_data)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@vault_bp.route('/tree', methods=['GET'])
def get_vault_tree():
    try:
        def build_tree(current_dir):
            entries = []
            try:
                for entry in sorted(os.listdir(current_dir)):
                    if entry.startswith('.') or entry == "node_modules":
                        continue
                    full_path = os.path.join(current_dir, entry)
                    rel_path = os.path.relpath(full_path, OBSIDIAN_VAULT_PATH).replace("\\", "/")
                    
                    if os.path.isdir(full_path):
                        entries.append({
                            "name": entry,
                            "type": "directory",
                            "path": rel_path,
                            "children": build_tree(full_path)
                        })
                    elif entry.endswith('.md'):
                        entries.append({
                            "name": entry,
                            "type": "file",
                            "path": rel_path
                        })
            except Exception:
                pass
            return entries

        tree = build_tree(OBSIDIAN_VAULT_PATH)
        return jsonify(tree)
    except Exception as e:
        return jsonify({"error": f"Failed to list tree structure: {str(e)}"}), 500


@vault_bp.route('/recent', methods=['GET'])
def get_recent_notes():
    recent_files = []
    try:
        for root, dirs, files in os.walk(OBSIDIAN_VAULT_PATH):
            for file in files:
                if file.endswith('.md'):
                    full_path = os.path.join(root, file)
                    mtime = os.path.getmtime(full_path)
                    rel_path = os.path.relpath(full_path, OBSIDIAN_VAULT_PATH)
                    recent_files.append((full_path, rel_path, mtime))
                    
        # Sort by modification time desc
        recent_files.sort(key=lambda x: x[2], reverse=True)
        take_files = recent_files[:20]
        
        results = []
        for path, rel, mtime in take_files:
            note_data = parse_note(path, rel)
            results.append({
                "path": note_data["path"],
                "title": note_data["title"],
                "tags": note_data["tags"],
                "last_modified": mtime
            })
            
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"Failed to extract recent notes: {str(e)}"}), 500
