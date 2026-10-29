import pathlib
p = pathlib.Path("jeafx.py")
s = p.read_text(encoding="utf-8")
s = s.replace("ltf_lo = min(ltf.l[ltf_start:ltf_end+1], zlo)", "ltf_lo = min(float(np.min(ltf.l[ltf_start:ltf_end+1])), zlo)")
s = s.replace("ltf_hi = max(ltf.h[ltf_start:ltf_end+1], zhi)", "ltf_hi = max(float(np.max(ltf.h[ltf_start:ltf_end+1])), zhi)")
p.write_text(s, encoding="utf-8")
print("fixed jeafx.py numpy bug")
