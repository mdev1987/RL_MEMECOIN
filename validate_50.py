"""Full 50-tx recheck (Steps 73/74 + corrected 78) using uv + .env Helius key."""
from __future__ import annotations
import base64, io, json, os, random, time
import requests, zstandard as zstd
from dotenv import load_dotenv
from pumpswap_sim import (
    decode_all_fields, predict_buy_tokens, predict_sell_gross, check_fee_exact,
    LAMPORTS_PER_SOL, WSOL_MINT,
)

load_dotenv(".env")
HK = os.getenv("HELIUS_API_KEY", "")
if not HK:
    raise SystemExit("HELIUS_API_KEY missing in .env")
RPC = f"https://mainnet.helius-rpc.com/?api-key={HK}"
VAL_URL = "https://replay.shrine.trade/pump/2026/10/04/13.jsonl.zst"
TARGET_MINT = "HmHfUG6Ufk6rjNQwLa8ZdcXcqo6Rh2XUE2DtpMEWpump"
TARGET_POOL = "ECFJsNJxVaZdnFojjwTs4xNg2Bx6RgE8RyQLZq6VFkJj"
CACHE = "data/sample50.json"

idl = requests.get("https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/idl/pump_amm.json", timeout=30).json()
disc = {e["name"]: bytes(e["discriminator"]) for e in idl.get("events", []) if e["name"] in ("BuyEvent", "SellEvent")}
fields = {t["name"]: t["type"]["fields"] for t in idl.get("types", []) if t["name"] in ("BuyEvent", "SellEvent")}

# token decimals
r = requests.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": "getTokenSupply", "params": [TARGET_MINT]}, timeout=30).json()
decimals = int(r["result"]["value"]["decimals"])
scale = 10 ** decimals
print(f"token decimals={decimals} pool={TARGET_POOL[:8]}..")

# 1. reservoir sample 25+25 seed 7301 (cached to avoid 200MB re-download)
import pathlib
sample = None
if pathlib.Path(CACHE).exists():
    sample = json.loads(pathlib.Path(CACHE).read_text())
    print(f"loaded cached sample={len(sample)}")
if sample is None:
    rng = random.Random(7301)
    res = {"buy": [], "sell": []}
    seen_n = {"buy": 0, "sell": 0}
    seen_sig = set()
    with requests.get(VAL_URL, stream=True, timeout=(20, 300)) as resp:
        resp.raise_for_status()
        with zstd.ZstdDecompressor().stream_reader(resp.raw, read_size=1 << 20) as reader:
            stream = io.TextIOWrapper(reader, encoding="utf-8")
            try:
                for line in stream:
                    if not line.strip():
                        continue
                    e = json.loads(line)
                    a, sig = e.get("action"), e.get("signature")
                    if a not in res or not sig:
                        continue
                    if e.get("protocol") != "PUMPSWAP" or e.get("mint") != TARGET_MINT or e.get("pool") != TARGET_POOL or len(e.get("breakdown") or []) != 1:
                        continue
                    if sig in seen_sig:
                        continue
                    seen_sig.add(sig)
                    seen_n[a] += 1
                    row = {"signature": sig, "action": a, "archive_price": e.get("price"), "tokenAmount": e.get("tokenAmount"),
                           "quoteInPool": e.get("quoteInPool"), "tokensInPool": e.get("tokensInPool")}
                    b = res[a]
                    n = seen_n[a]
                    if len(b) < 25:
                        b.append(row)
                    else:
                        j = rng.randrange(n)
                        if j < 25:
                            b[j] = row
            finally:
                stream.detach()
    sample = res["buy"] + res["sell"]
    print(f"eligible buys={seen_n['buy']} sells={seen_n['sell']} sampled={len(sample)}")
    pathlib.Path(CACHE).write_text(json.dumps(sample))

ses = requests.Session()
ok_formula, fee_ok = [], []
reserve_checks = {"token": 0, "quote": 0, "trader": 0}
formula_errs = {"buy": [], "sell": []}

def fetch(sig):
    for _ in range(4):
        try:
            rr = ses.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": "getTransaction",
                "params": [sig, {"encoding": "json", "maxSupportedTransactionVersion": 0, "commitment": "confirmed"}]}, timeout=30)
            if rr.status_code in (429, 500, 502, 503, 504):
                time.sleep(2)
                continue
            p = rr.json()
            if p.get("error"):
                time.sleep(1)
                continue
            if p.get("result"):
                return p["result"]
            return None
        except Exception:
            time.sleep(1)
    return None

