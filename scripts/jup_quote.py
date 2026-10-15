"""Jupiter quote + local sign check (shadow mode).

- GET /swap/v2/order for a BUY (SOL -> USDC) and a SELL (USDC -> SOL).
- Signs the returned transaction LOCALLY with a fresh throwaway keypair.
- NEVER broadcasts: /execute is not called anywhere in this file.

Usage: .venv/bin/python scripts/jup_quote.py [--buy-sol 0.05] [--sell-usdc 5]
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
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


def jup_get(path: str, params: dict, api_key: str) -> dict:
    r = requests.get(f"{BASE}{path}", params=params,
                     headers={"x-api-key": api_key}, timeout=30)
    if not r.ok:
        rid = r.headers.get("x-api-gateway-request-id", "?")
        raise SystemExit(f"[{r.status_code}] gateway-request={rid} body={r.text[:300]}")
    return r.json()


def show(label: str, o: dict) -> None:
    print(f"--- {label} ---")
    print(f"router={o.get('router')} mode={o.get('mode')} tx_version={o.get('transactionVersion')}")
    print(f"in={o.get('inAmount')} {o.get('inputMint', '')[:8]} "
          f"-> out={o.get('outAmount')} {o.get('outputMint', '')[:8]}")
    print(f"feeBps={o.get('feeBps')} platformFee={o.get('platformFee')} "
          f"priceImpact={o.get('priceImpact')}%")
    print(f"sigFee={o.get('signatureFeeLamports')} prioFee={o.get('prioritizationFeeLamports')} "
          f"rentFee={o.get('rentFeeLamports')} gasless={o.get('gasless')}")
    legs = [(s.get("percent"), (s.get("swapInfo") or {}).get("label"))
            for s in (o.get("routePlan") or [])]
    print(f"route={legs} requestId={o.get('requestId')}")
    tx = o.get("transaction")
    print(f"transaction: {'present (%d chars)' % len(tx) if tx else repr(tx)}")
    if o.get("errorCode") is not None:
        print(f"errorCode={o.get('errorCode')} errorMessage={o.get('errorMessage')}")


def sign_locally(order: dict):
    """Deserialize order['transaction'], sign with a fresh keypair, verify.

    Returns (pubkey_str, signature_str). Keypair is random per run and the
    secret never leaves this process. Nothing is broadcast.
    """
    from solders.keypair import Keypair
    from solders.transaction import VersionedTransaction

    raw = order.get("transaction")
    if not raw:
        return None
    kp = Keypair()  # fresh throwaway signer; unfunded; signing needs no funds
    tx = VersionedTransaction.from_bytes(base64.b64decode(raw))
    msg = tx.message
    sig = kp.sign_message(bytes(msg))
    assert sig.verify(kp.pubkey(), bytes(msg)), "signature self-check failed"
    signed = VersionedTransaction.populate(msg, [sig])
    assert bytes(signed.message) == bytes(msg)
    return str(kp.pubkey()), str(sig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--buy-sol", type=float, default=0.05)
    ap.add_argument("--sell-usdc", type=float, default=5.0)
    ap.add_argument("--self-test-sign", action="store_true",
                    help="prove the local sign pipeline on a dummy 0-lamport "
                         "self-transfer (fresh blockhash, signed, verified, never broadcast)")
    a = ap.parse_args()
    api_key = os.environ.get("JUPITER_API_KEY", "")
    if not api_key:
        raise SystemExit("JUPITER_API_KEY missing in .env")

    buy_lam = int(round(a.buy_sol * LAMPORTS))
    sell_units = int(round(a.sell_usdc * 1_000_000))

    # 1) BUY quote-only (no taker -> quote, no transaction)
    buy_q = jup_get("/order", {"inputMint": SOL, "outputMint": USDC,
                               "amount": str(buy_lam)}, api_key)
    show(f"BUY {a.buy_sol:g} SOL -> USDC (quote-only)", buy_q)
    time.sleep(1.2)

    # 2) SELL quote-only
    sell_q = jup_get("/order", {"inputMint": USDC, "outputMint": SOL,
                                "amount": str(sell_units)}, api_key)
    show(f"SELL {a.sell_usdc:g} USDC -> SOL (quote-only)", sell_q)
    time.sleep(1.2)

    # 3) BUY order with taker, then local sign (never /execute).
    # NOTE: Jupiter only builds when the taker can fund the trade
    # (errorCode 1 otherwise). Fund the throwaway with dust to unlock builds.
    from solders.transaction import VersionedTransaction
    signer, kind = _resolve_signer()
    print(f"taker source: {kind} taker={signer.pubkey()}")
    order = jup_get("/order", {"inputMint": SOL, "outputMint": USDC,
                               "amount": str(buy_lam),
                               "taker": str(signer.pubkey())}, api_key)
    show("BUY order with taker", order)
    if order.get("transaction"):
        tx = VersionedTransaction.from_bytes(
            base64.b64decode(order["transaction"]))
        sig = signer.sign_message(bytes(tx.message))
        assert sig.verify(signer.pubkey(), bytes(tx.message))
        VersionedTransaction.populate(tx.message, [sig])
        print(f"SIGNED locally: taker={signer.pubkey()} signature={sig}")
        print("NOT broadcast (no /execute call). Done.")
    else:
        print(f"no transaction built: errorCode={order.get('errorCode')} "
              f"{order.get('errorMessage')}")

    if a.self_test_sign:
        _self_test_sign()


def _self_test_sign() -> None:
    """Sign a dummy 0-lamport self-transfer with a fresh blockhash.

    Proves the exact local-sign code path (serialize -> ed25519 sign ->
    verify -> populate) without involving funds or the network beyond one
    read-only blockhash fetch. Nothing is broadcast.
    """
    from solders.hash import Hash
    from solders.keypair import Keypair
    from solders.message import MessageV0
    from solders.system_program import TransferParams, transfer
    from solders.transaction import VersionedTransaction

    hk = os.environ.get("HELIUS_API_KEY", "")
    if not hk:
        raise SystemExit("HELIUS_API_KEY missing in .env")
    rpc = requests.post(f"https://mainnet.helius-rpc.com/?api-key={hk}",
                        json={"jsonrpc": "2.0", "id": 1,
                              "method": "getLatestBlockhash",
                              "params": [{"commitment": "confirmed"}]},
                        timeout=30).json()
    bh = rpc["result"]["value"]["blockhash"]
    kp = Keypair()  # fresh throwaway signer
    ix = transfer(TransferParams(from_pubkey=kp.pubkey(),
                                 to_pubkey=kp.pubkey(), lamports=0))
    msg = MessageV0.try_compile(kp.pubkey(), [ix], [], Hash.from_string(bh))
    sig = kp.sign_message(bytes(msg))
    assert sig.verify(kp.pubkey(), bytes(msg)), "self-check failed"
    signed = VersionedTransaction.populate(msg, [sig])
    assert bytes(signed.message) == bytes(msg)
    print(f"SELF-TEST SIGNED: taker={kp.pubkey()} signature={sig} "
          f"blockhash={bh[:8]}.. (0 lamports, not broadcast)")


def _resolve_signer():
    """Live/paper parity: use BS58_PRIVATE_KEY as taker when configured
    (throwaway pre-live, real wallet on live — identical code path).
    Falls back to a random throwaway keypair when unset."""
    from solders.keypair import Keypair
    b58 = os.environ.get("BS58_PRIVATE_KEY", "").strip()
    if b58:
        B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        n = 0
        for c in b58:
            n = n * 58 + B58.index(c)
        return Keypair.from_bytes(n.to_bytes(64, "big")), "env"
    return Keypair(), "throwaway"


if __name__ == "__main__":
    main()
