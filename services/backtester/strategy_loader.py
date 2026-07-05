"""
Strategy Loader
================
Dynamically loads strategy plugins from:
  1. Built-in strategies (services/backtester/strategies/builtin.py)
  2. Agent-created strategies (/data/strategies/*.py)
     Written by Hermes Agent via the create_strategy MCP tool.

Usage:
    from services.backtester.strategy_loader import load_strategy, list_strategies

    strategy_cls = load_strategy("fvg_fill")
    instance     = strategy_cls()
    signal       = instance.find_signal(bars, i, smc, triggered_ids)
"""

import os
import sys
import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Dict, Type, Optional, List

from services.backtester.strategies.base import BaseStrategy
from services.backtester.strategies.builtin import BUILTIN_STRATEGIES

log = logging.getLogger("strategy_loader")

CUSTOM_STRATEGY_DIR = Path(os.getenv("STRATEGY_DIR", "/data/strategies"))

COMPAT_ALIASES = {
    "smc_ob_entry": "ob_reaction",
    "ob_entry": "ob_reaction",
    "smc_fvg_fill": "fvg_fill",
    "fvg": "fvg_fill",
    "smc_liquidity_sweep": "liquidity_sweep_reversal",
    "liquidity_sweep": "liquidity_sweep_reversal",
}


def _load_custom_strategies() -> Dict[str, Type[BaseStrategy]]:
    """Scan /data/strategies/*.py and import any BaseStrategy subclasses."""
    custom = {}
    if not CUSTOM_STRATEGY_DIR.exists():
        return custom

    for py_file in CUSTOM_STRATEGY_DIR.glob("*.py"):
        try:
            spec   = importlib.util.spec_from_file_location(py_file.stem, py_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (isinstance(obj, type)
                        and issubclass(obj, BaseStrategy)
                        and obj is not BaseStrategy
                        and hasattr(obj, "name")
                        and obj.name != "base"):
                    custom[obj.name] = obj
                    log.info(f"Loaded custom strategy: {obj.name} from {py_file.name}")
        except Exception as e:
            log.error(f"Failed to load strategy from {py_file.name}: {e}")

    return custom


def list_strategies() -> List[Dict]:
    """Return metadata for all available strategies (builtin + custom)."""
    all_strats = {**BUILTIN_STRATEGIES, **_load_custom_strategies()}
    result = []
    for name, cls in all_strats.items():
        result.append({
            "name":           name,
            "description":    cls.description,
            "author":         getattr(cls, "author", "builtin"),
            "version":        getattr(cls, "version", "1.0"),
            "valid_sessions": getattr(cls, "valid_sessions", []),
            "min_bars":       getattr(cls, "min_bars", 30),
            "source":         "builtin" if name in BUILTIN_STRATEGIES else "custom",
        })
    return sorted(result, key=lambda x: (x["source"], x["name"]))


def load_strategy(name: str) -> Optional[Type[BaseStrategy]]:
    """Return strategy class by name, or None if not found."""
    canonical = COMPAT_ALIASES.get(name, name)

    if canonical in BUILTIN_STRATEGIES:
        return BUILTIN_STRATEGIES[canonical]
    if name in BUILTIN_STRATEGIES:
        return BUILTIN_STRATEGIES[name]

    custom = _load_custom_strategies()
    for key in (canonical, name):
        if key in custom:
            return custom[key]

    log.warning(f"Strategy '{name}' not found. Available: {list(BUILTIN_STRATEGIES.keys()) + list(_load_custom_strategies().keys())}")
    return None


def validate_strategy_code(code: str) -> tuple[bool, str]:
    """
    Validate Python code for a strategy plugin before saving.
    Returns (is_valid, error_message).
    """
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    class_defs = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if not class_defs:
        return False, "No class definition found. Strategy must define a class that inherits from BaseStrategy."

    for cls in class_defs:
        attrs = {n.targets[0].id: n for n in ast.walk(cls)
                 if isinstance(n, ast.Assign) and n.targets and isinstance(n.targets[0], ast.Name)}
        if "name" not in attrs:
            return False, f"Class {cls.name} missing required 'name' attribute."
        if "description" not in attrs:
            return False, f"Class {cls.name} missing required 'description' attribute."

    has_find_signal = any(
        isinstance(n, ast.FunctionDef) and n.name == "find_signal"
        for cls in class_defs for n in ast.walk(cls)
    )
    if not has_find_signal:
        return False, "Strategy class must implement 'find_signal(self, bars, i, smc, triggered_ids)' method."

    return True, "OK"


def save_strategy(name: str, code: str) -> tuple[bool, str]:
    """Save a strategy plugin to /data/strategies/. Returns (success, message)."""
    valid, msg = validate_strategy_code(code)
    if not valid:
        return False, msg

    CUSTOM_STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    path = CUSTOM_STRATEGY_DIR / f"{safe_name}.py"
    path.write_text(code, encoding="utf-8")
    log.info(f"Strategy saved: {path}")
    return True, str(path)


def delete_strategy(name: str) -> tuple[bool, str]:
    """Delete a custom strategy. Cannot delete builtins."""
    if name in BUILTIN_STRATEGIES:
        return False, f"Cannot delete built-in strategy '{name}'"
    safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    path = CUSTOM_STRATEGY_DIR / f"{safe_name}.py"
    if not path.exists():
        return False, f"Strategy file not found: {path}"
    path.unlink()
    return True, f"Strategy '{name}' deleted."
