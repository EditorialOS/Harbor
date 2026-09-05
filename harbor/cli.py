"""Harbor CLI.

Legacy intake commands remain. v0.8 adds the worker runtime and tenant config.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from . import core, deck_client
from .config import ConfigError, load_tenant
from .runtime import run_worker
from .worker import catalog as worker_catalog


def _kv(items):
    return dict(kv.split("=", 1) for kv in items)


def main():
    ap = argparse.ArgumentParser(prog="harbor", description="Installable AI worker runtime")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("catalog", help="list legacy intake jobs")
    sub.add_parser("connections", help="list Deck connected accounts")
    r = sub.add_parser("run", help="run one legacy intake job")
    r.add_argument("job"); r.add_argument("--credential", default="")
    r.add_argument("--input", action="append", default=[], help="key=value")

    sub.add_parser("workers", help="list installable workers")
    s = sub.add_parser("status", help="show tenant configuration without secrets")
    s.add_argument("--tenant", required=True, help="path to tenant config.json")
    w = sub.add_parser("run-worker", help="run a worker for a tenant")
    w.add_argument("worker")
    w.add_argument("--tenant", required=True, help="path to tenant config.json")
    w.add_argument("--input", action="append", default=[], help="key=value")

    args = ap.parse_args()

    if args.cmd == "catalog":
        for jid, j in core.load_catalog().items():
            print(f"  {jid:20} [{j['scope']:7}] {j['label']}  → feeds {j['feeds']}")
        return

    if args.cmd == "connections":
        for c in deck_client.list_connections():
            print(f"  {c['id']:16} {c.get('provider','?'):16} {c.get('status','?')}")
        return

    if args.cmd == "run":
        inputs = _kv(args.input)
        try:
            rec = core.run_job(args.job, args.credential, inputs)
        except (core.HarborError, deck_client.DeckError) as e:
            print(f"FAILED: {e}", file=sys.stderr); sys.exit(1)
        print(json.dumps(rec, indent=2))
        return

    if args.cmd == "workers":
        print(json.dumps(worker_catalog(), indent=2))
        return

    try:
        tenant = load_tenant(args.tenant)
    except (ConfigError, OSError, json.JSONDecodeError) as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr); sys.exit(2)

    if args.cmd == "status":
        safe = asdict(tenant)
        for c in safe.get("connections", []):
            if c.get("secret_ref"):
                c["secret_ref"] = c["secret_ref"].split(":", 1)[0] + ":***"
        print(json.dumps(safe, indent=2))
        return

    if args.cmd == "run-worker":
        result = run_worker(tenant, args.worker, _kv(args.input))
        print(json.dumps(asdict(result), indent=2, default=str))
        if result.status in {"failed", "blocked"}:
            sys.exit(1)
        return


if __name__ == "__main__":
    main()
