import pathlib, sys
p = pathlib.Path("jeafx.py")
src = p.read_text(encoding="utf-8")
if 'z["state"], z["end_i"] = "used", i' in src:
    print("already patched"); sys.exit(0)
old = """            if best is not None:
                _, z, edge, (stop, tgt) = best
                side[i], sl_out[i], tp_out[i], ent_out[i] = z["side"], stop, tgt, edge"""
new = """            if best is not None:
                _, z, edge, (stop, tgt) = best
                side[i], sl_out[i], tp_out[i], ent_out[i] = z["side"], stop, tgt, edge
                z["state"], z["end_i"] = "used", i"""
if old not in src:
    print("ERROR: anchor not found"); sys.exit(1)
p.with_suffix(".py.bak3").write_text(src, encoding="utf-8")
p.write_text(src.replace(old, new, 1), encoding="utf-8")
print("patched refill bug (backup -> jeafx.py.bak3)")
