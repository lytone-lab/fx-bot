import pathlib, sys
p = pathlib.Path("jeafx.py")
s = p.read_text(encoding="utf-8")
old1 = "ltf_lo = min(ltf.l[ltf_start:ltf_end+1], zlo)"
new1 = "ltf_lo = min(float(np.min(ltf.l[ltf_start:ltf_end+1])), zlo)"
old2 = "ltf_hi = max(ltf.h[ltf_start:ltf_end+1], zhi)"
new2 = "ltf_hi = max(float(np.max(ltf.h[ltf_start:ltf_end+1])), zhi)"
if old1 not in s or old2 not in s:
    print("ERROR: anchor not found"); sys.exit(1)
s = s.replace(old1, new1, 1).replace(old2, new2, 1)
p.with_suffix(".py.bak8").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
p.write_text(s, encoding="utf-8")
print("fixed new_zone numpy slice (backup -> jeafx.py.bak8)")
