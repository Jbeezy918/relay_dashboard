#!/usr/bin/env python3
"""Test datetime safety and prevent Section 5 regression"""

from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

APP = Path("/Users/joebudds/Documents/Updated_Relay_Files/app.py")

def load():
    spec = spec_from_file_location("app", str(APP))
    mod = module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def test_safe_dt_valid_and_invalid():
    app = load()
    z = app._safe_dt("2024-01-01T00:00:00Z")
    assert str(z).endswith("+00:00")
    fallback = app._safe_dt("not-a-date")
    assert hasattr(fallback, "year")

def test_no_direct_fromisoformat_calls_outside_helper():
    text = APP.read_text()
    fromisoformat_count = text.count("datetime.fromisoformat")
    # exactly one usage (inside _safe_dt)
    assert fromisoformat_count == 1

if __name__ == "__main__":
    test_safe_dt_valid_and_invalid()
    test_no_direct_fromisoformat_calls_outside_helper()
    print("✅ All datetime safety tests passed")