#!/usr/bin/env python3
"""publish_constituents.py — push board membership into the data warehouse.

Runs on the Actions runner after refetch_constituents.py. Copies the
constituents files and the reverse index into
jiegengxiangjianxue1/db-market/sector/ through the contents API (a clone would
pull the whole 40MB warehouse for a few hundred small files).

Skips a file whose remote content is already identical, so repeated runs are
cheap.
"""
import base64
import glob
import json
import os
import subprocess
import sys

MARKET_REPO = "jiegengxiangjianxue1/db-market"
TOKEN = os.environ.get("GH_TOKEN") or ""
UA_AGENT = "board-constituents"


def log(m):
    print(f"[pub] {m}", flush=True)


def api(method, path, body=None):
    url = f"https://api.github.com/repos/{MARKET_REPO}/contents/{path}"
    data = json.dumps(body).encode() if body is not None else None
    cmd = ["curl", "-s", "-X", method, url,
           "-H", f"Authorization: token {TOKEN}",
           "-H", "Accept: application/vnd.github+json",
           "-H", "User-Agent: " + UA_AGENT]
    if data:
        cmd += ["-H", "Content-Type: application/json", "-d", data.decode()]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {}


def publish(local_path, dest):
    with open(local_path, "rb") as f:
        body = f.read()
    b64 = base64.b64encode(body).decode()
    cur = api("GET", dest)
    if cur.get("content"):
        try:
            if base64.b64decode(cur["content"]) == body:
                return "same"
        except Exception:
            pass
    payload = {"message": f"sector: {os.path.basename(dest)}",
               "content": b64, "branch": "main"}
    if cur.get("sha"):
        payload["sha"] = cur["sha"]
    r = api("PUT", dest, payload)
    return "ok" if r.get("content") else f"fail:{str(r)[:120]}"


def main():
    if not TOKEN:
        log("GH_TOKEN is not set; cannot publish")
        return 1
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base = os.path.join(root, "data", "sector")

    targets = []
    for kind in ("industry", "concept"):
        targets += sorted(glob.glob(os.path.join(
            base, f"{kind}_constituents", "*.json")))
    idx = os.path.join(base, "stock_to_board.json")
    if os.path.exists(idx):
        targets.append(idx)
    tv = os.path.join(base, "tv_groups.json")
    if os.path.exists(tv):
        targets.append(tv)

    ok = same = fail = 0
    for p in targets:
        rel = os.path.relpath(p, base)
        dest = f"sector/{rel}"
        r = publish(p, dest)
        if r == "ok":
            ok += 1
        elif r == "same":
            same += 1
        else:
            fail += 1
            log(f"  {rel}: {r}")
    log(f"published {ok}, unchanged {same}, failed {fail}, of {len(targets)}")
    return 0 if fail == 0 and ok + same > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
