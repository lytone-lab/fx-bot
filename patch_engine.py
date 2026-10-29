import pathlib, sys
p = pathlib.Path("backtest2.py")
src = p.read_text(encoding="utf-8")
if "STRATEGIES[\"jeafx\"]" in src:
    print("already patched, nothing to do"); sys.exit(0)
old = "STRATEGIES = {\"trend_atr\": strat_trend_atr, \"mine\": strat_mine}"
if old not in src:
    print("ERROR: anchor line not found - aborting, nothing changed"); sys.exit(1)
new = old + """
try:
    from jeafx import strat_jeafx as _jeafx_strategy
    STRATEGIES["jeafx"] = _jeafx_strategy
except Exception as _e:
    print(f"[warn] jeafx NOT registered: {_e!r}")
"""
p.with_suffix(".py.bak").write_text(src, encoding="utf-8")
p.write_text(src.replace(old, new, 1), encoding="utf-8")
print("patched backtest2.py (backup saved as backtest2.py.bak)")
