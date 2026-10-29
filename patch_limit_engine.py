import pathlib, sys
p = pathlib.Path("backtest2.py")
src = p.read_text(encoding="utf-8")

if "filled = False" in src and "ent_s = sig" in src:
    print("already patched"); sys.exit(0)

# 1. Add reading of the entry price array
old_sig = "    sl_s, tp_s = sig[\"sl\"].values, sig[\"tp\"].values"
new_sig = "    sl_s, tp_s = sig[\"sl\"].values, sig[\"tp\"].values\n    ent_s = sig[\"entry\"].values.astype(float) if \"entry\" in sig.columns else np.full(n, np.nan)"
if old_sig not in src:
    print("ERROR: anchor 1 not found"); sys.exit(1)
src = src.replace(old_sig, new_sig, 1)

# 2. Replace the entry execution logic
old_entry = """        if pos == 0 and t > 0 and side[t - 1] != 0 and not np.isnan(sl_s[t - 1]) and equity > 0:
            s = int(side[t - 1])
            px = o[t] * (1 + slip * s)  # slippage always works against you
            dist = (px - sl_s[t - 1]) * s"""

new_entry = """        if pos == 0 and t > 0 and side[t - 1] != 0 and not np.isnan(sl_s[t - 1]) and equity > 0:
            s = int(side[t - 1])
            lim = ent_s[t - 1]
            filled = False
            if np.isnan(lim):
                px = o[t] * (1 + slip * s)
                filled = True
            elif s == 1 and l[t] <= lim:
                px, filled = min(lim, o[t]), True
            elif s == -1 and h[t] >= lim:
                px, filled = max(lim, o[t]), True
                
            if not filled:
                dist = 0
            else:
                dist = (px - sl_s[t - 1]) * s"""

if old_entry not in src:
    print("ERROR: anchor 2 not found"); sys.exit(1)
src = src.replace(old_entry, new_entry, 1)

p.with_suffix(".py.bak5").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
p.write_text(src, encoding="utf-8")
print("patched backtest2.py limit order engine (backup -> backtest2.py.bak5)")
