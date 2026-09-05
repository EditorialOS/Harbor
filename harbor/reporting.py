"""File output helpers. Files are date-stamped and never overwritten."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any


def ensure_workspace(root: str | Path) -> Path:
    root = Path(root)
    for rel in ("Work/reports", "Work/runs", "Work/intake", "Work/drafts"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    return root


def write_report(root: str | Path, slug: str, markdown: str, *, now: _dt.datetime | None = None) -> str:
    root = ensure_workspace(root)
    now = now or _dt.datetime.now(_dt.timezone.utc)
    date = now.date().isoformat()
    base = root / "Work" / "reports" / f"{date}-{slug}.md"
    path = base
    n = 2
    while path.exists():
        path = base.with_name(f"{base.stem}-{n}{base.suffix}")
        n += 1
    path.write_text(markdown)
    return str(path)


def write_run(root: str | Path, record: dict[str, Any], run_id: str) -> str:
    root = ensure_workspace(root)
    path = root / "Work" / "runs" / f"{run_id}.json"
    path.write_text(json.dumps(record, indent=2, default=str))
    return str(path)
