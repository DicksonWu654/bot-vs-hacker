#!/usr/bin/env python3
"""Build the static data for the site.

    .venv/bin/python site/build_data.py            # from the project root
    .venv/bin/python site/build_data.py --no-copy  # data only, skip raw copy (fast iteration)

Inputs (all optional, handled defensively):
  data/incidents.json                master dataset written by the consolidation agent (schema: notes/phase3-brief.md)
  incidents/*/incident.json          fallback: per-incident narrative + raw_refs (field names vary a lot)
  incidents/*/timeline.json          events (list, or {"events": [...]})
  incidents/*/race_*.json            'bvh-race/1' per-block docs: txs, relay bids, mempool first-seen, raw_refs
  data/evolution/by_era(_v2).json, per_exploit(_v2).json, findings(_v2).txt
  research/bot-re/ronin_calldata_diff.json

Outputs:
  site/data/incidents.json           one summary row per race (the comparison table)
  site/data/incident/<id>.json       the three-lane race detail for each row
  site/data/evolution.json           charts for evolution.html
  site/data/explainer.json           calldata diff for explainer.html
  site/data/meta.json                build info, sizes, caveats
  site/raw/<path under data/raw/>    ONLY files referenced by raw_refs (see copy_raw)
  site/raw/mempool-dumpster/*.rows.csv   verbatim rows for cited tx hashes, cut from the 100 MB+ day files
  site/raw/MANIFEST.json             provenance (origin path, sha256, bytes, upstream URL) for each published raw file

Rules honoured: nothing from private/, no c0ffeebabe bot internals (only tx-level public facts), no race_*.json
or incident.json analysis files are published (they hold call-structure analysis); only raw responses.
"""
import csv
import datetime
import glob
import hashlib
import io
import json
import math
import os
import re
import shutil
import statistics
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts/lib"))
from publication import scrub_public
import evidence_check

SITE = ROOT / "site"
DATA_OUT = SITE / "data"
RAW_OUT = SITE / "raw"
RAW_BUDGET_MB = int(os.environ.get("BVH_RAW_BUDGET_MB", "250"))
MAX_BIDS = 400
MAX_RECORD = 140

HEADLINE_TYPES = {"beat-pending-attack", "deploy-window-copy"}
YOINK_BUILDER = "I can haz block?"

# --------------------------------------------------------------------------------------------------------------
# Curated fallback table. Used for fields that data/incidents.json does not (yet) provide. Everything here is
# lifted from the incident summary.txt files; the consolidated dataset overrides any field it supplies.
#   block      : block number of the bot's landing block (picks the race_*.json doc)
#   bot_addr   : EOA prefixes that identify the bot's txs ; bot_tx : tx-hash prefixes
#   atk_addr / atk_tx : same for the attacker (or the user / whitehat whose tx was copied)
#   atk_block  : block where the attacker's own call landed (None = never landed / no attacker)
# --------------------------------------------------------------------------------------------------------------
YOINK = "0xfde0d157"
C0FFEE = "0xc0ffeebabe"
SPEC = [
    dict(slug="alkimiya-2025", block=22146340, bot="Yoink (gen 3)", race_type="beat-pending-attack",
         bot_addr=[YOINK], atk_addr=["0xf6ffba5c"], atk_tx=["0xc8875004"], atk_block=22146341,
         gross_eth=50.885, returned_pct=82.5, fate_kind="returned",
         fate="Yoink sent 48.33 ETH to an Alkimiya-linked Safe; 6.33 ETH came back, net return 42.0 ETH.",
         one_liner="Yoink took position 0 one block before the attacker's WBTC drain, reusing the attacker's own deployed index contract; the attacker's tx reverted."),
    dict(slug="balancer-2025", block=23717398, bot="Bitfinding (whitehat)", race_type="post-failure-replay",
         bot_tx=["0x1dc60f91"], atk_tx=["0x6ed07db1"], atk_block=23717397,
         fate_kind="returned", fate="Funds returned to the Balancer DAO multisig; 10% bounty paid 2026-01-15.",
         one_liner="A whitehat replayed the attacker's creation input one block later (3 of 983 words differ) and returned the funds. Rescue of leftovers, not pre-emption."),
    dict(slug="bifi-2026", block=26210256, bot="c0ffeebabe.eth", race_type="deploy-window-copy",
         bot_addr=[C0FFEE], atk_addr=["0x7c78a049"], atk_block=None, fate_kind="unknown", fate="No return found.",
         one_liner="The attacker deployed a purpose-built contract and never called it. A tx one position into the next block emptied the market and paid the builder."),
    dict(slug="blueberry-2024", block=19287289, bot="c0ffeebabe.eth", race_type="beat-pending-attack",
         bot_addr=[C0FFEE], atk_addr=["0x0512ac94"], atk_block=19287290, gross_eth=457.685, returned_pct=95.4,
         fate_kind="returned",
         fate="The builder sent 366.5 ETH (80.1%) to the Blueberry multisig inside the same block; the bot's EOA later sent 70 ETH; the proposer got 91.04 ETH.",
         one_liner="A bot tx at index 0 landed one block before the attacker's public tx and took the market cash; the attacker's own borrows returned 0."),
    dict(slug="curve-vyper-2023", sub="pETH", block=17806056, bot="anonymous front-runner 0x6ec21d18",
         race_type="beat-pending-attack", verdict="confirmed-onchain", bot_addr=["0x6ec21d18"], atk_addr=["0x172f6fde"],
         atk_block=17806056, gross_eth=6106.65, returned_pct=90.0, fate_kind="returned",
         fate="Returned 5,495.4 WETH to JPEG'd and kept a 610.6 WETH (10%) bounty.",
         one_liner="A different address at index 0 ran a byte-copy of the attacker's code (20 bytes differ) and took 6,106.65 WETH; the attacker's own tx at index 91 reverted."),
    dict(slug="curve-vyper-2023", sub="msETH", block=17806550, make_focus="0xc93eb238ff42632525e990119d3edc7775299a70b56e54d83ec4f53736400964", bot="c0ffeebabe.eth", race_type="beat-pending-attack",
         verdict="confirmed-onchain", bot_addr=[C0FFEE], atk_addr=["0x19c7849d"], atk_block=17806552, gross_eth=866.55,
         fate_kind="unknown", fate="Return not established in this dataset.",
         one_liner="c0ffeebabe's index-0 tx took the pool funds before a second-wave actor deployed in the same block."),
    dict(slug="curve-vyper-2023", sub="CRV/ETH 2", block=17808683, bot="c0ffeebabe.eth", race_type="beat-pending-attack",
         verdict="confirmed-onchain", bot_addr=[C0FFEE], atk_addr=["0x19c7849d"], atk_block=None, gross_eth=2879.66,
         returned_pct=100.0, fate_kind="returned", fate="2,879.54 ETH returned to Curve's deployer after an on-chain message.",
         one_liner="c0ffeebabe's tx at index 7 preceded the second-wave actor's deploy at index 13 and pre-empted a pending second attack."),
    dict(slug="defiplaza-2024", block=20240539, bot="Yoink", race_type="beat-pending-attack",
         bot_addr=[YOINK], atk_addr=["0x14b362d2"], atk_tx=["0x8f029510", "0xe00b0998"], atk_block=20240540,
         fate_kind="partial",
         fate="About $23K of tokens returned; roughly 13.4 ETH of sold tokens and the 4.76 ETH builder refund stayed with Yoink's addresses. No ETH return found.",
         one_liner="The attacker's deploy and run() were seen in the public mempool 5.8 s before the slot. Yoink's builder bid 3.0 s later and won; 25 of 25 DeFi Plaza calls match byte for byte."),
    dict(slug="dodo-v2-2021", block=12000022, bot="Antelope", race_type="beat-pending-attack",
         bot_addr=["0x35541875"], atk_addr=["0x368a6558"], atk_block=12000022, fate_kind="returned",
         fate="Antelope returned 955,815 WSZO, 296,009 USDT, 114.5 ETH and more on 2021-03-10.",
         one_liner="Bot Antelope landed the attacker's init() calldata at index 4 against his index 176, one block after he staged the pool, and emptied it. His tx reverted."),
    dict(slug="earningfarm-2022", block=15746200, bot="'0xa57' bot", race_type="beat-pending-attack",
         bot_addr=["0x26bce6ec"], atk_addr=["0xdf31f4c8"], atk_block=15746200, gross_eth=480.1, returned_pct=0.0,
         fate_kind="kept", fate="480.1 ETH went to the bot owner's wallet. No return to Earning.Farm found.",
         one_liner="Index 0 with a zero priority fee and an 18.7 ETH builder payment; the attacker's later transaction reverted."),
    dict(slug="euler-copybot-2023", block=16817996, bot="anonymous copier 0x5F259D0b", race_type="deploy-window-copy",
         bot_addr=["0x5f259d0b"], atk_addr=["0xb2698c2d"], atk_block=16818013, fate_kind="n-a",
         fate="The copy sent the 8.88M DAI to a cash-out wallet hard-coded by the attacker: it captured nothing.",
         one_liner="A copier redeployed the attacker's contract with four addresses swapped and drained first, 17 blocks before the attacker's own first call (which ran out of gas)."),
    dict(slug="kelp-rseth-2026", block=25980525, bot="Yoink (gen 3)", race_type="deploy-window-copy", gross_eth=18.95017,
         bot_addr=[YOINK], atk_addr=["0x0dc2c5d6"], atk_block=None, fate_kind="returned",
         fate="About 30 h later Yoink's vault returned 2,882.37 rsETH to an owner of the victim Safe.",
         one_liner="Twelve seconds after the attacker's prepare() tx, Yoink called the attacker's own executor at position 0. The attacker's finishing tx never landed."),
    dict(slug="makina-2026", block=24273362, bot="EIP-7702 searcher 0x935bfb49", race_type="deploy-window-copy",
         bot_addr=["0x935bfb49"], atk_addr=["0x2f934b0f"], atk_block=None, gross_eth=1299.05 + 0.13, returned_pct=70.9,
         fate_kind="returned",
         fate="The builder forwarded 1,023.0 ETH; 920.7 ETH reached Makina's Safe, 102.3 ETH (10%, Safe Harbor) was kept.",
         one_liner="The attacker deployed; twelve seconds later a searcher at position 0 of the next block ran the the extraction from the public bytecode and paid 1,299 ETH to the builder."),
    dict(slug="paraswap-2024", block=19470561, bot="Yoink", race_type="bot-was-first-exploiter", bot_addr=[YOINK],
         fate_kind="partial", returned_pct=67.2, gross_eth=6.4633,
         fate="Yoink sent 4.342 ETH to the Safe Paraswap named (67% of the sale, 99.8% of its net) and declined to send the rest.",
         one_liner="No racing attacker: Yoink's index-0 tx was the first on-chain exploitation of the bug, eleven hours before anyone else."),
    dict(slug="ronin-2024", sub="Yoink", block=20468848, bot="Yoink", race_type="beat-whitehat-or-user", gross_eth=796.4115,
         bot_addr=[YOINK], atk_addr=["0x5f494a30"], atk_tx=["0xb7c3f85a"], atk_block=20468849, fate_kind="returned",
         fate="Yoink withdrew 800 ETH and 792.46 ETH reached the Ronin Safe; the reported $500K bounty is not on chain.",
         one_liner="Yoink copied a user's pending withdrawal, rewriting recipient and quantity (1,998,046.875 USDC). There is no hostile attacker: the user's own tx reverted."),
    dict(slug="ronin-2024", sub="ETH leg", block=20468679, bot="anonymous searcher 0x1a56abf4", gross_eth=3996.09375,
         race_type="beat-whitehat-or-user", bot_addr=["0x1a56abf4"], atk_tx=["0xc78fb8cd"], atk_block=20468888,
         fate_kind="returned", fate="4,000 ETH returned at 10:00:59, before Ronin's first on-chain message.",
         one_liner="A searcher copied a user's 0.35 WETH withdrawal, changing 2 of 76 calldata words, and took 3,996.09 ETH."),
    dict(slug="ronin-2024", sub="racer 3", block=20468790, bot="anonymous searcher 0x00001b0b",
         race_type="beat-whitehat-or-user", bot_addr=["0x00001b0b"], atk_tx=["0x56439c"], atk_block=20468790,
         fate_kind="unknown", fate="Not traced.",
         one_liner="A third searcher copied a user's withdrawal with one word changed and paid the Titan builder through a 2.175 ETH priority fee."),
    dict(slug="saddle-2022", block=14684434, bot="BlockSec whitehat", race_type="post-failure-replay",
         bot_addr=["0x811929c3"], atk_addr=["0x63341ba9"], atk_block=14684432, returned_pct=100.0, fate_kind="returned",
         fate="All 1,356.73 WETH returned to Saddle.",
         one_liner="A rescue contract replayed the attacker's reverted second attempt two blocks later (20 bytes differ). A rescue of what the attacker left behind."),
    dict(slug="securedfinance-2026", block=25914192, bot="c0ffeebabe.eth", race_type="post-failure-replay",
         bot_addr=[C0FFEE], atk_addr=["0xd3ac7b3a"], atk_block=25914188, fate_kind="kept",
         fate="28.837 of 28.85 ETH went to the builder; the bot kept 0.0115 ETH. No return found or needed.",
         one_liner="The attacker's tx landed and ran out of gas. Four blocks later a bot completed the extraction and sold about 0.9 WBTC."),
    dict(slug="shoco-2023", block=16440979, bot="generic searcher 0xE71ACA93", race_type="beat-pending-attack",
         bot_addr=["0xe71aca93"], atk_addr=["0x14d8ada7"], atk_block=16440979, gross_eth=4.1589, returned_pct=0.0,
         fate_kind="kept", fate="Funds stayed in the bot contract: no return, no bounty.",
         one_liner="A bot at position 0 ran adapted victim calls (own capital, no flash loan) and took 4.16 ETH; the attacker's tx at position 15 of the same block reverted."),
    dict(slug="sushi-rp2-2023", block=17007838, bot="Yoink", race_type="beat-whitehat-or-user", bot_addr=[YOINK],
         atk_tx=["0x43ff7e01"], atk_block=17007839, fate_kind="returned",
         fate="875 ETH of 1,800 WETH was returned via the Sushi multisig; Yoink 380, c0ffeebabe 305.3, Trust 90, BlockSec 100.",
         one_liner="Yoink pulled 100 WETH one block before the tx everyone calls the attack, which was a whitehat's with a max fee below that block's base fee."),
    dict(slug="time-2023", block=18730463, bot="Yoink", race_type="bot-was-first-exploiter", bot_addr=[YOINK],
         fate_kind="kept", fate="No hacker tx exists; Yoink's net profit is the published loss.",
         one_liner="The tx every report calls the attack is Yoink's own: no separate attacker tx exists."),
    dict(slug="transitswap-2022", block=15655281, bot="Yoink (gen 0)", race_type="beat-pending-attack",
         bot_addr=[YOINK, "0x6c6b87d4"], bot_tx=["0x9f43b61d"], atk_addr=["0x5f0b31aa"], atk_tx=["0x6f7d546a"], atk_block=15655281,
         gross_eth=29.3065, returned_pct=90.4, fate_kind="returned",
         fate="Exactly 26.505 ETH was sent to Transit eleven months later (2023-09-06).",
         one_liner="Yoink's tx at index 24 landed ahead of the attacker's last transaction, tipping 2 wei over its 3.0 gwei; that transaction reverted."),
    dict(slug="uncx-2026", block=26191920, bot="Yoink", race_type="beat-pending-attack", bot_addr=[YOINK],
         atk_addr=["0x78c9b118"], atk_block=26191921, fate_kind="partial",
         fate="Yoink's vault returned 8.10 ETH and 82.1M X, keeping exactly 20M X.",
         one_liner="Yoink's X-token drain landed one block before the attacker's transaction, which reverted."),
]

