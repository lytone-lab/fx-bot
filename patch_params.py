import pathlib, sys
p = pathlib.Path("backtest2.py")
src = p.read_text(encoding="utf-8")
if "out[k] = v  # string fallback" in src:
    print("already patched, nothing to do"); sys.exit(0)
old = """            try:
                out[k] = int(v)
            except ValueError:
                out[k] = float(v)"""
new = """            try:
                out[k] = int(v)
            except ValueError:
                try:
                    out[k] = float(v)
                except ValueError:
                    out[k] = v  # string fallback"""
if old not in src:
    print("ERROR: anchor block not found - aborting, nothing changed"); sys.exit(1)
p.with_suffix(".py.bak2").write_text(src, encoding="utf-8")
p.write_text(src.replace(old, new, 1), encoding="utf-8")
print("patched parse_params (backup saved as backtest2.py.bak2)")
