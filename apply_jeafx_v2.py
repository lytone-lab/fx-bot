import pathlib, sys

# --- Patch jeafx.py ---
p1 = pathlib.Path("jeafx.py")
src1 = p1.read_text(encoding="utf-8")

if "max_rr=4.0" in src1:
    print("jeafx.py already patched")
else:
    old_sig = 'def strat_jeafx(df, mode="confirm", htf_mult=4, bias_mult=0, k=1.5, atr_n=14, rr=2.0, buf=0.1,'
    new_sig = 'def strat_jeafx(df, mode="confirm", htf_mult=4, bias_mult=4, k=1.5, atr_n=14, rr=2.0, max_rr=4.0, buf=0.1,'
    src1 = src1.replace(old_sig, new_sig)

    old_imp = 'veto_body=3.0, bos_body=1.0, bos_speed=0.5, imp_body=1.0, eq_tol=0.1, eq_dist=5.0,'
    new_imp = 'veto_body=3.0, bos_body=1.0, bos_speed=0.5, imp_body=0.5, eq_tol=0.1, eq_dist=5.0,'
    src1 = src1.replace(old_imp, new_imp)

    old_fa = 'confirm_bars=40, flip=1, bounce=0.5, flip_age=40, allow_short=True):'
    new_fa = 'confirm_bars=40, flip=1, bounce=0.5, flip_age=20, allow_short=True):'
    src1 = src1.replace(old_fa, new_fa)

    old_pt = '''    def pick_target(z, entry, risk):
        if z["side"] == 1:
            cands = [x["price"] for x in htf.sh[-30:] if x["price"] > entry]
            if not z["flip"] and z["peak"] > entry:
                cands.append(z["peak"])
            for t in sorted(set(cands)):
                if (t - entry) / risk >= rr:
                    return t
        else:
            cands = [x["price"] for x in htf.sl[-30:] if x["price"] < entry]
            if not z["flip"] and z["peak"] < entry:
                cands.append(z["peak"])
            for t in sorted(set(cands), reverse=True):
                if (entry - t) / risk >= rr:
                    return t
        return None'''
    new_pt = '''    def pick_target(z, entry, risk):
        if z["side"] == 1:
            cands = [x["price"] for x in htf.sh[-30:] if x["price"] > entry]
            if not z["flip"] and z["peak"] > entry:
                cands.append(z["peak"])
            for t in sorted(set(cands)):
                if (t - entry) / risk >= rr:
                    return min(t, entry + max_rr * risk)
        else:
            cands = [x["price"] for x in htf.sl[-30:] if x["price"] < entry]
            if not z["flip"] and z["peak"] < entry:
                cands.append(z["peak"])
            for t in sorted(set(cands), reverse=True):
                if (entry - t) / risk >= rr:
                    return max(t, entry - max_rr * risk)
        return None'''
    src1 = src1.replace(old_pt, new_pt)

    old_fz = 'zinfo = find_zone(htf, Li, hj, d, "largest", imp_body)'
    new_fz = 'zinfo = find_zone(htf, Li, hj, d, "first", imp_body)'
    src1 = src1.replace(old_fz, new_fz)

    old_nz = '''    def new_zone(s_, zinfo, hj, i, L_price, L_idx, peak, peak_i, flip_):
        zi, zlo, zhi = zinfo
        z = {"id": len(zones) + 1, "side": s_, "lo": zlo, "hi": zhi, "zidx": zi, "hidx": hj, "bidx": i,'''
    new_nz = '''    def new_zone(s_, zinfo, hj, i, L_price, L_idx, peak, peak_i, flip_):
        zi, zlo, zhi = zinfo
        ltf_start = htf_start[zi] if zi < len(htf_start) else i
        ltf_end = htf_end[zi] if zi < len(htf_end) else i
        if ltf_end >= ltf_start and not flip_:
            ltf_lo = min(ltf.l[ltf_start:ltf_end+1])
            ltf_hi = max(ltf.h[ltf_start:ltf_end+1])
        else:
            ltf_lo, ltf_hi = zlo, zhi
        z = {"id": len(zones) + 1, "side": s_, "lo": ltf_lo, "hi": ltf_hi, "zidx": zi, "hidx": hj, "bidx": i,'''
    src1 = src1.replace(old_nz, new_nz)

    p1.with_suffix(".py.bak6").write_text(p1.read_text(encoding="utf-8"), encoding="utf-8")
    p1.write_text(src1, encoding="utf-8")
    print("patched jeafx.py (backup -> jeafx.py.bak6)")

# --- Patch backtest2.py (Pyramiding) ---
p2 = pathlib.Path("backtest2.py")
src2 = p2.read_text(encoding="utf-8")

if "pyramided = False" in src2:
    print("backtest2.py already patched")
else:
    old_loop = "    for t in range(n):\n        # 1) enter at this candle's open"
    new_loop = "    pyramided = False\n    for t in range(n):\n        # 1) enter at this candle's open"
    src2 = src2.replace(old_loop, new_loop, 1)

    old_cond = "        if pos == 0 and t > 0 and side[t - 1] != 0 and not np.isnan(sl_s[t - 1]) and equity > 0:"
    new_cond = "        if t > 0 and side[t - 1] != 0 and not np.isnan(sl_s[t - 1]) and equity > 0:"
    src2 = src2.replace(old_cond, new_cond, 1)

    old_exec = """            if filled:
                dist = (px - sl_s[t - 1]) * s
                ok = dist > 0 and (tp_s[t - 1] - px) * s > 0
                if ok and leverage > 1 and dist / px > 0.9 / leverage:
                    ok = False  # stop is further than the liquidation price: skip the trade
                if ok:
                    q = equity * risk_pct / dist
                    if q * px > equity * leverage:
                        q = equity * leverage / px
                    pos, entry, sl, tp, qty = s, px, float(sl_s[t - 1]), float(tp_s[t - 1]), q
                    risk_amt = q * dist
                    entry_fee = q * px * fee
                    entry_i = t"""

    new_exec = """            if filled:
                dist = (px - sl_s[t - 1]) * s
                ok = dist > 0 and (tp_s[t - 1] - px) * s > 0
                if ok and leverage > 1 and dist / px > 0.9 / leverage:
                    ok = False  # stop is further than the liquidation price: skip the trade
                if ok:
                    if pos == 0:
                        q = equity * risk_pct / dist
                        if q * px > equity * leverage:
                            q = equity * leverage / px
                        pos, entry, sl, tp, qty = s, px, float(sl_s[t - 1]), float(tp_s[t - 1]), q
                        risk_amt = q * dist
                        entry_fee = q * px * fee
                        entry_i = t
                        pyramided = False
                    elif pos == s and (px - entry) * pos > 0 and not pyramided:
                        q = equity * risk_pct / dist
                        if q * px > equity * leverage:
                            q = equity * leverage / px
                        new_qty = qty + q
                        entry = (entry * qty + px * q) / new_qty
                        qty = new_qty
                        sl = entry  # move to breakeven
                        entry_fee += q * px * fee
                        pyramided = True"""

    src2 = src2.replace(old_exec, new_exec, 1)

    p2.with_suffix(".py.bak6").write_text(p2.read_text(encoding="utf-8"), encoding="utf-8")
    p2.write_text(src2, encoding="utf-8")
    print("patched backtest2.py (backup -> backtest2.py.bak6)")