TITLES = {
    "curve-vyper-2023--aleth": "Curve / Vyper: alETH pool", "curve-vyper-2023--crv-eth-wave1": "Curve / Vyper: CRV/ETH pool, first wave",
    "uncx-2026--zc-copiers": "UNCX: the ZC-token copiers",
    "alkimiya-2025": "Alkimiya SilicaPools", "balancer-2025": "Balancer v2 (whitehat rescue)", "bifi-2026": "BiFi Lending",
    "blueberry-2024": "Blueberry Protocol", "curve-vyper-2023--peth": "Curve / Vyper: pETH pool",
    "curve-vyper-2023--mseth": "Curve / Vyper: msETH pool", "curve-vyper-2023--crv-eth-2": "Curve / Vyper: CRV/ETH pool",
    "defiplaza-2024": "DeFi Plaza", "dodo-v2-2021": "DODO V2", "earningfarm-2022": "Earning.Farm",
    "euler-copybot-2023": "Euler Finance (copied contract)", "kelp-rseth-2026": "Kelp rsETH holder Safe", "makina-2026": "Makina",
    "paraswap-2024": "Paraswap Augustus V6", "ronin-2024--yoink": "Ronin bridge: Yoink's copy",
    "ronin-2024--eth-leg": "Ronin bridge: ETH-leg copy", "ronin-2024--racer-3": "Ronin bridge: third copy",
    "saddle-2022": "Saddle Finance", "securedfinance-2026": "Secured Finance", "shoco-2023": "SHOCO token",
    "sushi-rp2-2023": "SushiSwap RouteProcessor2", "time-2023": "TIME token", "transitswap-2022": "Transit Swap",
    "uncx-2026": "UNCX token vesting",
}

HEX40 = re.compile(r"0x[0-9a-fA-F]{40}")
HEX64 = re.compile(r"0x[0-9a-fA-F]{64}")

# --------------------------------------------------------------------------------------------------------------
# c0ffeebabe.eth policy (publication policy): only public actions (which tx, which block, funds returned) are published.
#   * no per-transaction files (tx_/receipt_/trace_) of its transactions in site/raw: block-level files only
#   * trace_block files that contain its transactions are republished redacted (call trees removed; only the ETH
#     transfers to the block's fee recipient, i.e. the builder payment, are kept)
#   * Etherscan account lists of its EOA are republished as extracts holding only the cited rows
#   * no call-level text (selectors, call counts, "transaction-level call details") in narratives, events or one-liners
C0_EOA = "0xc0ffeebabe5d496b2dde509f9fa189c25cf29671"
C0_TX_PREFIX = ("0x4b3c70d0", "0x756c6805", "0x48618b87", "0x28be1d72",      # BiFi
                "0xf0464b01",                                   # Blueberry
                "0xc93eb238", "0xcd99fadd",                     # Curve msETH, CRV/ETH wave 2
                "0xcd615986", "0x5419ffb4", "0xc92d5c49",       # Secured Finance
                "0xf57b7dbf",                                   # UNCX ZC copier
                "0x04b166e7", "0xbb9aac79", "0x11d069cb",      # Sushi RP2 (three txs)
                "0x22a4bdce")                                  # Meta Pool later transaction
C0_REDACT_NOTE = ("Redacted by the publisher (publication policy: no per-transaction analysis of c0ffeebabe.eth). Call trees of "
                  "transactions sent by that address are removed; only ETH transfers to the block's fee recipient (the "
                  "builder payment) are kept. All other transactions are verbatim.")


def is_c0_pertx(path):
    m = re.search(r"(0x[0-9a-fA-F]{64})", os.path.basename(path or ""))
    return bool(m and m.group(1).lower().startswith(C0_TX_PREFIX))


def is_c0_list(path):
    return "0xc0ffeeba" in os.path.basename(path or "").lower()


FILTER_NEED = {}       # data/raw/etherscan/<c0 account list> -> set(cited tx hashes)


