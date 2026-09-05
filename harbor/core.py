"""core.py — Harbor's brain. Catalog + run (async, MFA-aware) + log.

Harbor moves data between Deck and a client folder. Two directions, honestly labeled:
  - PULL jobs  (scope: owned/public)  -> read data INTO the client folder (the intake product)
  - PUSH jobs  (scope: publish)       -> send content OUT via a Deck poster (ToS-sensitive; off by default)

Deck task ids are runtime catalog metadata. The source catalog deliberately has
no customer task ids. Mock mode is explicit for local development and tests.
"""

import datetime
import json
import pathlib
import uuid

from . import beehiiv_client, deck_client
from .beehiiv_client import BeehiivError
from .deck_client import DeckError, DeckInteractionRequired

CATALOG = {
    # ---- PULL via native API (preferred where an API exists) ----
    "email-performance": {
        "label": "Pull newsletter/email performance from beehiiv",
        "engine": "beehiiv",
        "scope": "owned",
        "feeds": "performance-analyst",
    },
    # ---- PULL: the intake product (feeds Alex's starving workers) ----
    "social-insights": {
        "label": "Pull social performance metrics",
        "scope": "owned",
        "feeds": "performance-analyst",
    },
    "account-pull": {
        "label": "Pull account data (utility, payroll, SaaS)",
        "scope": "owned",
        "feeds": "onboarding",
    },
    "content-audit": {
        "label": "Export client's own content archive",
        "scope": "owned",
        "feeds": "onboarding, voicekit-corpus",
    },
    "competitor-public": {
        "label": "Read a competitor's PUBLIC pages / ad library",
        "scope": "public",
        "feeds": "competitive-analyst",
    },
    # ---- PUSH: ToS-sensitive; configure at runtime and enable deliberately. ----
    "instagram-post": {
        "label": "Publish copy + images to Instagram",
        "scope": "publish",
        "feeds": "(none — outbound)",
        "enabled": False,  # off until you decide the ToS question
    },
}


class HarborError(Exception):
    pass


def load_catalog(path=None):
    if path and pathlib.Path(path).exists():
        merged = dict(CATALOG)
        merged.update(json.loads(pathlib.Path(path).read_text()))
        return merged
    return CATALOG


def run_job(job_id, credential_id, inputs, workdir="Work/intake", catalog_path=None):
    """Run one catalog job through Deck. Returns the logged record.
    On MFA pause, returns a record with status 'interaction_required' (not a crash)."""
    catalog = load_catalog(catalog_path)
    if job_id not in catalog:
        raise HarborError(f"unknown job '{job_id}'. Known: {', '.join(catalog)}")
    job = catalog[job_id]
    if job.get("enabled") is False:
        raise HarborError(
            f"job '{job_id}' is disabled (scope={job['scope']}). "
            f"Enable it deliberately in the catalog once you've decided."
        )
    if job.get("engine", "deck") == "deck" and not job.get("deck_task"):
        raise HarborError(f"job '{job_id}' has no Deck task id in its runtime catalog")
    if (
        job.get("engine", "deck") == "deck"
        and job["scope"] in ("owned", "publish")
        and not credential_id
    ):
        raise HarborError(
            f"job '{job_id}' needs a credential_id (the account connected in Deck)."
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    run_id = f"intake_{now.date():%Y%m%d}_{uuid.uuid4().hex[:6]}"
    started = now.isoformat(timespec="seconds")

    # API-first engines (beehiiv, etc.) — no Deck, no browser, no MFA.
    if job.get("engine") == "beehiiv":
        pub_id = inputs.get("publication_id") or credential_id
        if not pub_id:
            raise HarborError(
                "email-performance needs publication_id "
                "(pass --input publication_id=pub_xxx)."
            )
        try:
            data = beehiiv_client.publication_performance(
                pub_id, int(inputs.get("recent_posts", 5))
            )
        except BeehiivError as e:
            rec = {
                "run_id": run_id,
                "job": job_id,
                "status": "failed",
                "started_at": started,
                "error": str(e),
            }
            _log(rec, workdir, ok=False)
            return rec
        rec = {
            "run_id": run_id,
            "job": job_id,
            "status": "completed",
            "label": job["label"],
            "scope": job["scope"],
            "feeds": job["feeds"],
            "started_at": started,
            "data": data,
            "source": "beehiiv-api" + (" (mock)" if data.get("_mock") else ""),
        }
        _log(rec, workdir, ok=True)
        return rec

    # default engine: Deck
    try:
        allow_mock = str(inputs.get("mode", "")).lower() == "mock"
        run = deck_client.run_task(
            job["deck_task"], credential_id or None, inputs, allow_mock=allow_mock
        )
    except DeckInteractionRequired as e:
        rec = {
            "run_id": run_id,
            "job": job_id,
            "status": "interaction_required",
            "started_at": started,
            "deck_run": e.run_id,
            "interaction": e.interaction,
            "note": "Deck paused for MFA/verification — resolve in Deck, then re-run.",
        }
        _log(rec, workdir, ok=False)
        return rec
    except (DeckError, HarborError) as e:
        rec = {
            "run_id": run_id,
            "job": job_id,
            "status": "failed",
            "started_at": started,
            "error": str(e),
        }
        _log(rec, workdir, ok=False)
        return rec

    rec = {
        "run_id": run_id,
        "job": job_id,
        "status": "completed",
        "label": job["label"],
        "scope": job["scope"],
        "feeds": job["feeds"],
        "credential_id": credential_id or None,
        "started_at": started,
        "runtime_ms": run.get("runtime_ms"),
        "data": run["output"],
        "source": "deck" + (" (mock)" if run.get("_mock") else ""),
    }
    _log(rec, workdir, ok=True)
    return rec


def _log(record, workdir, ok):
    d = pathlib.Path(workdir)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{record['run_id']}.json").write_text(json.dumps(record, indent=2))
    with open(d.parent / "harbor-log.md", "a") as f:
        f.write(
            f"- {record['started_at']} · {record['job']} · {record['status']} · {record['run_id']}\n"
        )
