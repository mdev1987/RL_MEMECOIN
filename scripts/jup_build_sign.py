"""Jupiter Router path: /build -> assemble -> local sign (shadow mode).

- GET /swap/v2/build for a BUY (SOL -> USDC) with the env taker.
- Assembles a VersionedTransaction locally (resolves lookup tables via
  read-only Helius getAccountInfo), signs with BS58_PRIVATE_KEY, verifies.
- NEVER broadcasts: no /execute, no /submit, no sendTransaction anywhere.

Usage: .venv/bin/python scripts/jup_build_sign.py [--buy-sol 0.05]
"""
from __future__ import annotations

import argparse
import base64
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
# Live-signing key lives apart (least privilege: paper daemons never see it).
load_dotenv(Path(__file__).resolve().parents[1] / ".env.signer")

BASE = "https://api.jup.ag/swap/v2"
SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
LAMPORTS = 1_000_000_000

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58_to_bytes(s: str) -> bytes:
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    return n.to_bytes(64, "big")


def main() -> None:
    from solders.address_lookup_table_account import (
        AddressLookupTable, AddressLookupTableAccount,
    )
    from solders.hash import Hash
    from solders.instruction import AccountMeta, Instruction
    from solders.keypair import Keypair
    from solders.message import MessageV0
    from solders.pubkey import Pubkey
    from solders.transaction import VersionedTransaction

    ap = argparse.ArgumentParser()
    ap.add_argument("--buy-sol", type=float, default=0.05)
    a = ap.parse_args()
    api_key = os.environ.get("JUPITER_API_KEY", "")
    hk = os.environ.get("HELIUS_API_KEY", "")
    b58 = os.environ.get("BS58_PRIVATE_KEY", "").strip()
    if not api_key or not hk or not b58:
        raise SystemExit("need JUPITER_API_KEY + HELIUS_API_KEY + BS58_PRIVATE_KEY in .env")
    kp = Keypair.from_bytes(b58_to_bytes(b58))
    taker = str(kp.pubkey())

    o = requests.get(
        f"{BASE}/build",
        params={"inputMint": SOL, "outputMint": USDC,
                "amount": str(int(round(a.buy_sol * LAMPORTS))),
                "taker": taker},
        headers={"x-api-key": api_key}, timeout=30)
    if not o.ok:
        raise SystemExit(f"[{o.status_code}] {o.text[:300]}")
    o = o.json()
    if "routePlan" not in o:
        raise SystemExit(f"no routes: {str(o)[:300]}")
    print(f"in={o['inAmount']} -> out={o['outAmount']} "
          f"route={[(s['percent'], s['swapInfo']['label']) for s in o['routePlan']]}")

    def conv(ixd: dict) -> Instruction:
        return Instruction(
            program_id=Pubkey.from_string(ixd["programId"]),
            data=base64.b64decode(ixd["data"]),
            accounts=[AccountMeta(Pubkey.from_string(x["pubkey"]),
                                  x["isSigner"], x["isWritable"])
                      for x in ixd["accounts"]],
        )

    ixs = [conv(x) for x in o.get("computeBudgetInstructions", [])]
    ixs += [conv(x) for x in o.get("setupInstructions", [])]
    ixs.append(conv(o["swapInstruction"]))
    if o.get("cleanupInstruction"):
        ixs.append(conv(o["cleanupInstruction"]))
    ixs += [conv(x) for x in o.get("otherInstructions", [])]
    if o.get("tipInstruction"):
        ixs.append(conv(o["tipInstruction"]))
    print(f"instructions={len(ixs)}")

    rpc = f"https://mainnet.helius-rpc.com/?api-key={hk}"
    alts = []
    for table, addrs in (o.get("addressesByLookupTableAddress") or {}).items():
        acc = requests.post(
            rpc, json={"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
                       "params": [table, {"encoding": "base64"}]},
            timeout=30).json()["result"]["value"]
        if not acc:
            raise SystemExit(f"LUT missing on-chain: {table}")
        data = base64.b64decode(acc["data"][0])
        lut = AddressLookupTable.deserialize(data)
        alts.append(AddressLookupTableAccount(
            key=Pubkey.from_string(table), addresses=list(lut.addresses)))
    print(f"lookup_tables={len(alts)}")

    bh = bytes(o["blockhashWithMetadata"]["blockhash"])
    msg = MessageV0.try_compile(Pubkey.from_string(taker), ixs, alts,
                                Hash(bh))
    sig = kp.sign_message(bytes(msg))
    assert sig.verify(kp.pubkey(), bytes(msg)), "signature self-check failed"
    signed = VersionedTransaction.populate(msg, [sig])
    assert bytes(signed.message) == bytes(msg)
    print(f"BUILT+SIGNED locally: taker={taker}")
    print(f"signature={sig} (NOT broadcast: no /execute, no /submit)")
    print(f"wire_bytes={len(bytes(signed))} fee_payer={msg.account_keys[0]}")


if __name__ == "__main__":
    main()