# ------------------------------------------------------------------------------------------------ helpers
def jload(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def short(a, n=6, m=4):
    a = a or ""
    return a if len(a) <= n + m + 2 else f"{a[:n + 2]}…{a[-m:]}"


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def rid(spec):
    return spec["slug"] + (("--" + slugify(spec["sub"])) if spec.get("sub") else "")


def f(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def wei_eth(w):
    try:
        return int(w) / 1e18
    except Exception:
        return 0.0


def rnd(x, n=4):
    return None if x is None else round(x, n)


def clean_name(x):
    if not x:
        return None
    x = str(x)
    if any((ord(c) < 32 or 127 <= ord(c) < 160 or c == "\ufffd") for c in x):
        return None
    return x


def norm_verdict(v):
    v = (v or "").lower()
    if v.startswith("confirmed"):
        return "confirmed-onchain"
    if v.startswith("related"):
        return "related-not-frontrun"
    if v.startswith("reject"):
        return "rejected"
    if v.startswith("reported"):
        return "reported"
    return v.split()[0] if v else "unknown"


# raw registry ----------------------------------------------------------------------------------------------
MANIFEST = {}
RAW_USED = {}          # data/raw/... path -> site url
MEMPOOL_NEED = {}      # data/raw/mempool-dumpster/<file>.zip -> set(hashes)
MEMPOOL_FOUND = {}     # site url of a mempool extract -> hashes that really have rows in it
MEMPOOL_CACHE = {}     # verified small extracts reused when source digest and cited hashes are unchanged


def load_manifest():
    p = ROOT / "data/raw/MANIFEST.jsonl"
    if not p.exists():
        return
    with open(p) as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("path"):
                MANIFEST[d["path"]] = d


DEAD_RAW = {}          # data/raw path -> why it is not published (empty body / HTTP error text from a retired relay)


def dead_reason(path):
    """None when the saved response is usable; else a short reason (empty body, error text, non-2xx status)."""
    p = ROOT / path
    try:
        sz = p.stat().st_size
    except OSError:
        return "file missing"
    mf = MANIFEST.get(path, {})
    st = mf.get("status")
    when = (mf.get("retrieved_at") or "")[:10]
    if sz == 0:
        return "empty body (HTTP %s when queried %s)" % (st if st is not None else "?", when)
    if sz < 200 and path.endswith(".json"):
        try:
            json.loads(p.read_bytes())
        except Exception:
            return "error text, not JSON (HTTP %s when queried %s): %r" % (st if st is not None else "?", when, p.read_bytes()[:40].decode("utf-8", "replace"))
    if isinstance(st, int) and st >= 400:
        return "HTTP %s when queried %s" % (st, when)
    return None


def raw(path, hashes=None):
    """Register a data/raw path; return its site URL (relative to site/) or None when not publishable."""
    if not path or not isinstance(path, str):
        return None
    path = path.strip()
    if path.endswith("/seal_safeharbor_overview.html"):
        return None
    if not path.startswith("data/raw/"):
        return None
    if not (ROOT / path).is_file():
        return None
    why = dead_reason(path)
    if why:
        DEAD_RAW[path] = why
        return None                                  # never publish a saved error body / empty file as evidence
    if is_c0_pertx(path):
        return None                                  # c0ffeebabe.eth: block-level evidence only
    if is_c0_list(path):
        FILTER_NEED.setdefault(path, set()).update(h.lower() for h in (hashes or []))
    rel = path[len("data/raw/"):]
    if rel.startswith("mempool-dumpster/") and path.endswith(".zip"):
        url = "raw/" + rel[: -len(".zip")] + ".rows.csv"
        MEMPOOL_NEED.setdefault(path, set()).update(hashes or [])
        RAW_USED[path] = url
        return url
    url = "raw/" + rel
    RAW_USED[path] = url
    return url


# ------------------------------------------------------------------------------------------------ load sources
def load_incident_sources(slug):
    base = ROOT / "incidents" / slug
    inc = jload(base / "incident.json") or {}
    tl = jload(base / "timeline.json")
    events = []
    if isinstance(tl, dict):
        events = tl.get("events") or []
    elif isinstance(tl, list):
        events = tl
    races = {}
    for p in sorted(glob.glob(str(base / "race*.json"))):
        d = jload(p)
        if not isinstance(d, dict) or "block" not in d:
            continue
        n = d["block"].get("number")
        if n is None:
            continue
        old = races.get(n)
        if old is None or len(d.get("bids") or []) >= len(old.get("bids") or []):
            races[n] = d
    return inc, events, races


def ensure_race(slug, races, spec):
    """Some bot blocks have no incidents/<slug>/race_*.json (Curve msETH, block 17806550). Rebuild the doc with the
    project's own scripts/blockrace.py (reads the cached raw responses) into data/cache/site-races/, not into incidents/."""
    if spec["block"] in races or not spec.get("make_focus"):
        return
    cache = ROOT / "data/cache/site-races"
    cache.mkdir(parents=True, exist_ok=True)
    p = cache / f"{slug}_{spec['block']}.json"
    if not p.exists():
        import subprocess
        cmd = [sys.executable, str(ROOT / "scripts/blockrace.py"), str(spec["block"]), "--focus", spec["make_focus"],
               "--slug", slug, "--out", str(p)]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            print("  !! blockrace failed:", r.stderr[-300:], file=sys.stderr)
    d = jload(p)
    if isinstance(d, dict) and "block" in d:
        races[spec["block"]] = d


def consolidated():
    p = ROOT / "data/incidents.json"
    d = scrub_public(jload(p))
    if isinstance(d, dict):
        d = d.get("incidents") or d.get("rows") or []
    return d if isinstance(d, list) else None


# ------------------------------------------------------------------------------------------------ bids
def thin_record(rec, cap):
    """Keep the record curve under `cap` points, dropping the smallest relative increments first."""
    rec = list(rec)
    while len(rec) > cap:
        best, bi = None, None
        for i in range(1, len(rec) - 1):
            inc = (rec[i][1] - rec[i - 1][1]) / max(rec[i - 1][1], 1e-9)
            if best is None or inc < best:
                best, bi = inc, i
        rec.pop(bi)
    return rec


def process_bids(doc, t0, winner_hash):
    bids = [b for b in (doc.get("bids") or []) if b.get("value_eth") is not None and b.get("timestamp_ms")]
    if not bids:
        return None
    bids.sort(key=lambda b: b["timestamp_ms"])
    builders, bidx = [], {}

    def bi(name):
        name = name or "unknown"
        if name not in bidx:
            bidx[name] = len(builders)
            builders.append(name)
        return bidx[name]

    # record curve over all bids (all relays), then flags
    rec, best = [], -1.0
    recset = set()
    for i, b in enumerate(bids):
        v = float(b["value_eth"])
        if v > best:
            best = v
            rec.append([b["timestamp_ms"] - t0, v, bi(b.get("builder_name")), b.get("block_hash")])
            recset.add(i)
    # selection for the dot plot
    sel = set(recset)
    for i, b in enumerate(bids):
        if b.get("block_hash") == winner_hash or b.get("is_winning_block"):
            sel.add(i)
    if len(sel) < MAX_BIDS:
        # biggest bid of each builder in each 250 ms bucket => keeps the shape of every builder's ladder
        bucket = {}
        for i, b in enumerate(bids):
            k = (b.get("builder_name"), (b["timestamp_ms"] - t0) // 250)
            if k not in bucket or float(b["value_eth"]) > float(bids[bucket[k]]["value_eth"]):
                bucket[k] = i
        cand = sorted(bucket.values(), key=lambda i: -float(bids[i]["value_eth"]))
        for i in cand:
            if len(sel) >= MAX_BIDS:
                break
            sel.add(i)
    if len(sel) < MAX_BIDS and len(bids) > len(sel):
        rest = [i for i in range(len(bids)) if i not in sel]
        step = max(1, len(rest) // (MAX_BIDS - len(sel)))
        for i in rest[::step]:
            if len(sel) >= MAX_BIDS:
                break
            sel.add(i)
    out = []
    for i in sorted(sel):
        b = bids[i]
        flag = (1 if (b.get("block_hash") == winner_hash or b.get("is_winning_block")) else 0) | (2 if i in recset else 0)
        out.append([b["timestamp_ms"] - t0, rnd(float(b["value_eth"]), 5), bi(b.get("builder_name")), flag,
                    b.get("num_tx"), (b.get("block_hash") or "")[:12]])
    record = thin_record([[r[0], rnd(r[1], 5), r[2], r[3][:12] if r[3] else ""] for r in rec], MAX_RECORD)
    vals = [float(b["value_eth"]) for b in bids]
    return dict(n_total=len(bids), n_shown=len(out), n_offslot=int((doc.get("bid_summary") or {}).get("n_offslot_excluded") or 0),
                builders=builders, series=out, record=record,
                first_ms=bids[0]["timestamp_ms"] - t0, last_ms=bids[-1]["timestamp_ms"] - t0,
                max_eth=rnd(max(vals), 5), median_eth=rnd(statistics.median(vals), 5),
                relays=sorted({b.get("relay") for b in bids if b.get("relay")}))


def first_reaction(bids_raw, t0, seen_rel, winner_name):
    """First bid after the attacker's tx was first seen that looks like a reaction (see delay_method)."""
    bids = sorted([b for b in bids_raw if b.get("value_eth") is not None and b.get("timestamp_ms")],
                  key=lambda b: b["timestamp_ms"])
    if not bids or seen_rel is None:
        return None, None
    pre = [float(b["value_eth"]) for b in bids if b["timestamp_ms"] - t0 < seen_rel]
    if winner_name == YOINK_BUILDER:
        for b in bids:
            if b.get("builder_name") == YOINK_BUILDER and b["timestamp_ms"] - t0 >= seen_rel:
                return b, "first bid from the winning builder (Yoink's) after first sight"
        return None, None
    base = statistics.median(pre) if pre else 0.0
    mx = max(pre) if pre else 0.0
    thr = max(0.1, 10 * base, 3 * mx)
    for b in bids:
        if b["timestamp_ms"] - t0 >= seen_rel and float(b["value_eth"]) >= thr:
            return b, f"first bid after first sight at least 10x the pre-sight median ({base:.3g} ETH) and 3x the pre-sight max"
    return None, None


# ------------------------------------------------------------------------------------------------ one race
def build_race(spec, inc, events, races, cons_row):
    rid_ = rid(spec)
    doc = races.get(spec["block"])
    if not doc:
        print(f"  !! {rid_}: no race doc for block {spec['block']}", file=sys.stderr)
        return None, None
    blk = doc["block"]
    pre_merge = blk.get("slot") is None
    t0 = (blk.get("slot_start_unix") or blk["timestamp"]) * 1000
    fee_rec = (blk.get("fee_recipient") or "").lower()
    txs = doc.get("txs") or []
    watch = [a.lower() for a in (doc.get("watch_addresses") or [])]

    bot_addr = [a.lower() for a in spec.get("bot_addr", [])]
    bot_tx = [a.lower() for a in spec.get("bot_tx", [])]
    atk_addr = [a.lower() for a in spec.get("atk_addr", [])]
    atk_tx = [a.lower() for a in spec.get("atk_tx", [])]

    def role_of(t):
        h = (t.get("hash") or "").lower()
        fr = (t.get("from") or "").lower()
        if any(h.startswith(p) for p in bot_tx) or any(fr.startswith(p) for p in bot_addr):
            return "bot"
        if any(h.startswith(p) for p in atk_tx) or any(fr.startswith(p) for p in atk_addr):
            return "attacker"
        if fr == fee_rec and wei_eth(t.get("value_wei")) > 0:
            return "builder"
        return None

    bot_contracts = sorted({(t.get("to") or "").lower() for t in txs if role_of(t) == "bot" and t.get("to")})
    block_tx = []
    ntx = len(txs)
    notable_idx = set()
    for t in txs:
        r = role_of(t)
        cb = wei_eth(t.get("coinbase_transfer_wei"))
        if r is None and cb >= 0.05:
            r = "bribe"  # another searcher paying the builder directly
        if r is None and t.get("focus"):
            r = "focus"
        t["_role"] = r
        if r:
            notable_idx.add(t["index"])
    # compact strip for every tx, detail for the notable ones
    strip = []
    for t in txs:
        tip = t.get("priority_fee_gwei")
        if tip is None:
            tip = t.get("gas_price_gwei")
        strip.append([t["index"], 1 if t.get("status") == 1 else 0, t["_role"] or "", rnd(f(tip, 0), 3),
                      rnd(wei_eth(t.get("coinbase_transfer_wei")), 4)])
    notable = []
    block_ref = raw(doc.get("raw_refs", {}).get("block"))
    rcpt_ref = raw(doc.get("raw_refs", {}).get("receipts"))
    trace_ref = raw(doc.get("raw_refs", {}).get("traces"))
    for t in txs:
        if t["index"] not in notable_idx:
            continue
        v = wei_eth(t.get("value_wei"))
        to = (t.get("to") or "").lower()
        label = None
        if t["_role"] == "builder":
            label = "builder payout"
            if to in bot_contracts or any(to.startswith(p) for p in bot_addr):
                label = "builder refund to the bot"
        notable.append(dict(i=t["index"], h=t["hash"], from_=t.get("from"), to=t.get("to"), role=t["_role"],
                            ok=t.get("status") == 1, value_eth=rnd(v, 6), cb_eth=rnd(wei_eth(t.get("coinbase_transfer_wei")), 6),
                            sel=t.get("selector"), gas=t.get("gas_used"), tip=f(t.get("priority_fee_gwei"), f(t.get("gas_price_gwei"))),
                            err=t.get("trace_top_error"), label=label,
                            bundle_like=t.get("inferred_bundle_like"),
                            raw=dict(tx=block_ref, receipt=rcpt_ref, trace=trace_ref)))

    # ---- flows (where the loot went) -------------------------------------------------------------
    bot_txs = [t for t in txs if t["_role"] == "bot"]
    focus_set = {x.lower() for x in (doc.get("focus_txs") or [])}
    primary = next((t for t in bot_txs if t["hash"].lower() in focus_set), bot_txs[0] if bot_txs else None)
    primary_cb = wei_eth(primary.get("coinbase_transfer_wei")) if primary else 0.0
    coinbase_all = sum(wei_eth(t.get("coinbase_transfer_wei")) for t in bot_txs)
    coinbase = primary_cb
    bot_prio = sum(wei_eth(t.get("priority_fee_total_wei")) for t in bot_txs)
    winner = doc.get("winner") or {}
    prop_eth = f(winner.get("bid_value_eth"))
    prop_tx_hash = ((winner.get("proposer_payment_tx") or {}).get("hash") or "").lower()
    payouts, refund_bot, refund_other = [], 0.0, 0.0
    for t in txs:
        if t["_role"] == "builder":
            v = wei_eth(t.get("value_wei"))
            to = (t.get("to") or "").lower()
            if t["hash"].lower() == prop_tx_hash or (prop_eth and abs(v - prop_eth) < 1e-6):
                continue
            if to in bot_contracts or any(to.startswith(p) for p in bot_addr):
                refund_bot += v
            else:
                refund_other += v
            payouts.append(dict(i=t["index"], h=t["hash"], to=t.get("to"), eth=rnd(v, 6),
                                kind="refund to the bot" if (to in bot_contracts or any(to.startswith(p) for p in bot_addr)) else "payout to another address"))
    total_in = coinbase_all + bot_prio
    kept = total_in - (prop_eth or 0) - refund_bot - refund_other if total_in else None
    flows = dict(bot_coinbase_eth=rnd(coinbase_all, 6), primary_coinbase_eth=rnd(primary_cb, 6), n_bot_txs=len(bot_txs), bot_priority_fee_eth=rnd(bot_prio, 6), proposer_eth=rnd(prop_eth, 6),
                 refund_to_bot_eth=rnd(refund_bot, 6), payout_other_eth=rnd(refund_other, 6),
                 builder_kept_eth=rnd(max(kept, 0), 6) if kept is not None else None, payouts=payouts,
                 meaningful=bool(coinbase_all > 0.01 or refund_bot > 0.01),
                 proposer_payment_tx=prop_tx_hash or None, fee_recipient=blk.get("fee_recipient"),
                 builder_name=blk.get("extra_data_name"))

    # ---- mempool --------------------------------------------------------------------------------
    hash_to_tx = {}
    for d in races.values():
        for t in d.get("txs") or []:
            hash_to_tx.setdefault(t["hash"].lower(), (t, d))
    mem_entries = {}
    cov_info = None
    for d in races.values():
        m = d.get("mempool") or {}
        if d is doc:
            cov_info = m.get("coverage")
        for h, e in (m.get("txs") or {}).items():
            mem_entries.setdefault(h.lower(), (e, m, d))
    mem_out = []
    rel_all_hashes = set(mem_entries.keys())
    for h, (e, m, d) in mem_entries.items():
        tx, td = hash_to_tx.get(h, (None, None))
        r = role_of(tx) if tx else None
        if r is None and tx is None:
            r = "bot" if any(h.startswith(p) for p in bot_tx) else "attacker" if any(h.startswith(p) for p in atk_tx) else None
        if r is None and tx is not None and tx.get("focus"):
            r = "focus"
        blockn = (td or d)["block"]["number"] if (td or d) else None
        item = dict(h=h, role=r, block=blockn, idx=tx["index"] if tx else None)
        if e.get("first_seen_ms"):
            item.update(seen=True, t_ms=e["first_seen_ms"], rel_ms=e["first_seen_ms"] - t0,
                        sources=[dict(s=x["source"], t=x["first_seen_ms"]) for x in (e.get("per_source_first_seen") or [])],
                        incl_block=e.get("included_at_block"), delay_ms=e.get("inclusion_delay_ms"))
            rr = e.get("raw_refs") or {}
            item["raw"] = dict(csv=raw(rr.get("tx_csv"), [h]), sourcelog=raw(rr.get("sourcelog"), [h]),
                               summary=raw(rr.get("summary")))
        else:
            item.update(seen=False, note=e.get("note"))
            item["raw"] = dict(index=raw(((m.get("coverage") or {}).get("index_raw"))))
        mem_out.append(item)
    covered = bool(cov_info and cov_info.get("covered"))
    seen_atk = [x for x in mem_out if x.get("seen") and x.get("role") == "attacker"]
    pending_atk = [x for x in seen_atk if (x.get("incl_block") is None or x["incl_block"] >= blk["number"])]
    if seen_atk:
        mstate = "measured"
    elif covered:
        mstate = "absent-from-archive"
    else:
        mstate = "in-block-only"
    mnote = {
        "measured": "First-seen times come from the Flashbots mempool-dumpster (several independent sources).",
        "absent-from-archive": "The mempool archive covers this day, but none of the cited txs was seen before inclusion. That means private order flow or missed by every source.",
        "in-block-only": "In-block evidence only: no public mempool archive for this date.",
    }[mstate]
    if cov_info and cov_info.get("reason") and mstate == "in-block-only":
        mnote += " (" + cov_info["reason"] + ")"
    mempool = dict(state=mstate, note=mnote, covered=covered, entries=sorted(mem_out, key=lambda x: x.get("t_ms") or 9e18),
                   coverage_raw=raw((cov_info or {}).get("index_raw")))

    # ---- attacker first seen -> reaction
    seen_rel = None
    if pending_atk and spec["race_type"] in ("beat-pending-attack", "deploy-window-copy", "beat-whitehat-or-user"):
        seen_rel = min(x["rel_ms"] for x in pending_atk)
    delay = None
    rbid = None
    method = None
    if seen_rel is not None and doc.get("bids"):
        rbid, method = first_reaction(doc["bids"], t0, seen_rel, winner.get("builder_name"))
        if rbid:
            delay = rbid["timestamp_ms"] - t0 - seen_rel

    # ---- auction -------------------------------------------------------------------------------------
    winner_hash = None
    for d_ in doc.get("delivered") or []:
        winner_hash = d_.get("block_hash")
        break
    bids = process_bids(doc, t0, winner_hash)
    rs = doc.get("relays_status") or {}
    answered = {}
    for k, v in rs.items():
        rb_, rd_ = raw(v.get("raw_bids")), raw(v.get("raw_delivered"))
        gone = None
        for pth_, got_ in ((v.get("raw_bids"), rb_), (v.get("raw_delivered"), rd_)):
            if pth_ and got_ is None and pth_ in DEAD_RAW:
                gone = "relay no longer serves this: " + DEAD_RAW[pth_] + "; nothing to link"
                break
        answered[k] = dict(delivered=v.get("delivered_n"), bids=v.get("bids_n"), http=v.get("bids_http"), note=v.get("note"),
                           error=v.get("error"), raw_bids=rb_, raw_delivered=rd_, retired=gone)
    auction = None
    if bids or doc.get("delivered"):
        auction = dict(
            bids=bids, relays=answered,
            winner=dict(builder=winner.get("builder_name"), eth=rnd(prop_eth, 6), relays=winner.get("delivered_by_relays"),
                        hash=winner_hash, t_ms=None, pubkey=winner.get("builder_pubkey"),
                        fee_recipient=winner.get("proposer_fee_recipient")),
            raw=dict(delivered=raw(((rs.get("flashbots") or {}).get("raw_delivered")) if (rs.get("flashbots") or {}).get("delivered_n") else None)),
            n_builders=(doc.get("bid_summary") or {}).get("n_builders"))
        # winning bid time
        wb = [b for b in (doc.get("bids") or []) if b.get("block_hash") == winner_hash]
        if wb:
            auction["winner"]["t_ms"] = max(b["timestamp_ms"] for b in wb) - t0
            auction["winner"]["eth_bid"] = rnd(max(float(b["value_eth"]) for b in wb), 6)
        # relay raw files for chosen answers
        for k, v in answered.items():
            if v.get("delivered") and v.get("raw_delivered"):
                auction["raw"]["delivered"] = v["raw_delivered"]
                break
        auction["raw"]["bids"] = next((v["raw_bids"] for k, v in answered.items() if v.get("bids") and v.get("raw_bids")), None)
        # every relay file that holds bids: the totals, the chart and the record ledger are drawn from all of them
        auction["raw"]["bids_all"] = [dict(relay=k, url=v["raw_bids"], n=v["bids"], capped=(v["bids"] == 500)) for k, v in answered.items() if v.get("bids") and v.get("raw_bids")]
        # the relay data API returns at most 500 rows per request (limit=10000 answers HTTP 400): a 500-row file is a lower bound
        auction["raw"]["capped"] = [x["relay"] for x in auction["raw"]["bids_all"] if x["capped"]]
        auction["raw"]["delivered_all"] = [dict(relay=k, url=v["raw_delivered"], n=v["delivered"]) for k, v in answered.items() if v.get("delivered") and v.get("raw_delivered")]
        runner = None
        if bids:
            wpk_ = (winner.get("builder_pubkey") or "").lower()
            others = [b for b in (doc.get("bids") or []) if b.get("value_eth") is not None and (b.get("builder_pubkey") or "").lower() != wpk_
                      and not (b.get("builder_name") and b.get("builder_name") == winner.get("builder_name"))]
            if others:
                rb = max(others, key=lambda b: float(b["value_eth"]))
                runner = dict(builder=rb.get("builder_name") or ("unnamed builder " + (rb.get("builder_pubkey") or "")[:10] + "..."),
                              eth=rnd(float(rb["value_eth"]), 6), t_ms=rb["timestamp_ms"] - t0)
        auction["runner_up"] = runner
    pm = doc.get("premerge") or {}
    gas_lane = pm_note = None
    if pre_merge:
        pm_note = pm.get("note")
    # ---- other-block context: where the attacker's own call landed
    atk_idx = None
    atk_block = spec.get("atk_block")
    ab_doc = races.get(atk_block) if atk_block else None
    for d in ([ab_doc] if ab_doc else []) + [doc]:
        for t in d.get("txs") or []:
            if role_of(t) == "attacker" and (d["block"]["number"] == atk_block or d is doc and atk_block == blk["number"]):
                if atk_idx is None or t.get("status") == 0:
                    atk_idx = t["index"]
    next_block = None
    if ab_doc is not None and atk_block != blk["number"]:
        nb = ab_doc["block"]
        nb_notable = []
        for t in ab_doc.get("txs") or []:
            rr = role_of(t)
            if rr in ("attacker", "bot"):
                nb_notable.append(dict(i=t["index"], h=t["hash"], role=rr, ok=t.get("status") == 1, from_=t.get("from"),
                                       to=t.get("to"), tip=f(t.get("priority_fee_gwei"), f(t.get("gas_price_gwei"))),
                                       value_eth=rnd(wei_eth(t.get("value_wei")), 6), err=t.get("trace_top_error")))
        next_block = dict(number=nb["number"], ts_ms=nb["timestamp"] * 1000, ntx=nb.get("tx_count"), builder=clean_name(nb.get("extra_data_name")),
                          notable=nb_notable, raw=dict(block=raw((ab_doc.get("raw_refs") or {}).get("block")),
                                                       receipts=raw((ab_doc.get("raw_refs") or {}).get("receipts")),
                                                       trace=raw((ab_doc.get("raw_refs") or {}).get("traces"))))
    bot_idx = next((t["index"] for t in txs if t["_role"] == "bot"), None)
    blocks_ahead = None
    if atk_block is not None:
        blocks_ahead = atk_block - blk["number"]

    # ---- events ----------------------------------------------------------------------------------------
    multi = sum(1 for s in SPEC if s["slug"] == spec["slug"]) > 1
    main_hashes = {(t.get("hash") or "").lower() for t in txs}
    evs = []
    def event_url(rr, e):
        """One timeline raw_ref (a data/raw path, or a race_N.json doc standing for its saved block) -> site URL or None."""
        if not isinstance(rr, str):
            return None
        if rr.startswith("data/raw/"):
            url = raw(rr, HEX64.findall(e.get("tx") or ""))
            if url is None and is_c0_pertx(rr) and any(h.lower() in main_hashes for h in HEX64.findall(e.get("tx") or "")):
                url = trace_ref          # block-level (redacted) trace instead of the per-tx trace
            elif url is None and is_c0_pertx(rr) and str(e.get("block") or "").isdigit() and (ROOT / f"data/raw/rpc/trace_block_{e['block']}.json").exists():
                url = raw(f"data/raw/rpc/trace_block_{e['block']}.json", [])   # its block's trace, call trees of c0ffeebabe.eth cut on copy
            return url
        m = re.search(r"race_(\d+)\.json", rr)
        if m and races.get(int(m.group(1))):
            return raw((races[int(m.group(1))].get("raw_refs") or {}).get("block"))
        return None

    tl_notes = []
    for e in events:
        t = e.get("t_utc_ms")
        k = e.get("kind")
        if k == "bid":
            continue
        if not e.get("detail") and e.get("note"):
            tl_notes.append(e["note"])           # a note about the timeline itself, not an event: no time, no value, no raw link
            continue
        if multi and t is not None and not (t0 - 6 * 3600e3 <= t <= t0 + 60 * 3600e3):
            continue
        rr = e.get("raw_ref")
        allrefs = ([rr] if isinstance(rr, str) else list(rr or [])) + [x for x in (e.get("raw_refs") or [])]
        urls = []
        for r_ in allrefs:
            u_ = event_url(r_, e)
            if u_ and u_ not in urls:
                urls.append(u_)
        if not urls and k in ("tx", "payment", "payout", "return", "fund") and str(e.get("block") or "") == str(blk["number"]) and "web" not in str(rr):
            if block_ref:
                urls.append(block_ref)   # same block as the race: its saved block file backs the position/hash
        if not urls and e.get("tx"):
            # Timeline sources may name an analysis file that is excluded from publication.
            # Prefer the saved transaction response; c0 transactions always use block-level evidence.
            hashes = HEX64.findall(e["tx"])
            eb = e.get("block")
            for txhash in hashes:
                candidates = []
                if not txhash.lower().startswith(C0_TX_PREFIX):
                    candidates.extend(sorted((ROOT / "data/raw/rpc").glob("*" + txhash + "*.json")))
                if str(eb or "").isdigit():
                    candidates.extend(ROOT / "data/raw/rpc" / name for name in
                                      (f"block_{eb}.json", f"receipts_{eb}.json", f"trace_block_{eb}.json"))
                for source in candidates:
                    url = raw(source.relative_to(ROOT).as_posix(), [txhash])
                    if url and url not in urls:
                        urls.append(url)
        evs.append(dict(t=t, utc=e.get("utc") or e.get("t_utc"), prec=e.get("precision"), kind=k, actor=e.get("actor"),
                        detail=e.get("detail"), tx=e.get("tx"), block=e.get("block"), raw=(urls[0] if urls else None), raws=urls,
                        raw_note=(None if urls else e.get("raw_note")), derived=(e.get("derived") or None)))
    evs.sort(key=lambda e: (e["t"] is None, e["t"] or 0))

    # raw refs from incident.json: collect only bot-independent evidence (never c0ffeebabe call traces)
    inc_raw = {}
    for k, v in (inc.get("raw_refs") or {}).items():
        if isinstance(v, str) and v.startswith("data/raw/"):
            if "c0ffee" in (spec["bot"] or "").lower() and re.search(r"bot.*(trace|calldata|input)", k):
                continue
            if is_c0_pertx(v) or is_c0_list(v):
                continue
            u = raw(v, [])
            if u:
                inc_raw[k] = u

    # ---- summary numbers
    pct_builder = None
    ge = spec.get("gross_eth")
    if cons_row and (cons_row.get("loot") or {}).get("captured_native"):
        ge = f(cons_row["loot"]["captured_native"], ge)
    if ge and coinbase:
        pct_builder = rnd(min(100.0, 100 * coinbase / ge), 2 if (coinbase / ge > 0.98 or coinbase / ge < 0.01) else 1)
    spark = []
    if bids:
        r = bids["record"]
        step = max(1, len(r) // 40)
        spark = [[x[0], x[1]] for x in r[::step]]
        if r and spark[-1] != [r[-1][0], r[-1][1]]:
            spark.append([r[-1][0], r[-1][1]])
    attacker_seen_ms = (t0 + seen_rel) if seen_rel is not None else None

    detail = dict(
        id=rid_, slug=spec["slug"], sub=spec.get("sub"),
        name=inc.get("name") or spec["slug"], date=inc.get("date"), one_liner=spec.get("one_liner"),
        bot=spec["bot"], race_type=spec["race_type"], narrative=inc.get("verdict_reason"),
        chain=inc.get("chain", "ethereum"),
        verdict=spec.get("verdict") or norm_verdict(inc.get("verdict")),
        t0_ms=t0, pre_merge=pre_merge, premerge_note=pm_note, slot=blk.get("slot"),
        block=dict(number=blk["number"], hash=blk.get("hash"), ts_ms=blk["timestamp"] * 1000, ntx=blk.get("tx_count"),
                   builder=clean_name(blk.get("extra_data_name")), fee_recipient=blk.get("fee_recipient"), gas_used=blk.get("gas_used"),
                   base_fee_gwei=blk.get("base_fee_gwei"), raw=dict(block=block_ref, receipts=rcpt_ref, trace=trace_ref,
                   slot=(raw(f"data/raw/beacon/block_slot_{blk['slot']}.json") if blk.get("slot") else None))),
        strip=strip, txs=notable, flows=flows, next_block=next_block, mempool=mempool, auction=auction,
        bot_idx=bot_idx, atk_idx=atk_idx, atk_block=atk_block, blocks_ahead=blocks_ahead,
        attacker_seen_rel_ms=seen_rel, reaction=(dict(t_ms=rbid["timestamp_ms"] - t0, eth=rnd(float(rbid["value_eth"]), 5),
                                                      builder=rbid.get("builder_name"), delay_ms=delay, method=method) if rbid else None),
        events=evs, fate=dict(kind=spec.get("fate_kind"), text=spec.get("fate"), returned_pct=spec.get("returned_pct")),
        incident_raw=inc_raw, timeline_notes=tl_notes,
        sources=[s for s in (inc.get("sources") or []) if isinstance(s, str) and s.startswith("http")][:8],
    )
    row = dict(
        id=rid_, slug=spec["slug"], sub=spec.get("sub"), name=detail["name"], date=detail["date"], bot=spec["bot"],
        race_type=spec["race_type"], verdict=detail["verdict"], one_liner=spec.get("one_liner"),
        mempool=mstate, attacker_first_seen_ms=attacker_seen_ms,
        bot_first_bid_ms=(rbid["timestamp_ms"] if rbid else None), detection_delay_ms=delay, delay_method=method,
        blocks_ahead=blocks_ahead, bot_idx=bot_idx, atk_idx=atk_idx, atk_landed=atk_block is not None,
        n_bids=bids["n_total"] if bids else 0, spark=spark, winner_builder=(winner.get("builder_name") or clean_name(blk.get("extra_data_name"))),
        winning_bid_eth=rnd(prop_eth, 4), proposer_paid_eth=rnd(prop_eth, 4), coinbase_eth=rnd(coinbase, 4),
        builder_refund_eth=rnd(refund_bot, 4), builder_payout_other_eth=rnd(refund_other, 4), gross_eth=ge,
        pct_to_builder=pct_builder, returned_pct=spec.get("returned_pct"), fate_kind=spec.get("fate_kind"), fate=spec.get("fate"),
        block=blk["number"], pre_merge=pre_merge, relays_answered=sum(1 for v in answered.values() if v.get("bids")),
        raw=dict(block=block_ref, receipts=rcpt_ref, trace=trace_ref,
                 bids=(auction or {}).get("raw", {}).get("bids"), delivered=(auction or {}).get("raw", {}).get("delivered"),
                 mempool=next((x["raw"]["csv"] for x in mem_out if x.get("seen") and x.get("role") == "attacker" and x["raw"].get("csv")), None),
                 mempool_sourcelog=next((x["raw"]["sourcelog"] for x in mem_out if x.get("seen") and x.get("role") == "attacker" and x["raw"].get("sourcelog")), None),
                 mempool_index=mempool.get("coverage_raw")),
    )
    return detail, row


# ------------------------------------------------------------------------------------------------ overlay
def overlay(row, cons):
    """Merge a consolidated row (schema in phase3-brief.md) over the derived row. Consolidated wins where present."""
    if not cons:
        return row
    def g(*path):
        cur = cons
        for p in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur
    m = {
        "name": g("name"), "sub_label": g("sub_label"), "evidence_strength": g("evidence_strength"), "evidence_strength_basis": g("evidence_strength_basis"), "public_ordering": g("public_ordering"), "comparison_policy": g("comparison_policy"), "caveat": g("caveat"), "date": g("date_utc") and str(g("date_utc"))[:10], "verdict": g("verdict"),
        "race_type": g("race_type"), "one_liner": g("one_liner"), "bot": g("bot", "label"),
        "mempool": g("evidence_level_mempool"), "loot_scope": g("loot", "scope"), "loot_note": g("loot", "loot_note"), "attacker_first_seen_ms": g("attacker_first_seen_utc_ms"),
        "bot_first_bid_ms": g("bot_first_bid_utc_ms"), "detection_delay_ms": g("detection_delay_ms"),
        "blocks_ahead": g("blocks_ahead"), "n_bids": g("auction", "n_bids"), "winner_builder": g("auction", "winning_builder"),
        "winning_bid_eth": g("auction", "winning_bid_eth"), "proposer_paid_eth": g("auction", "proposer_paid_eth"),
        "coinbase_eth": g("loot", "coinbase_paid_eth"), "paid_to_builder_eth": g("loot", "paid_to_block_producer_eth"), "builder_refund_eth": g("loot", "builder_refund_eth"),
        "returned_pct": g("fate", "returned_pct"), "fate": g("fate", "returned_desc"),
    }
    mm = {"in-block-only": "in-block-only", "measured": "measured", "absent-from-archive": "absent-from-archive"}
    for k, v in m.items():
        if v is None or v == "":
            continue
        if k == "mempool":
            v = mm.get(v, v)
        if k == "verdict":
            v = norm_verdict(v)
        row[k] = v
    cl = g("auction", "escalation")
    if isinstance(cl, list) and len(cl) > 1 and not row.get("spark"):
        row["spark"] = [[x[0], x[1]] for x in cl if isinstance(x, (list, tuple)) and len(x) >= 2]
    lt = cons.get("loot") or {}
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if num(lt.get("pct_to_builder")):
        row["pct_to_builder"] = rnd(min(100.0, float(lt["pct_to_builder"])), 2)
    if num(lt.get("gross_loot_eth")):
        row["gross_eth"] = lt["gross_loot_eth"]
    fs = {"none": "kept", "returned": "returned", "partial": "partial", "none-found": "kept", "not-applicable": "n-a", "unknown": "unknown"}
    rs = g("fate", "return_status")
    if rs in fs:
        row["fate_kind"] = fs[rs]
    if num(g("fate", "returned_pct")):
        row["returned_pct"] = g("fate", "returned_pct")
    elif rs in ("none-found",):
        row["returned_pct"] = None
    for k in ("returned_pct_of_gross", "returned_pct_of_bot_net", "returned_pct_of_victim_loss", "returned_by_builder_or_proposer_eth", "returned_pct_note"):
        if g("fate", k) is not None:   # explicit return denominators (data/harmonize_log.json -> returns_schema)
            row[k] = g("fate", k)
    if "detection_delay_ms" in cons:
        row["detection_delay_ms"] = cons["detection_delay_ms"]
        row["delay_method"] = cons.get("detection_method")
        row["detection_delay_ub_ms"] = cons.get("detection_delay_ub_ms")
    mon = money_of(cons)
    if mon:
        row["money"] = mon
    row["consolidated"] = True
    return row


# Who lost each headline race (owner decision 2026-10-23; audit launch/reports/v3-adversary.findings.md).
# verdict / label / note / evidence come from data/incidents.json `beaten_party`. BEATEN_EXTRA adds saved responses
# for the same facts that the site can publish (the loser's transactions, the mempool day rows) for rows whose own
# cited files are account lists the site does not otherwise carry.
BEATEN_EXTRA = {
    "unizen-2024--pending-ads": ["data/raw/mempool-dumpster/2024-03-08.csv.zip",
                                 "data/raw/rpc/tx_0x44ca0e6b77d75b63e9969323ad4a09509d806e2cc1b812caa001864a5c89ba88.json"],
    "unizen-2024--pending-xi": ["data/raw/rpc/tx_0x7234dfac08015dd1a71cf1e831a3a720ed7d3be9e98d38c606b443b6ee8c8b87.json",
                                "data/raw/rpc/tx_0x5cfe50df6e9bb8e07d36f7f5a031adad672550695106f4b94e227928b86efe61.json"],
    "defiplaza-2024": ["data/raw/etherscan/p2_907f_txlist.json"],
}
BEATEN_KIND = {"original-attacker-confirmed": "confirmed", "likely-attacker": "likely", "later-exploiter-or-unresolved": "later"}


def beaten_of(bp, row_id, exists=None):
    """The site's `beaten` field for one headline row: {verdict, kind, label, note, evidence: [site urls]}.
    `exists` (optional) filters the urls to files already published, for a data-only patch without the raw copy."""
    if not isinstance(bp, dict) or not bp.get("verdict"):
        return None
    urls = []
    for p in list(bp.get("evidence") or []) + BEATEN_EXTRA.get(row_id, []):
        u = raw(p, [])
        if u and u not in urls and (exists is None or exists(u)):
            urls.append(u)
    return dict(verdict=bp["verdict"], kind=BEATEN_KIND.get(bp["verdict"], "later"), label=bp.get("label"),
                note=bp.get("note"), evidence=urls)


def money_of(cons):
    """v2 money split: where every ETH of the take went (bot net, returns by side, bounty). Copied from the
    consolidated loot/fate records so pages can show the whole split (returned / builder+proposer / bot / other)."""
    lt, ft = cons.get("loot") or {}, cons.get("fate") or {}
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    m = {
        "bot_net_eth": lt.get("bot_net_eth"), "priority_fee_eth": lt.get("priority_fee_paid_eth"),
        "returned_total_eth": ft.get("returned_total_eth"), "returned_by_bot_side_eth": ft.get("returned_by_bot_side_eth"),
        "returned_by_builder_eth": ft.get("returned_by_builder_or_proposer_eth"), "bounty_kept_eth": ft.get("bounty_kept_eth"),
        "victim_loss_eth": ft.get("victim_loss_eth"),
    }
    m = {k: v for k, v in m.items() if num(v)}
    if isinstance(ft.get("bounty_desc"), str) and ft.get("bounty_desc"):
        m["bounty_desc"] = ft["bounty_desc"]
    cn = lt.get("captured_native")
    if isinstance(cn, dict) and cn.get("desc"):
        m["captured_desc"] = cn["desc"]
    return m


def _nrm(x):
    return re.sub(r"[^a-z0-9]", "", str(x or "").lower().replace("wave", ""))


def match_cons(cons_rows, spec):
    if not cons_rows:
        return None
    cands = [c for c in cons_rows if c.get("slug") == spec["slug"]]
    if not cands:
        return None
    if spec.get("sub"):
        a = _nrm(spec["sub"])
        subs = [c for c in cands if _nrm(c.get("sub")) and (_nrm(c.get("sub")) == a or _nrm(c.get("sub")).startswith(a) or a.startswith(_nrm(c.get("sub"))))]
        return subs[0] if subs else None
    withbot = [c for c in cands if (c.get("bot") or {}).get("block") == spec["block"]]
    return (withbot or [c for c in cands if c.get("race_type") != "late-copy"] or cands)[0]


# ------------------------------------------------------------------------------------------------ evolution
def build_evolution():
    w6 = ROOT / "data/evolution"
    v2 = (w6 / "by_era_v2.json").exists()
    be_all = jload(w6 / ("by_era_v2.json" if v2 else "by_era.json")) or {}
    be = be_all.get("attacker_only") or be_all      # v2 nests the attacker-sender tables
    pe = jload(w6 / ("per_exploit_v2.json" if (w6 / "per_exploit_v2.json").exists() else "per_exploit.json")) or {}
    ft = w6 / ("findings_v2.txt" if (w6 / "findings_v2.txt").exists() else ("findings.txt" if not v2 else "findings_v2.txt"))
    findings = ft.read_text() if ft.exists() else ""
    byy = be.get("by_year") or {}
    yrs = sorted(byy.keys())
    years = []
    for y in yrs:
        d = byy[y]
        cn = (d.get("counts") or {})
        wl = (d.get("wilson95_pct") or {})
        years.append(dict(
            year=int(y), n=d.get("n_exploits_total"), constructor_pct=d.get("constructor_exploit_pct"),
            constructor_k=(cn.get("constructor_exploit_pct") or {}).get("k"), constructor_n=(cn.get("constructor_exploit_pct") or {}).get("n"),
            constructor_ci=wl.get("constructor_exploit_pct"),
            constructor_or_internal_pct=(d.get("constructor_exploit_pct") or 0) + (d.get("internal_create_exploit_pct") or 0),
            same_block_deploy_pct=d.get("deploy_gap_same_block_pct"), same_tx_pct=d.get("same_tx_deploy_and_attack_pct"),
            no_window_pct=d.get("no_watchable_window_pct"),
            public_pct=d.get("dumpster_attacker_seen_pct"), control_pct=d.get("dumpster_control_seen_pct"),
            gap_s_median=d.get("deploy_gap_s_median_fresh_le7d"), gap_n=d.get("deploy_gap_n"),
            tip_gwei_median=d.get("tip_gwei_median"), tip_zero_pct=d.get("tip_zero_pct"), idx_median=d.get("tx_index_median"),
            bribe_pct=d.get("coinbase_bribe_pct"), flashloan_pct=d.get("flashloan_pct"),
            origin_pct=d.get("origin_check_pct_of_attacker_contracts"), unverified_pct=d.get("unverified_pct_of_attacker_contracts")))
    quarters = []
    for q, d in sorted((be.get("dumpster_era_by_quarter") or {}).items()):
        quarters.append(dict(q=q, n=d.get("n") if d.get("n") is not None else d.get("n_exploits_total"),
                             public=d.get("public"), private=d.get("private_bundle"), unknown=d.get("unknown"),
                             attacker_pct=d.get("attacker_seen_pct") if "attacker_seen_pct" in d else d.get("dumpster_attacker_seen_pct"),
                             attacker_ci=d.get("attacker_seen_wilson95"),
                             control_pct=d.get("control_seen_pct") if "control_seen_pct" in d else d.get("dumpster_control_seen_pct"),
                             constructor_pct=d.get("constructor_exploit_pct")))
    eras = []
    for k, d in (be.get("by_era") or {}).items():
        eras.append(dict(era=k, n=d.get("n_exploits_total"), constructor_pct=d.get("constructor_exploit_pct"),
                         public_pct=d.get("dumpster_attacker_seen_pct"), control_pct=d.get("dumpster_control_seen_pct"),
                         gap_s=d.get("deploy_gap_s_median_fresh_le7d"), tip=d.get("tip_gwei_median"), idx=d.get("tx_index_median")))
    dots = []
    for r in (pe.get("exploits") or []):
        if r.get("sender_class") not in (None, "attacker") or r.get("status") not in (None, "ok"):
            continue
        t = r.get("techniques") or {}
        dt = r.get("block_time_utc") or ""
        if not dt or not t:
            continue
        ex = r.get("exposure") or {}
        dots.append(dict(
            n=r.get("name"), d=dt[:10], y=r.get("year"), ctor=bool(t.get("constructor_exploit") or t.get("internal_create_exploit")),
            gap=t.get("deploy_gap_s") if t.get("deploy_gap_s") is not None else None,
            same_tx=bool(t.get("deploy_same_tx")), tip=t.get("tip_gwei"), med=t.get("block_median_tip_gwei"),
            bribe=t.get("coinbase_bribe_eth"), exp=ex.get("label"), idx=r.get("tx_index"), blk=r.get("block"),
            fresh=bool(t.get("deploy_fresh_le_7d"))))
    overall = be.get("overall") or {}
    cnt = overall.get("exposure_counts_all") or {}
    dn = overall.get("dumpster_era_n")
    # dumpster-era (measured) totals: sum of the quarterly counts, since the overall block mixes in pre-Aug-2023 heuristics
    qpub = sum((q.get("public") or 0) for q in quarters)
    qpri = sum((q.get("private") or 0) for q in quarters)
    qunk = sum((q.get("unknown") or 0) for q in quarters)
    measured = dict(n=qpub + qpri + qunk, public=qpub, private=qpri, unknown=qunk, since="2023-08-07",
                    attacker_seen_pct=overall.get("dumpster_attacker_seen_pct"), control_seen_pct=overall.get("dumpster_control_seen_pct"),
                    relative_visibility=overall.get("dumpster_relative_visibility"), excess_pts=overall.get("dumpster_excess_invisibility_pts"),
                    lead_time_s_median=overall.get("public_lead_time_s_median"), lead_time_n=overall.get("public_lead_time_s_n"),
                    n_reported=dn)
    bs = be_all.get("bot_side") or {}
    bot_side = None
    if bs:
        bo = bs.get("overall") or {}
        bot_side = dict(overall={k: bo.get(k) for k in ("n_rows", "n_measured", "tx_index_0_n", "tx_index_0_pct", "tx_index_0_wilson95", "bribe_paid_n", "bribe_paid_pct_of_measured", "bribe_eth_total", "bribe_eth_median_when_paid", "bribe_share_of_eth_inflow_median")},
                        note=bs.get("bribe_share_note"))
    vs = ((be_all.get("v1_vs_v2") or {}).get("scopes") or {}).get("overall")
    out = dict(version="v2" if v2 else "v1", provisional=not v2, years=years, quarters=quarters, eras=eras, dots=dots,
               overall=dict(n=overall.get("n_exploits_total"), resolved=overall.get("n_resolved"), private=cnt.get("private-bundle"),
                            public=cnt.get("public"), unknown=cnt.get("unknown"),
                            constructor_pct=overall.get("constructor_exploit_pct"), constructor_n=overall.get("constructor_exploit_n"),
                            same_tx_pct=overall.get("same_tx_deploy_and_attack_pct"), no_window_pct=overall.get("no_watchable_window_pct"),
                            gap_s_median=overall.get("deploy_gap_s_median_fresh_le7d"), bribe_pct=overall.get("coinbase_bribe_pct")),
               measured=measured, bot_side=bot_side, v1_vs_v2=vs,
               external=be_all.get("external_evidence") or be.get("external_evidence"), findings=findings,
               source_files=dict(by_era="data/evolution/" + ("by_era_v2.json" if v2 else "by_era.json"),
                                 per_exploit="data/evolution/" + ("per_exploit_v2.json" if (w6 / "per_exploit_v2.json").exists() else "per_exploit.json"),
                                 findings="data/evolution/" + ft.name))
    return out, v2


def build_explainer():
    d = jload(ROOT / "research/bot-re/ronin_calldata_diff.json") or {}
    yt, at = d.get("yoink_tx", ""), d.get("attacker_tx", "")
    d["raw"] = dict(
        yoink_tx=raw(f"data/raw/rpc/tx_{yt}.json"), user_tx=raw(f"data/raw/rpc/tx_{at}.json"),
        yoink_receipt=raw(f"data/raw/rpc/receipt_{yt}.json"), user_receipt=raw(f"data/raw/rpc/receipt_{at}.json"),
        yoink_trace=raw(f"data/raw/rpc/trace_{yt}.json"), user_trace=raw(f"data/raw/rpc/trace_{at}.json"))
    return d


DOWNLOADS = [
    # (source relative to project root, name under site/downloads/, description)
    ("research/bot-re/ronin_calldata_diff.json", "yoink/ronin_calldata_diff.json", "Ronin: user vs Yoink calldata, word by word"),
    ("research/bot-re/corpus_stats.json", "yoink/corpus_stats.json", "Yoink: generations, revert rates, selectors"),
    ("research/bot-re/blackbox_results.json", "yoink/blackbox_results.json", "Yoink: local black-box tests of the profit guard and bribe rule"),
    ("research/bot-re/fork_replay_results.json", "yoink/fork_replay_results.json", "Yoink: local-fork replays at Ronin"),
    ("research/bot-re/incident_txs.json", "yoink/incident_txs.json", "Yoink: decoded scripts of the incident txs"),
    ("data/evolution/findings.txt", "evolution/findings_v1.txt", "Evolution study: findings text (v1)"),
    ("data/evolution/findings_v2.txt", "evolution/findings_v2.txt", "Evolution study: findings text (v2, corrected)"),
    ("data/evolution/by_era.json", "evolution/by_era_v1.json", "Evolution study: aggregates (v1)"),
    ("data/evolution/by_era_v2.json", "evolution/by_era_v2.json", "Evolution study: aggregates (v2, corrected)"),
    ("data/evolution/per_exploit.json", "evolution/per_exploit_v1.json", "Evolution study: one row per exploit (v1)"),
    ("data/evolution/per_exploit_v2.json", "evolution/per_exploit_v2.json", "Evolution study: one row per exploit (v2, corrected)"),
    ("data/evolution/calibration.json", "evolution/calibration.json", "Evolution study: heuristic calibration"),
    ("research/explainer/bibliography.json", "bibliography.json", "Bibliography with verification status"),
    ("data/comparison_table.csv", "comparison_table.csv", "One row per race: the home-page table as CSV"),
]


def copy_downloads():
    out = []
    dst_root = SITE / "downloads"
    if dst_root.exists():
        shutil.rmtree(dst_root)
    for src, name, desc in DOWNLOADS:
        p = ROOT / src
        if not p.exists():
            continue
        txt = p.read_bytes()
        if name.endswith("blackbox_results.json"):
            try:
                jb = json.loads(txt)
                if isinstance(jb, list):
                    jb = [x for x in jb if not (isinstance(x, dict) and str(x.get("label", "")).startswith("gate:"))]    # access-control probes are not published
                    txt = json.dumps(jb, indent=1).encode()
            except Exception:
                pass
        if name == "comparison_table.csv":
            rd = list(csv.DictReader(io.StringIO(txt.decode("utf-8"))))
            for r_ in rd:
                if not r_.get("sub") and r_.get("slug") in C0_ONE_LINER:
                    r_["one_liner"] = C0_ONE_LINER[r_["slug"]]
            bio = io.StringIO()
            w_ = csv.DictWriter(bio, fieldnames=list(rd[0].keys()), lineterminator="\n")
            w_.writeheader()
            w_.writerows(rd)
            txt = bio.getvalue().encode("utf-8")
        if b"REDACT" in txt or b"private/" in txt:
            print("  !! not publishing (contains a REDACT/private marker):", src, file=sys.stderr)
            continue
        dst = dst_root / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(txt)
        out.append(dict(path="downloads/" + name, bytes=len(txt), desc=desc, origin=src))
    return out


# files that static pages (explainer.html, methods.html) link directly: registered so copy_raw publishes them
STATIC_RAW = []

# ------------------------------------------------------------------------------------------------ raw copy
def human(n):
    return f"{n / 1e6:.1f} MB"


def extract_mempool(site_raw_manifest, log):
    """Cut verbatim CSV rows for the cited hashes out of the 100 MB+ mempool-dumpster day files."""
    total = 0
    for path, hashes in sorted(MEMPOOL_NEED.items()):
        src = ROOT / path
        url = RAW_USED[path]
        dst = SITE / url
        dst.parent.mkdir(parents=True, exist_ok=True)
        hs = {h.lower() for h in hashes if h}
        hs_b = {h.encode() for h in hs}
        rows = 0
        MEMPOOL_FOUND.setdefault(url, set())
        if path in MEMPOOL_CACHE:
            dst.write_bytes(MEMPOOL_CACHE[path])
            for line in MEMPOOL_CACHE[path].splitlines()[1:]:
                parts = line.split(b",", 3)
                if len(parts) > 2 and parts[1].lower() in hs_b:
                    rows += 1
                    MEMPOOL_FOUND[url].add(parts[1].decode().lower())
        else:
            with zipfile.ZipFile(src) as z, open(dst, "wb") as out:
                name = z.namelist()[0]
                with z.open(name) as fh:
                    header = fh.readline()
                    out.write(header)
                    if hs:
                        for line in fh:
                            parts = line.split(b",", 3)
                            if len(parts) > 2 and parts[1].lower() in hs_b:
                                out.write(line)
                                rows += 1
                                MEMPOOL_FOUND.setdefault(url, set()).add(parts[1].decode().lower())
        mf = MANIFEST.get(path, {})
        site_raw_manifest[url[len("raw/"):]] = dict(
            origin=path, kind="verbatim rows for the cited tx hashes (header + matching lines), cut from the upstream day file",
            rows=rows, upstream_url=mf.get("url"), upstream_bytes=mf.get("bytes"), upstream_sha256=mf.get("sha256"),
            retrieved_at=mf.get("retrieved_at"), cited_hashes=sorted(hs))
        total += dst.stat().st_size
        log.append(f"  mempool extract {path} -> {url} ({rows} rows)")
    return total


def block_miner(n):
    for nm in (f"block_{n}.json", f"block_{n}_full.json", f"blk_{n}.json"):
        d = jload(ROOT / "data/raw/rpc" / nm)
        r = (d or {}).get("result") if isinstance(d, dict) else None
        if isinstance(r, dict) and r.get("miner"):
            return r["miner"].lower()
    return None


def redact_trace_block(path):
    """Return (doc, n_redacted) for a trace_block file; n_redacted = txs sent by c0ffeebabe.eth whose call trees were cut."""
    d = jload(path)
    if not isinstance(d, dict) or not isinstance(d.get("result"), list):
        return None, 0
    m = re.search(r"trace_block_(\d+)", os.path.basename(str(path)))
    miner = block_miner(m.group(1)) if m else None
    n = 0
    for ent in d["result"]:
        r = ent.get("result") if isinstance(ent, dict) else None
        if not isinstance(r, dict) or (r.get("from") or "").lower() != C0_EOA:
            continue
        keep = []

        def walk(c):
            for sub in c.get("calls") or []:
                v = sub.get("value")
                if miner and (sub.get("to") or "").lower() == miner and v not in (None, "0x0", "0x00", "0x"):
                    keep.append({"type": sub.get("type"), "from": sub.get("from"), "to": sub.get("to"), "value": v})
                walk(sub)
        walk(r)
        red = {k: r[k] for k in ("type", "from", "to", "value", "gas", "gasUsed") if k in r}
        red["calls"] = keep
        red["redacted"] = C0_REDACT_NOTE
        ent["result"] = red
        n += 1
    return d, n


def redact_c0_generic(path):
    """Blocks with full tx objects and block receipts: drop the input calldata and event logs of c0ffeebabe.eth's own transactions.
    Returns (doc, n) or (None, 0) when nothing needed redacting."""
    try:
        txt = Path(path).read_text()
    except Exception:
        return None, 0
    low = txt.lower()
    if "c0ffeeba" not in low and not any(p in low for p in C0_TX_PREFIX):
        return None, 0
    try:
        d = json.loads(txt)
    except Exception:
        return None, 0
    n = [0]

    def is_c0(o):
        if any(isinstance(o.get(key), str) and o[key].lower() == C0_EOA
               for key in ("from", "from_", "sender", "eoa", "attacker_eoa")):
            return True
        h = (o.get("transactionHash") or o.get("hash") or o.get("tx") or o.get("primary_tx") or "").lower()
        return any(h.startswith(p) for p in C0_TX_PREFIX)

    def walk(o):
        if isinstance(o, dict):
            if is_c0(o):
                inp = o.get("input")
                if isinstance(inp, str) and len(inp) > 2:
                    o["input"] = "0x"
                    o["inputRedacted"] = "calldata of a c0ffeebabe.eth transaction is not published (publication policy)"
                    n[0] += 1
                if isinstance(o.get("logs"), list) and o["logs"] and "status" in o:
                    o["logsRedacted"] = len(o["logs"])
                    o["logs"] = []
                    n[0] += 1
                for key in ("methodId", "functionName", "selector", "sel"):
                    if o.get(key):
                        o[key] = "" if key in ("methodId", "functionName") else None
                        n[0] += 1
                for key in ("techniques", "n_calls", "watch_calls", "n_addresses_touched", "touches_watch",
                            "trace_top_error", "replay_evidence", "call_diff", "call_tree"):
                    if key in o:
                        o.pop(key)
                        n[0] += 1
                if o.get("calls"):
                    plain = [call for call in o["calls"] if isinstance(call, dict)
                             and not (set(call) - {"type", "from", "to", "value"})]
                    if plain != o["calls"]:
                        o["calls"] = plain
                        o["redacted"] = C0_REDACT_NOTE
                        n[0] += 1
            for v in list(o.values()):
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(d)
    return (d, n[0]) if n[0] else (None, 0)


def filter_list(path, hashes):
    d = jload(path)
    rows = d.get("result") if isinstance(d, dict) else d
    if not isinstance(rows, list):
        return None, 0
    hs = {h.lower() for h in hashes}
    keep = [r for r in rows if isinstance(r, dict) and (r.get("hash") or r.get("transactionHash") or "").lower() in hs]
    out = dict(d) if isinstance(d, dict) else {}
    out["result"] = keep
    out["extract"] = "Rows for the cited transactions only (publication policy: no wider activity profile of c0ffeebabe.eth). Rows are verbatim."
    return out, len(keep)


def third_party_html_stub(upstream_url):
    """Ship a link-only citation instead of executable/copyrighted third-party page HTML."""
    url = upstream_url or ""
    archive = "https://web.archive.org/"
    return ("<!doctype html><meta charset=\"utf-8\"><title>Source link</title>"
            "<main><p>This third-party page is linked for reference and is not bundled.</p>"
            "<p>Public source: <a rel=\"noopener\" href=\"%s\">%s</a></p>"
            "<p>Archive lookup: <a rel=\"noopener\" href=\"%s\">web.archive.org</a></p></main>" % (url, url, archive))

def copy_raw(copy=True):
    log = []
    manifest = {}
    plain = {p: u for p, u in RAW_USED.items() if p not in MEMPOOL_NEED}
    sizes = {p: (ROOT / p).stat().st_size for p in plain}
    total = sum(sizes.values())
    skipped = []
    budget = RAW_BUDGET_MB * 1e6
    mem_est = 0.5e6
    if total + mem_est > budget:
        # drop bulky full-block traces / receipts first, then the biggest remaining, until we fit
        order = sorted(plain, key=lambda p: (0 if "/trace_block" in p else 1 if "/receipts_" in p else 2, -sizes[p]))
        for p in order:
            if total + mem_est <= budget:
                break
            skipped.append((p, sizes[p]))
            total -= sizes[p]
        for p, _ in skipped:
            plain.pop(p, None)
    if copy:
        old_manifest = jload(RAW_OUT / "MANIFEST.json") or {}
        for path, hashes in MEMPOOL_NEED.items():
            url = RAW_USED[path]
            prior = old_manifest.get(url[len("raw/"):], {})
            src = SITE / url
            upstream_sha = MANIFEST.get(path, {}).get("sha256")
            if (upstream_sha and prior.get("upstream_sha256") == upstream_sha
                    and {h.lower() for h in prior.get("cited_hashes", [])} == {h.lower() for h in hashes}
                    and src.is_file() and src.stat().st_size < 1_000_000):
                body = src.read_bytes()
                if prior.get("sha256") == hashlib.sha256(body).hexdigest():
                    MEMPOOL_CACHE[path] = body
        if RAW_OUT.exists():
            shutil.rmtree(RAW_OUT)
        RAW_OUT.mkdir(parents=True)
        for p, u in plain.items():
            dst = SITE / u
            dst.parent.mkdir(parents=True, exist_ok=True)
            mf = MANIFEST.get(p, {})
            base = os.path.basename(p)
            doc, note = None, None
            if base.startswith("trace_block_"):
                doc, nred = redact_trace_block(ROOT / p)
                if nred:
                    note = f"redacted: call trees of {nred} transaction(s) sent by c0ffeebabe.eth removed; builder-payment transfers kept"
                else:
                    doc = None
            elif base.startswith(("block_", "blk_", "receipts_", "rcpt")) and p not in FILTER_NEED:
                doc, nred = redact_c0_generic(ROOT / p)
                if nred:
                    note = f"redacted: input calldata and event logs of c0ffeebabe.eth transactions removed ({nred} field(s)); everything else verbatim"
                else:
                    doc = None
            elif p in FILTER_NEED and FILTER_NEED[p]:
                doc, nrow = filter_list(ROOT / p, FILTER_NEED[p])
                if doc is not None:
                    note = f"extract: {nrow} cited row(s) of the saved account list"
            if doc is not None:
                dst.write_text(json.dumps(doc, separators=(",", ":")))
                body = dst.read_bytes()
                manifest[u[len("raw/"):]] = dict(origin=p, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), upstream_sha256=mf.get("sha256"),
                                                 upstream_url=mf.get("url"), retrieved_at=mf.get("retrieved_at"), method=mf.get("method"), note=note)
                sizes[p] = len(body)
                continue
            if p in FILTER_NEED:
                continue          # a c0ffeebabe.eth account list with no cited row: not published
            # Saved press/framework HTML is link-only: no scripts, styles, client keys or copied page body.
            parts = Path(p).parts
            if Path(p).suffix.lower() == ".html" and any(x.startswith("web") or x == "balancer-web" for x in parts):
                body = third_party_html_stub(mf.get("url"))
                dst.write_text(body, encoding="utf-8")
                b = dst.read_bytes()
                manifest[u[len("raw/"):]] = dict(origin=p, bytes=len(b), sha256=hashlib.sha256(b).hexdigest(),
                                                 upstream_sha256=mf.get("sha256"), upstream_url=mf.get("url"),
                                                 retrieved_at=mf.get("retrieved_at"), method=mf.get("method"),
                                                 note="link-only stub: scripts, styles, client keys and copied page body removed")
                sizes[p] = len(b)
                continue
            shutil.copy2(ROOT / p, dst)
            manifest[u[len("raw/"):]] = dict(origin=p, bytes=sizes[p], sha256=mf.get("sha256"), upstream_url=mf.get("url"),
                                             retrieved_at=mf.get("retrieved_at"), method=mf.get("method"))
        mem_bytes = extract_mempool(manifest, log)
        (RAW_OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    else:
        mem_bytes = 0
    return dict(files=len(plain) + len(MEMPOOL_NEED), bytes=total + mem_bytes, skipped=skipped, log=log, mempool_days=len(MEMPOOL_NEED))


def prune_mempool_links():
    """A mempool entry links the day file's rows ('raw rows') and the per-source log. Some txs appear only in the per-source log
    (their rows are absent from the day file); the 'raw rows' link would then open a header-only file, so it is dropped."""
    n = 0
    for jf in list((DATA_OUT / "incident").glob("*.json")):
        d = json.loads(jf.read_text())
        ch = False
        for en in (d.get("mempool") or {}).get("entries") or []:
            r_ = en.get("raw") or {}
            for key in ("csv", "sourcelog"):
                u = r_.get(key)
                if u and en.get("seen") and u in MEMPOOL_FOUND and en["h"].lower() not in MEMPOOL_FOUND[u]:
                    r_[key] = None
                    ch = True
                    n += 1
        if ch:
            jf.write_text(json.dumps(d, separators=(",", ":")))
    rows = json.loads((DATA_OUT / "incidents.json").read_text())
    for r in rows:
        for key in ("mempool", "mempool_sourcelog"):
            u = (r.get("raw") or {}).get(key)
            if u and u in MEMPOOL_FOUND and not MEMPOOL_FOUND[u]:
                r["raw"][key] = None
    (DATA_OUT / "incidents.json").write_text(json.dumps(rows, separators=(",", ":")))
    print(f"  mempool links pruned where the extract has no row for the tx: {n}")


# ------------------------------------------------------------------------------------------------ c0ffeebabe policy
C0_ONE_LINER = {
    "curve-vyper-2023--mseth": "c0ffeebabe.eth's transaction landed at position 0 of block 17806550, before the later actor's contract deployment at position 10. It took 866.73 ETH gross and paid the builder 0.173 ETH, leaving 866.55 ETH net before gas.",
    "curve-vyper-2023--crv-eth-2": "c0ffeebabe.eth's transaction landed at position 7 of block 17808683, before the later actor's deployment at position 13. It took 2,879.66 ETH; 2,879.54 ETH was later returned to Curve's deployer.",
    "uncx-2026--zc-copiers": "The attacker's ZC transaction landed in block 26191745; other transactions followed in blocks 26191993 and 26191995. c0ffeebabe.eth landed at position 0 of 26191995 and later returned 15.764813 ETH on Base.",
    "bifi-2026": "One block after an attacker deployed a purpose-built BiFi USDT-market drain contract, and before it was ever called, c0ffeebabe.eth's tx emptied the market (netting 165,574.51 USDT, 68.06 WETH) and paid 0.9868 ETH to the builder.",
    "blueberry-2024": "c0ffeebabe.eth's tx took the full market cash (457.68 ETH) one block before the attacker's public tx landed, which then got nothing; the builder passed 366.5 ETH to Blueberry's multisig and c0ffeebabe's EOA later sent it 70 ETH.",
    "securedfinance-2026": "The attacker's public tx ran out of gas and reverted at block 25914188; 48 s later c0ffeebabe.eth's tx (block 25914192, pos 0) completed the extraction, ended with 28.85 ETH, and paid 28.84 ETH to the builder.",
}
C0_NARRATIVE = {
    "curve-vyper-2023--mseth": "In-block evidence only. c0ffeebabe.eth's transaction 0xc93eb238... landed at position 0 of block 17806550, before the later actor's deployment at position 10. That actor's transaction 0xe2eb61b1... landed in block 17806552 and received no net ETH. The earlier transaction took 866.73 ETH gross and paid the builder 0.173 ETH, leaving 866.55 ETH net before gas.",
    "curve-vyper-2023--crv-eth-2": "In-block evidence only. c0ffeebabe.eth's transaction 0xcd99fadd... landed at position 7 of block 17808683, before the later actor's deployment at position 13. Curve's deployer subsequently described the transaction in an on-chain message and requested a refund; 2,879.54 ETH was returned.",
    "bifi-2026": "The attacker EOA 0x7c78a049 deployed a purpose-built contract (0x8c0d729d) in block 26210255 (position 333) and never sent a call to it; the EOA's next transaction, in block 26210307, is unrelated. c0ffeebabe.eth's transaction 0x756c6805... landed in the next block, 26210256, at position 1, and emptied the market (USDT balance 170,038.086 -> 4,462.937), paying 0.9868 ETH to the builder. We count it as a deploy-window copy, by the same rule as Makina and Kelp: the transaction is counted from its ordering, funds and public block evidence. No attacker transaction was ever seen pending (the deploy and anything later are private flow, or absent from the mempool dump), so this rests on in-block and bytecode evidence.",
    "blueberry-2024": "The attacker (EOA 0x0512ac94..., contract 0x70b96d02... deployed 02:18:11 UTC) broadcast its exploit tx 0xb6748899... to the public mempool; first seen 02:22:09.219 UTC (Chainbound), 1.78 s before slot 8485909. c0ffeebabe.eth's tx 0xf0464b01... is index 0 of block 19287289 (02:22:11), the block before the attacker's tx (block 19287290, index 218, 02:22:23). It took the markets' cash (457.68 ETH) and paid 457.55 ETH to the builder; the attacker's tx still succeeded in the next block but received nothing from any market. The attacker's tx was pending in the public mempool when the bot's block was built; the bot's own tx is not in the mempool archive. The relationship is reported only from the public transaction, block, position and funds.",
    "securedfinance-2026": "The attacker's public-mempool tx 0x5d4e4fa9... (first seen 22:42:20.456) was mined in block 25914188 (locally built, no relay) and reverted: out of gas inside a flash-loan callback (gas limit 13,118,277, used 12,717,983). c0ffeebabe.eth's tx 0xcd615986... landed in block 25914192 at position 0, four blocks and 48 s later, and completed the extraction, ending with 28.85 ETH, of which 28.84 ETH went to the builder. It is in a later block than the attacker's tx and the attacker had no tx pending (next attacker tx 23:25), so it neither front-ran a pending attacker tx nor shares or precedes the attacker's block: it fails the confirmed-onchain test and is classed as a replay after a failure.  A different searcher (0xf601d764) later took 16,000 USDC from the same vault at block 25914405 position 0, also after the failure.",
}
# Narratives involving this operator are selected by transaction prefix, without quoting prior call comparisons.
C0_NARR_EDITS = {
    "0x04b166e7": ("sushi-rp2-2023", "Yoink landed before Trust's whitehat transaction. Later, c0ffeebabe.eth's transaction 0x04b166e7... landed at position 0 of block 17007842, paying 678.88 ETH to the builder. Returns recorded for the incident include 305.3 ETH from c0ffeebabe, 380 ETH from Yoink, 90 ETH from Trust and 100 ETH from BlockSec."),
    "0xf57b7dbf": ("uncx-2026", "Yoink landed in block 26191920 before the attacker's X-token transaction in block 26191921. The ZC transactions came later: another address in block 26191993, then c0ffeebabe.eth's transaction 0xf57b7dbf... at position 0 of block 26191995. Its EOA later returned 15.764813 ETH on Base. These ZC transactions followed the attacker's block 26191745."),
}
# event rewrites: (incident id, tx-hash prefix) -> new detail text (None = drop the event)
C0_EVENT = {
    ("bifi-2026", "0x756c68055a"): "block 26210256 pos 1: c0ffeebabe.eth's tx empties the market (USDT balance 170,038.09 -> 4,462.94); coinbase transfer 0.986829 ETH",
    ("blueberry-2024", "0xf0464b01d9"): "index 0: c0ffeebabe.eth's tx takes the markets' cash, worth 457.6846 ETH; 457.5473 ETH coinbase transfer",
    ("securedfinance-2026", "0xcd61598607"): "block 25914192 (153 txs): idx 0 is c0ffeebabe.eth's tx, which pays 28.837 ETH to coinbase 0x6c42a0b5; idx 152 builder pays proposer 1.2786 ETH. The tx is not in the mempool dump.",
    ("uncx-2026", "0xf57b7dbfdb"): "block 26191995 pos 0: c0ffeebabe.eth's tx follows the ZC copier from block 26191993, coinbase 0.116363 ETH; builder.ultrasound.money bid 0.039738 ETH delivered via titan relay at +944ms (jump from 0.0252 to 0.0399 at +900ms)",
    ("sushi-rp2-2023", "0xbb9aac7944"): "idx 1: c0ffeebabe.eth's transaction received 100 WETH; coinbase transfer 10.0 ETH",
    ("sushi-rp2-2023", "0x04b166e7b4"): "idx 0: c0ffeebabe.eth's transaction received 800 WETH; coinbase transfer 678.88 ETH (BlockSec: 'One bot owned by c0ffeebabe.eth even bribed 678 Eth to the builder in one transaction!')",
    ("sushi-rp2-2023", "0x11d069cbe4"): "idx 2: c0ffeebabe.eth's transaction received 100 WETH; no coinbase payment",
}
C0_DROP_EVENT = re.compile(r"two more c0ffeebabe txs|c0ffeebabe self-transfer", re.I)


def scrub_c0(detail, row):
    """Apply the c0ffeebabe policy to one built race (detail + table row), in place."""
    rid_ = detail["id"]
    is_c0 = "c0ffee" in (detail.get("bot") or "").lower() and "not c0ffeebabe" not in (detail.get("bot") or "").lower()
    if is_c0:
        if rid_ in C0_ONE_LINER:
            detail["one_liner"] = row["one_liner"] = C0_ONE_LINER[rid_]
        if rid_ in C0_NARRATIVE:
            detail["narrative"] = C0_NARRATIVE[rid_]
        # keep one transaction of the bot (the first); drop selectors, bundle guesses and the bot's other txs
        bots = sorted([t for t in detail["txs"] if t.get("role") == "bot"], key=lambda t: t["i"])
        keep = {bots[0]["h"].lower()} if bots else set()
        drop_idx = {t["i"] for t in bots if t["h"].lower() not in keep}
        detail["txs"] = [t for t in detail["txs"] if t["i"] not in drop_idx]
        for t in detail["txs"]:
            if t.get("role") == "bot":
                t["sel"] = None
                t["bundle_like"] = None
        for st in detail["strip"]:
            if st[0] in drop_idx:
                st[2] = ""
        fl = detail["flows"]
        fl["n_bot_txs"] = 1
        fl["bot_coinbase_eth"] = fl["primary_coinbase_eth"]
        fl["bot_priority_fee_eth"] = None
        # table-level coinbase is the primary tx's already
    for prefix, (slug, narrative) in C0_NARR_EDITS.items():
        if detail["slug"] == slug and any((e.get("tx") or "").lower().startswith(prefix) for e in detail["events"]):
            detail["narrative"] = narrative
    evs = []
    for e in detail["events"]:
        if C0_DROP_EVENT.search(e.get("detail") or ""):
            continue
        key = next((k for k in C0_EVENT if k[0] == rid_ and (e.get("tx") or "").lower().startswith(k[1])), None)
        if key:
            e["detail"] = C0_EVENT[key]
        evs.append(e)
    detail["events"] = evs
    detail.pop("incident_raw", None) if is_c0 else None
    return detail, row


def scrub_makina_narrative(detail):
    if isinstance(detail.get("narrative"), list):
        detail["narrative"] = [x for x in detail["narrative"] if "c0ffeebabe" not in x]


# ------------------------------------------------------------------------------------------------ lineages + messages
YOINK_MSG_PICK = [
    # (key, heading, context, [tx hash prefixes in reading order], incident link or None)
    ("sushi", "SushiSwap, April 2023", "A message signed as Sushi's security contact reached Yoink's wallet about five hours after the first RouteProcessor2 copy; Yoink answered the next day. That reply reverted, so the 380 ETH it carries did not move in this transaction. A repeat that did move 380 ETH to the multisig named in the first message landed about three and a half minutes later.",
     ["0xdffd3b6ff8", "0x7b6eb36aac"], "sushi-rp2-2023"),
    ("conic", "Conic Finance, July 2023", "Not one of the races counted here. It shows how a return gets negotiated, arithmetic included.",
     ["0x6382dad8f1", "0xaf1535ea5b", "0x9074a68818"], None),
    ("paraswap", "Paraswap, March 2024", "Paraswap asked for the money back. The two sides disagree about whether the payment to the validator at the end of the block counts against Yoink's profit.",
     ["0xa645a61524", "0xbd43d2dec1", "0x3d3e7cfe2b"], "paraswap-2024"),
    ("ronin", "Ronin bridge, August 2024", "A one-line thank-you addressed to the bot's wallet on the day of the Ronin copies.",
     ["0x8d3b20fb3f"], "ronin-2024&sub=Yoink"),
    ("makina", "Makina, January 2026", "Sent about twelve hours after the Makina race, to the address that the builder had forwarded 1,023.0 ETH of the searcher's payment to. The message does not say why Yoink wrote.",
     ["0xb4b66692ba"], "makina-2026"),
    ("botbot", "Another bot, September 2022", "From the bot's first weeks. The other party is not identified, and its claim about where it got its information is its own.",
     ["0x6f7ea46547", "0xfac61b5e93", "0x75a3ea5827", "0x6ec320afba"], None),
]


YOINK_EXTRA_TX = {"sushi": ("0xbefe5711e7", "The repeat transfer of 380 ETH that succeeded")}


def build_lineages():
    src = ROOT / "research/lineages/yoink_messages.json"
    d = jload(src)
    if not d:
        return None
    msgs = d.get("messages") or []
    byp = {}
    for m in msgs:
        byp[m["tx"].lower()] = m
    groups = []
    cited = set()
    for key, head, ctx, prefixes, link in YOINK_MSG_PICK:
        ms = []
        for pre in prefixes:
            m = next((x for x in msgs if x["tx"].lower().startswith(pre)), None)
            if not m:
                print("  !! yoink message not found:", pre, file=sys.stderr)
                continue
            cited.add(m["tx"].lower())
            ms.append(dict(tx=m["tx"], block=m["block"], time_utc=m["time_utc"], dir=m["direction"], frm=m["from"], to=m["to"],
                           value_eth=m["value_eth"], text=m["text"], failed=str(m.get("is_error")) == "1"))
        extra = None
        if key in YOINK_EXTRA_TX:
            pre, label = YOINK_EXTRA_TX[key]
            for p in sorted(glob.glob(str(ROOT / "data/raw/etherscan/w8_0xfde0d157_txlist_*.json"))):
                for r in (jload(p) or {}).get("result") or []:
                    if (r.get("hash") or "").lower().startswith(pre):
                        extra = dict(tx=r["hash"], label=label, time_utc=datetime.datetime.fromtimestamp(int(r["timeStamp"]), datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
                        cited.add(r["hash"].lower())
                        break
                if extra:
                    break
        groups.append(dict(key=key, heading=head, context=ctx, messages=ms, incident=link, extra=extra))
    # a verbatim extract of the cited rows from the saved Etherscan lists of Yoink's EOA
    rows, seen = [], set()
    for p in sorted(glob.glob(str(ROOT / "data/raw/etherscan/w8_0xfde0d157_txlist_*.json"))):
        j = jload(p) or {}
        for r in (j.get("result") or []):
            h = (r.get("hash") or "").lower()
            if h in cited and h not in seen:
                seen.add(h)
                rows.append(r)
    missing = cited - seen
    if missing:
        print("  !! yoink message rows missing from the saved txlists:", len(missing), file=sys.stderr)
    rows.sort(key=lambda r: int(r.get("blockNumber") or 0))
    ex_path = "raw/etherscan/w8_yoink_messages_extract.json"
    (SITE / "raw/etherscan").mkdir(parents=True, exist_ok=True)
    (SITE / ex_path).write_text(json.dumps(dict(status="1", message="OK (extract)", result=rows), indent=1))
    # the contract-creation rows of the same EOA (to == ""), verbatim, behind the "17 contracts" count
    crows, cseen = [], set()
    for p in sorted(glob.glob(str(ROOT / "data/raw/etherscan/w8_0xfde0d157_txlist_*.json"))):
        j = jload(p) or {}
        for r in (j.get("result") or []):
            h = (r.get("hash") or "").lower()
            if (r.get("to") or "") == "" and (r.get("contractAddress") or "") and h not in cseen:
                cseen.add(h)
                crows.append(r)
    crows.sort(key=lambda r: int(r.get("blockNumber") or 0))
    cr_path = "raw/etherscan/w8_yoink_contract_creations_extract.json"
    (SITE / cr_path).write_text(json.dumps(dict(status="1", message="OK (extract)", result=crows), indent=1))
    c = jload(ROOT / "research/lineages/yoink_contracts.json") or {}
    if len(crows) != c.get("n_contracts"):
        print("  !! creation rows", len(crows), "vs n_contracts", c.get("n_contracts"), file=sys.stderr)
    a57, a57_extra = build_a57_evidence()
    out = dict(
        messages=dict(total=d.get("count"), by_direction=d.get("by_direction"), eoa=d.get("yoink_eoa"), decoding=d.get("decoding"),
                      groups=groups, raw=ex_path),
        yoink=dict(contracts=c.get("n_contracts"), eoa=c.get("deployer_eoa"), raw=cr_path),
        a57=a57,
    )
    return out, dict(path=ex_path, rows=len(rows), cited=sorted(cited), extra=[dict(path=cr_path, rows=len(crows))] + a57_extra)


# the 0xa57 "one operator" claim: three facts, each from saved responses (no c0ffeebabe item involved)
A57_DODO_TX = "0x75d4765dd704d82f0bf539da88aff2568da38697f153b14d285abc8749da683f"       # Cheetah's DODO withdraw, block 12000167
A57_EF_TX = "0x1f1aba5bef04b7026ae3cb1cb77987071a8aff9592e785dd99860566ccad83d1"         # the Earning.Farm copy, block 15746200
A57_DEPLOY_TXS = ("0x0d8fc644c8", "0x4d373b2c9b")                                         # 0x8641df2d -> 0xa57bd001 (2019); -> factory 0x95a64fc0 -> 0xa69babef (2022)


def publish_file(rel, mm):
    """Copy one saved raw file to site/raw (these facts are cited from a static paragraph, not from an incident JSON)."""
    src = ROOT / "data/raw" / rel
    if not src.exists() or dead_reason("data/raw/" + rel) or is_c0_pertx(rel) or is_c0_list(rel):
        return None
    dst = RAW_OUT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copyfile(src, dst)
    b = dst.read_bytes()
    mf = MANIFEST.get("data/raw/" + rel, {})
    mm[rel] = dict(origin="data/raw/" + rel, bytes=len(b), sha256=hashlib.sha256(b).hexdigest(), upstream_url=mf.get("url"),
                   retrieved_at=mf.get("retrieved_at"), method=mf.get("method"), note="cited by the 0xa57 lineage paragraph")
    return "raw/" + rel


def build_a57_evidence():
    mp = RAW_OUT / "MANIFEST.json"
    mm = jload(mp) or {}
    ev = {}
    ev["dodo_take"] = [publish_file(f"rpc/receipt_{A57_DODO_TX}.json", mm)]
    ev["ef_capital"] = [publish_file(f"rpc/trace_{A57_EF_TX}.json", mm)]
    # verbatim rows of the two deployer transactions, cut from the saved Etherscan list of 0x8641df2d
    rows, seen = [], set()
    for p in sorted(glob.glob(str(ROOT / "data/raw/etherscan/w8_0x8641df2d_txlist_*.json"))):
        for r in (jload(p) or {}).get("result") or []:
            h = (r.get("hash") or "").lower()
            if h.startswith(A57_DEPLOY_TXS) and h not in seen:
                seen.add(h)
                rows.append(r)
    rows.sort(key=lambda r: int(r.get("blockNumber") or 0))
    ex_path = "raw/etherscan/w8_a57_deployer_rows_extract.json"
    (SITE / "raw/etherscan").mkdir(parents=True, exist_ok=True)
    (SITE / ex_path).write_text(json.dumps(dict(status="1", message="OK (extract)", result=rows), indent=1))
    ev["deployer"] = [ex_path, publish_file("etherscan/creation_0xa69babef.json", mm)]
    ev = {k: [x for x in v if x] for k, v in ev.items()}
    mp.write_text(json.dumps(mm, indent=1))
    miss = [k for k, v in ev.items() if not v]
    if miss or len(rows) != 2:
        print("  !! a57 evidence incomplete:", miss, len(rows), file=sys.stderr)
    return ev, [dict(path=ex_path, rows=len(rows), origin="data/raw/etherscan/w8_0x8641df2d_txlist_*.json",
                     kind="verbatim rows of the two deployer transactions (0xa57bd001 in 2019; the factory that made 0xa69babef in 2022), cut from the saved Etherscan lists of 0x8641df2d")]


# ------------------------------------------------------------------------------------------------ gap-fill auto specs
def auto_specs(cons_rows):
    """Phase C gap-fill rows (scripts/dataset/gapfill_rules/*.json) get race pages from the consolidated dataset instead of a hand-curated SPEC entry.
    Only rows whose bot block has a race_<block>.json in incidents/<slug>/ are added; the rest stay table-only stubs."""
    out = []
    slugs = {p.stem for p in (ROOT / "scripts/dataset/gapfill_rules").glob("*.json")}
    fk = {"none": "kept", "returned": "returned", "partial": "partial", "kept": "kept", "none-found": "unknown", "not-applicable": "n-a"}
    for c in cons_rows or []:
        if c["slug"] not in slugs or c.get("race_type") == "no-race":
            continue
        bot, att, fate, lt = c.get("bot") or {}, c.get("attacker") or {}, c.get("fate") or {}, c.get("loot") or {}
        blk = bot.get("block")
        if not blk or not (ROOT / "incidents" / c["slug"] / f"race_{blk}.json").exists():
            continue
        spec = dict(slug=c["slug"], block=blk, bot=bot.get("label") or "bot", race_type=c["race_type"], verdict=c.get("verdict"),
                    bot_addr=[bot["eoa"][:10]] if bot.get("eoa") else [], bot_tx=[bot["tx"][:10]] if bot.get("tx") else [],
                    atk_addr=[a[:10] for a in (att.get("eoas") or []) if a][:3],
                    atk_tx=[t["hash"][:10] for t in (att.get("attack_txs") or []) if t.get("hash") and t.get("block") == c.get("attacker_block")][:3],
                    atk_block=c.get("attacker_block"), gross_eth=lt.get("gross_loot_eth"), returned_pct=fate.get("returned_pct"),
                    fate_kind=fk.get(fate.get("return_status"), "unknown"), fate=fate.get("returned_desc") or "",
                    one_liner=c.get("one_liner"))
        if c.get("sub"):
            spec["sub"] = c["sub"]
        out.append(spec)
    return out


def finalize_public_files():
    """Apply privacy filters to every output and refresh hashes for modified evidence."""
    mp = RAW_OUT / "MANIFEST.json"
    manifest = jload(mp) or {}
    for folder in (DATA_OUT, SITE / "downloads", RAW_OUT):
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path == mp:
                continue
            rel = path.relative_to(RAW_OUT).as_posix() if folder == RAW_OUT else None
            if path.name == "seal_safeharbor_overview.html":
                path.unlink()
                manifest.pop(rel, None)
                continue
            original = path.read_bytes()
            note = None
            if folder == RAW_OUT and (path.name == "alkimiya_io_exp.sol" or path.name.startswith("dhl_conic")):
                upstream = (manifest.get(rel) or {}).get("upstream_url") or "https://github.com/SunWeb3Sec/DeFiHackLabs"
                body = ("Third-party DeFiHackLabs source (SPDX: UNLICENSED). Source body is not hosted.\n" + upstream + "\n").encode("utf-8")
                note = "link-only stub: DeFiHackLabs UNLICENSED source body removed; source attribution retained"
            elif path.suffix == ".html" and folder == RAW_OUT:
                text = third_party_html_stub((manifest.get(rel) or {}).get("upstream_url"))
                body = text.encode("utf-8")
                note = "link-only stub: page body, scripts and client keys removed"
            elif path.suffix == ".json":
                doc = json.loads(original)
                if folder == RAW_OUT or folder == SITE / "downloads":
                    redacted, count = redact_c0_generic(path)
                    if count:
                        doc = redacted
                        note = "redacted: transaction calldata, selectors and event logs removed; public transaction facts retained"
                clean = scrub_public(doc)
                if clean != doc:
                    note = (note + "; " if note else "") + "contact details and internal wording redacted; transaction hashes retained"
                body = json.dumps(clean, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            else:
                body = scrub_public(original.decode("utf-8")).encode("utf-8")
            if body != original:
                path.write_bytes(body)
            if rel is not None:
                entry = manifest.setdefault(rel, {})
                if body != original and entry.get("sha256"):
                    entry.setdefault("upstream_sha256", entry["sha256"])
                entry.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
                if note:
                    entry["note"] = note
                if body != original or entry.get("upstream_sha256") or any(word in str(entry.get("note", "")).lower() for word in ("reduc", "redact", "stub", "extract")):
                    entry["publication_status"] = "reduced for publication"
    manifest = {rel: info for rel, info in manifest.items() if (RAW_OUT / rel).is_file()}
    mp.write_text(json.dumps(scrub_public(manifest), indent=1))
    paths = [p for p in RAW_OUT.rglob("*") if p.is_file()]
    return len([p for p in paths if p != mp]), sum(p.stat().st_size for p in paths)


def validate_published_events():
    """Publish timeline values only when their linked published responses support them."""
    evidence_check.BASE = str(SITE)
    omitted = 0
    for path in sorted((DATA_OUT / "incident").glob("*.json")):
        doc = json.loads(path.read_text())
        kept, gaps = [], []
        for event in doc.get("events", []):
            # This policy is intentionally restricted to other operators' event records.
            blob = json.dumps(event).lower()
            if "c0ffeeba" in blob or any(prefix in blob for prefix in C0_TX_PREFIX):
                kept.append(event)
                continue
            refs = event.get("raws") or ([event["raw"]] if event.get("raw") else [])
            if refs:
                results = evidence_check.check_event(event, refs)
                failures = [r["label"] for r in results if not r["ok"]]
            else:
                failures = ["published source unavailable"]
            if failures:
                gaps.append({"tx": event.get("tx"), "kind": event.get("kind"), "unsupported_fields": failures})
            else:
                kept.append(event)
        doc["events"] = kept
        doc["timeline_publication_gaps"] = gaps
        omitted += len(gaps)
        path.write_text(json.dumps(doc, separators=(",", ":")))
    print(f"timeline publication: {omitted} entries retained in source records pending complete published evidence")


# ------------------------------------------------------------------------------------------------ main
def main():
    copy = "--no-copy" not in sys.argv
    load_manifest()
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    (DATA_OUT / "incident").mkdir(exist_ok=True)
    cons_rows = consolidated()
    SPEC.extend(auto_specs(cons_rows))
    print("consolidated data/incidents.json:", "FOUND (%d rows)" % len(cons_rows) if cons_rows else "absent -> fallback to incidents/*")
    rows = []
    cache = {}
    used_cons = set()
    for spec in SPEC:
        slug = spec["slug"]
        if slug not in cache:
            cache[slug] = load_incident_sources(slug)
        inc, events, races = cache[slug]
        ensure_race(slug, races, spec)
        cons = match_cons(cons_rows, spec)
        if cons:
            used_cons.add(id(cons))
        detail, row = build_race(spec, inc, events, races, cons)
        if not detail:
            continue
        if cons:
            row = overlay(row, cons)
            detail["date"] = row["date"]
            detail["verdict"], detail["race_type"] = row["verdict"], row["race_type"]
            detail["bot"] = row["bot"]
            if cons.get("one_liner"):
                detail["one_liner"] = cons["one_liner"]
            detail["fate"] = dict(kind=row.get("fate_kind"), text=row.get("fate"), returned_pct=row.get("returned_pct"))
            detail["dataset_money"] = {"scope": cons["loot"].get("scope"), "coinbase_eth": cons["loot"].get("coinbase_paid_eth"),
                "paid_to_builder_eth": cons["loot"].get("paid_to_block_producer_eth"), "builder_refund_eth": cons["loot"].get("builder_refund_to_bot_eth"), "note": cons["loot"].get("loot_note")}
            if row["mempool"] == "measured" and detail["mempool"]["state"] == "absent-from-archive":
                row["mempool"] = "absent-from-archive"
            row["relays_answered"] = sum(bool(v.get("bids")) for v in (detail.get("auction") or {}).get("relays", {}).values())
            if "detection_delay_ms" in cons:
                dm = cons["detection_delay_ms"]
                if dm is None:
                    detail["reaction"] = None
                    row["detection_delay_ms"] = None
                    row["bot_first_bid_ms"] = None          # no measured reaction: do not keep the page-local guess
                else:
                    # the reaction bid is taken from the dataset's own detection record (the bid that defines the delay),
                    # never from the page-local heuristic: time, value and builder must be one and the same raw bid
                    dc = cons.get("detection_candidates") or {}
                    cand = dc.get("winning_builder_first_stepup") if (cons.get("detection_method") or "").startswith("winning-builder") else dc.get("first_big_jump")
                    fa, fb = cons.get("attacker_first_seen_utc_ms"), cons.get("bot_first_bid_utc_ms")
                    if detail.get("reaction") is None and cand:
                        detail["reaction"] = dict(t_ms=None, eth=None, builder=None, delay_ms=dm, method=None)
                    if detail.get("reaction") is not None:
                        if isinstance(fa, (int, float)) and isinstance(fb, (int, float)):
                            detail["attacker_seen_rel_ms"] = fa - detail["t0_ms"]
                            detail["reaction"]["t_ms"] = fb - detail["t0_ms"]
                        detail["reaction"]["delay_ms"] = dm
                        detail["reaction"]["method"] = cons.get("detection_method") or detail["reaction"].get("method")
                        if cand and cand.get("eth") is not None:
                            if isinstance(fb, (int, float)) and cand.get("ms_rel_slot") is not None and fb - detail["t0_ms"] != cand["ms_rel_slot"]:
                                print(f"  !! {row['id']}: detection candidate at {cand['ms_rel_slot']} ms but bot_first_bid_utc_ms gives {fb - detail['t0_ms']}", file=sys.stderr)
                            detail["reaction"]["eth"] = rnd(float(cand["eth"]), 5)
                            detail["reaction"]["builder"] = cand.get("builder")
        row["title"] = detail["title"] = ((cons["name"] + (": " + cons["sub_label"] if cons.get("sub_label") else "")) if cons and cons["slug"] in {"unizen-2024", "conic-2023", "neemo-2025", "mintswap-2024", "metapool-2025", "taopad-2024", "peapods-2025", "punk-2021", "alkemi-2026", "uncx-2026"} else TITLES.get(row["id"], detail["name"]))
        if cons:
            for field in ("name", "sub_label", "evidence_strength", "evidence_strength_basis", "public_ordering", "comparison_policy", "caveat"):
                detail[field] = cons.get(field)
        if row["id"] == "curve-vyper-2023--peth":
            detail["narrative"] = "In-block evidence only. The pETH front-runner at position 0 preceded the attacker at position 91 in block 17806056. The operator later returned 5,495.4 WETH to JPEG’d under an agreed 10% bounty."

        row["headline"] = bool(row["verdict"] == "confirmed-onchain" and row["race_type"] in HEADLINE_TYPES)
        if cons and "headline" in cons and isinstance(cons["headline"], bool):
            row["headline"] = cons["headline"]
        detail["headline"] = row["headline"]
        if row["headline"] and cons and cons.get("beaten_party"):
            row["beaten"] = beaten_of(cons["beaten_party"], row["id"])
        detail, row = scrub_c0(detail, row)
        scrub_makina_narrative(detail)
        # every relay bid file behind the row's bid total, so the race table can link all of them (not just Flashbots)
        if isinstance(row.get("raw"), dict):
            row["raw"]["bids_all"] = [dict(relay=a["relay"], url=a["url"]) for a in (((detail.get("auction") or {}).get("raw") or {}).get("bids_all") or [])]
        (DATA_OUT / "incident" / f"{row['id']}.json").write_text(json.dumps(detail, separators=(",", ":")))
        rows.append(row)
    # consolidated rows with no replay (rejected non-races, late copies): table rows only, no race page
    for c in cons_rows or []:
        if id(c) in used_cons:
            continue
        rid = c["slug"] + ("--" + slugify(str(c["sub"])) if c.get("sub") else "")
        bot = c.get("bot") or {}
        lt = c.get("loot") or {}
        rows.append(dict(
            id=rid, slug=c["slug"], sub=c.get("sub"), stub=True, name=c.get("name"),
            title=c["name"] + (": " + c["sub_label"] if c.get("sub_label") else ""),
            date=str(c.get("date_utc") or "")[:10], bot=bot.get("label") or "none", race_type=c.get("race_type"),
            verdict=norm_verdict(c.get("verdict")), one_liner=c.get("one_liner"), headline=bool(c.get("headline")),
            mempool=c.get("evidence_level_mempool"), detection_delay_ms=None, blocks_ahead=c.get("blocks_ahead"),
            spark=[], n_bids=0, winner_builder=None, winning_bid_eth=None, coinbase_eth=lt.get("coinbase_paid_eth") or None,
            pct_to_builder=None, returned_pct=None, fate_kind="n-a", fate=c.get("verdict_reason"), block=bot.get("block"),
            pre_merge=False, raw={}, consolidated=True))
    rows.sort(key=lambda r: (r["date"] or "", r["id"]))
    (DATA_OUT / "incidents.json").write_text(json.dumps(rows, separators=(",", ":")))
    evo, v2 = build_evolution()
    (DATA_OUT / "evolution.json").write_text(json.dumps(evo, separators=(",", ":")))
    expl = build_explainer()
    (DATA_OUT / "explainer.json").write_text(json.dumps(expl or {}, separators=(",", ":")))
    for sp in STATIC_RAW:
        raw(sp)
    # downloads that are our own derived data (never incident.json / race files)
    stats = copy_raw(copy)
    if copy:
        prune_mempool_links()
    downloads = copy_downloads()
    lin = build_lineages() if copy else None
    if lin:
        ldata, lex = lin
        (DATA_OUT / "lineages.json").write_text(json.dumps(ldata, separators=(",", ":")))
        mp = RAW_OUT / "MANIFEST.json"
        mm = jload(mp) or {}
        mm[lex["path"][len("raw/"):]] = dict(origin="data/raw/etherscan/w8_0xfde0d157_txlist_*.json", kind="verbatim rows of the cited message transactions, cut from the saved Etherscan account lists of Yoink's EOA", rows=lex["rows"], cited_hashes=lex["cited"])
        for ex in lex.get("extra", []):
            mm[ex["path"][len("raw/"):]] = dict(origin=ex.get("origin", "data/raw/etherscan/w8_0xfde0d157_txlist_*.json"), kind=ex.get("kind", "verbatim contract-creation rows (to empty) cut from the saved Etherscan account lists of Yoink's EOA"), rows=ex["rows"])
        mp.write_text(json.dumps(mm, indent=1))
    # prose that cites a saved file as "data/raw/..." -> publish that file and point the text at the site copy
    if copy:
        cite = re.compile(r"data/raw/([A-Za-z0-9_\-./]+\.(?:html|json|csv|txt))")
        mp2 = RAW_OUT / "MANIFEST.json"
        mm2 = jload(mp2) or {}
        for jf in list((DATA_OUT / "incident").glob("*.json")) + [DATA_OUT / "incidents.json"]:
            txt = jf.read_text()
            def fix(m):
                rel = m.group(1)
                srcp = ROOT / "data/raw" / rel
                if not srcp.exists() or is_c0_pertx(rel) or is_c0_list(rel) or srcp.stat().st_size > 3e6:
                    return m.group(0)
                dstp = RAW_OUT / rel
                if not dstp.exists():
                    dstp.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(srcp, dstp)
                    b = dstp.read_bytes()
                    mm2[rel] = dict(origin="data/raw/" + rel, bytes=len(b), sha256=hashlib.sha256(b).hexdigest(), note="cited in prose")
                return "raw/" + rel
            new_txt = cite.sub(fix, txt)
            if new_txt != txt:
                jf.write_text(new_txt)
        mp2.write_text(json.dumps(mm2, indent=1))
    if copy:
        stats["files"], stats["bytes"] = finalize_public_files()
        validate_published_events()
    headline_stats = jload(ROOT / "data/headline_stats.json") or {}
    (DATA_OUT / "headline_stats.json").write_text(json.dumps(headline_stats, separators=(",", ":")))
    heads = [r for r in rows if r["headline"]]
    meta = dict(
        built=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), consolidated=bool(cons_rows),
        evolution_version=evo["version"], n_rows=len(rows), n_headline=len(heads),
        n_headline_incidents=len({r["slug"] for r in heads}), n_incidents=len({r["slug"] for r in rows}),
        raw_files=stats["files"], raw_bytes=stats["bytes"], raw_skipped=[dict(path=p, bytes=b) for p, b in stats["skipped"]],
        raw_mempool_days=stats["mempool_days"], downloads=downloads,
        file_sizes={p: (SITE / p).stat().st_size for p in ("data/incidents.json", "data/evolution.json", "raw/MANIFEST.json")})
    (DATA_OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"rows: {len(rows)}  headline: {len(heads)} rows / {meta['n_headline_incidents']} incidents; evolution {evo['version']}")
    print(f"raw: {stats['files']} files, {human(stats['bytes'])} (budget {RAW_BUDGET_MB} MB)")
    for line in stats["log"][:4]:
        print(line)
    if stats["skipped"]:
        print("SKIPPED (over budget):")
        for p, b in sorted(stats["skipped"], key=lambda x: -x[1])[:20]:
            print(f"   {human(b):>9}  {p}")
    big = sorted(((ROOT / "site" / u).stat().st_size, u) for u in RAW_USED.values() if (SITE / u).exists())[-5:]
    print("largest published raw files:")
    for b, u in reversed(big):
        print(f"   {human(b):>9}  {u}")
    dsz = sum(p.stat().st_size for p in DATA_OUT.rglob("*.json"))
    print(f"site/data: {human(dsz)} in {sum(1 for _ in DATA_OUT.rglob('*.json'))} files")


if __name__ == "__main__":
    main()
