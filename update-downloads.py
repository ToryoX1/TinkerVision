#!/usr/bin/env python3
"""Summe der Downloads von Printables und Cults3D nach stats.json schreiben.

Printables ist öffentlich. Cults braucht einen API-Key:
  https://cults3d.com/en/api/keys
  export CULTS_API_KEY=...
  python3 update-downloads.py

Ohne Key bleibt der letzte Cults-Wert in stats.json stehen.
"""
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATS = ROOT / "stats.json"
PRINTABLES_ID = "2450000"
CULTS_NICK = "TinkerVision"


def post(url, query, headers=None):
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def printables():
    data = post(
        "https://api.printables.com/graphql/",
        '{ user(id: "%s") { downloadCount } }' % PRINTABLES_ID,
        {"User-Agent": "TinkerVision/downloads"},
    )
    return int(data["user"]["downloadCount"])


def cults(api_key):
    token = base64.b64encode(f"{CULTS_NICK}:{api_key}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "User-Agent": "TinkerVision/downloads"}
    total = 0
    offset = 0
    while True:
        query = """
        { myself { creationsBatch(limit: 50, offset: %d) {
          total
          results { downloadsCount }
        } } }
        """ % offset
        batch = post("https://cults3d.com/graphql", query, headers)["myself"]["creationsBatch"]
        rows = batch["results"] or []
        total += sum(int(r.get("downloadsCount") or 0) for r in rows)
        offset += len(rows)
        if not rows or offset >= int(batch["total"]):
            break
    return total


def main():
    previous = {}
    if STATS.exists():
        try:
            previous = json.loads(STATS.read_text())
        except json.JSONDecodeError:
            previous = {}

    printables_n = printables()
    cults_n = previous.get("cults")
    key = os.environ.get("CULTS_API_KEY")
    if key:
        cults_n = cults(key)
    elif cults_n is None:
        print("Hinweis: CULTS_API_KEY fehlt. Cults bleibt leer.", file=sys.stderr)

    total = printables_n + int(cults_n or 0)
    out = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "printables": printables_n,
        "cults": cults_n,
        "total": total,
    }
    STATS.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Printables {printables_n} + Cults {cults_n} = {total}")
    print(f"geschrieben: {STATS}")


if __name__ == "__main__":
    main()
