import pathlib, sys
p = pathlib.Path("jeafx.py")
src = p.read_text(encoding="utf-8")
if "if tgt is None or (tgt - entry) * s_ / risk < rr:" in src:
    print("already patched"); sys.exit(0)
old = """        tgt = pick_target(z, entry, risk)
        if tgt is None:
            z["why"] = "R15 no target with RR>=min"
            return None"""
new = """        tgt = pick_target(z, entry, risk)
        if tgt is None or (tgt - entry) * s_ / risk < rr:
            z["why"] = "R15 no target with RR>=min"
            return None"""
if old not in src:
    print("ERROR: anchor not found - aborting"); sys.exit(1)
p.with_suffix(".py.bak4").write_text(src, encoding="utf-8")
p.write_text(src.replace(old, new, 1), encoding="utf-8")
print("patched RR enforcement (backup -> jeafx.py.bak4)")