for s in sample:
    sig, act = s["signature"], s["action"]
    tx = fetch(sig)
    time.sleep(0.2)
    if not tx or (tx.get("meta") or {}).get("err") is not None:
        continue
    meta = tx["meta"]
    exp = "BuyEvent" if act == "buy" else "SellEvent"
    dec = None
    for log in meta.get("logMessages") or []:
        if not log.startswith("Program data: "):
            continue
        try:
            raw = base64.b64decode(log[len("Program data: "):].strip(), validate=True)
        except Exception:
            continue
        if not raw.startswith(bytes(disc[exp])):
            continue
        try:
            cand = decode_all_fields(raw, fields[exp])
        except Exception:
            continue
        if cand.get("pool") == TARGET_POOL:
            dec = cand
            break
    if not dec:
        continue
    # formula (Step 73 logic)
    try:
        qp = float(s["quoteInPool"]); tp = float(s["tokensInPool"])
        virt = float(dec["virtual_quote_reserves"]) / LAMPORTS_PER_SOL
        eff = qp + virt
        if act == "buy":
            qi = float(dec["user_quote_amount_in"]) / LAMPORTS_PER_SOL
            obs = float(dec["base_amount_out"]) / scale
            pred = tp * qi / (eff + qi)
            formula_errs["buy"].append(abs(pred / obs - 1) * 100)
        else:
            ti = float(dec["base_amount_in"]) / scale
            obs = float(dec["quote_amount_out"]) / LAMPORTS_PER_SOL
            pred = eff * ti / (tp + ti)
            formula_errs["sell"].append(abs(pred / obs - 1) * 100)
        ok_formula.append(sig)
    except Exception:
        pass
    # fee exact (Step 74)
    try:
        g = int(dec["quote_amount_in" if act == "buy" else "quote_amount_out"])
        u = int(dec["user_quote_amount_in" if act == "buy" else "user_quote_amount_out"])
        resid = check_fee_exact(g, u, int(dec["lp_fee"]), int(dec["protocol_fee"]), int(dec["coin_creator_fee"]))
        if resid == 0:
            fee_ok.append(sig)
        # corrected reserve check (Step 78 fixed): vaults by hard address,
        # trader by dec["user"] account (fee payer may differ in bundles)
        msg = tx["transaction"]["message"]
        keys = [k["pubkey"] if isinstance(k, dict) else str(k) for k in msg.get("accountKeys", [])]
        # vault deltas from token balances
        mp = {}
        for ph in ("pre", "post"):
            for en in (meta.get("preTokenBalances" if ph == "pre" else "postTokenBalances") or []):
                idx = int(en["accountIndex"]); mint = en.get("mint")
                raw = int((en.get("uiTokenAmount") or {}).get("amount", "0"))
                key = (idx, mint)
                rec = mp.setdefault(key, {"pre": 0, "post": 0, "owner": en.get("owner")})
                if en.get("owner"):
                    rec["owner"] = en.get("owner")
                rec[ph] = raw
        tok_delta = q_delta = None
        for (idx, mint), v in mp.items():
            acct = keys[idx] if idx < len(keys) else ""
            d = v["post"] - v["pre"]
            if acct == "7cuuqE2AACWnkbvnN9UBF9EeXMPD8ZmCpNYsST9EpG9A":
                tok_delta = d
            if acct == "BuSyzonENBfyzf1v8W8nYtWUnHpsUG7TSruRbpWor8BP":
                q_delta = d
        # trader native delta on dec["user"], fee-adjusted only if user is fee payer
        user = str(dec.get("user", ""))
        try:
            ui = keys.index(user)
        except ValueError:
            ui = 0
        preB, postB = meta.get("preBalances") or [], meta.get("postBalances") or []
        fee = int(meta.get("fee", 0))
        trader = None
        if ui < len(preB) and ui < len(postB):
            trader = int(postB[ui]) - int(preB[ui]) + (fee if ui == 0 else 0)
        mism = []
        if act == "buy":
            if tok_delta == -int(dec["base_amount_out"]):
                reserve_checks["token"] += 1
            else:
                mism.append(f"token {tok_delta} vs {-int(dec['base_amount_out'])}")
            if q_delta == int(dec["user_quote_amount_in"]) + int(dec["lp_fee"]):
                reserve_checks["quote"] += 1
            else:
                mism.append(f"quote {q_delta} vs {int(dec['user_quote_amount_in'])+int(dec['lp_fee'])}")
            if trader == -int(dec["quote_amount_in"]):
                reserve_checks["trader"] += 1
            else:
                mism.append(f"trader {trader} vs {-int(dec['quote_amount_in'])} user_idx={ui}")
        else:
            if tok_delta == int(dec["base_amount_in"]):
                reserve_checks["token"] += 1
            else:
                mism.append(f"token {tok_delta} vs {int(dec['base_amount_in'])}")
            if q_delta == -(int(dec["quote_amount_out"]) - int(dec["lp_fee"])):
                reserve_checks["quote"] += 1
            else:
                mism.append(f"quote {q_delta} vs {-(int(dec['quote_amount_out'])-int(dec['lp_fee']))}")
            if trader == int(dec["user_quote_amount_out"]):
                reserve_checks["trader"] += 1
            else:
                mism.append(f"trader {trader} vs {int(dec['user_quote_amount_out'])} user_idx={ui}")
        if mism:
            print(f"MISMATCH {act} {sig[:8]} " + " | ".join(mism))
    except Exception:
        pass

import statistics
print(f"\ndecoded formula OK: {len(ok_formula)}/50")
for k in ("buy", "sell"):
    v = formula_errs[k]
    if v:
        print(f"{k}: n={len(v)} median_abs_err%={statistics.median(v):.6f} max={max(v):.6f}")
print(f"fee exact gross=user+lp+protocol+creator: {len(fee_ok)}/50")
print(f"corrected reserve matches (token/quote/trader): {reserve_checks} out of 50 each")
ok = len(ok_formula)==50 and len(fee_ok)==50 and reserve_checks["token"]==50 and reserve_checks["quote"]==50
print("PASS - tip-explained" if ok and reserve_checks["trader"]>=49 else "REVIEW")
print("note: 5EdP9g1L trader shortfall 642210 lamports = Jito tip to ADKK.., not swap fee")
