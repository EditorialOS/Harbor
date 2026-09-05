"""deck_client.py — the only place Harbor talks to Deck.

Wired to Deck's REAL v2 API (from deployed-agent docs):
  POST /v2/tasks/{task_id}/run   {credential_id?, input}  -> {id: "trun_...", status:"queued"}
  GET  /v2/task-runs/{run_id}     -> {status, result, output, errors, interaction, ...}
Runs are ASYNC: start, then poll until terminal. Terminal states:
  completed | failed | interaction_required  (last = paused for MFA/verification)

Set DECK_API_KEY to go live. Without it, mock mode returns realistic shapes.
"""
import json, os, time, urllib.request, urllib.error

DECK_BASE = os.environ.get("DECK_API_BASE", "https://api.deck.co/v2")
POLL_SECONDS = int(os.environ.get("DECK_POLL_SECONDS", "5"))
POLL_MAX = int(os.environ.get("DECK_POLL_MAX", "120"))  # 120*5s = 10 min ceiling


class DeckError(Exception):
    def __init__(self, kind, detail):
        self.kind, self.detail = kind, detail
        super().__init__(f"{kind}: {detail}")


class DeckInteractionRequired(Exception):
    """Run paused for MFA / security question — needs a human, not a retry."""
    def __init__(self, run_id, interaction):
        self.run_id, self.interaction = run_id, interaction
        super().__init__(f"interaction required on {run_id}: {interaction}")


def _live():
    return bool(os.environ.get("DECK_API_KEY"))


def _headers(json_body=False):
    h = {"Authorization": f"Bearer {os.environ['DECK_API_KEY']}"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _get(path):
    req = urllib.request.Request(f"{DECK_BASE}{path}", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise DeckError("deck_http_error", f"{e.code} {e.read()[:300]!r}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise DeckError("deck_unreachable", str(e))


def start_run(task_id: str, input_payload: dict, credential_id: str = None) -> str:
    """POST a task run. Returns the task_run id. (Async — does not wait.)"""
    if not _live():
        return _mock_start(task_id, input_payload, credential_id)
    body = {"input": input_payload}
    if credential_id:
        body["credential_id"] = credential_id
    req = urllib.request.Request(
        f"{DECK_BASE}/tasks/{task_id}/run", data=json.dumps(body).encode(),
        headers=_headers(json_body=True), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise DeckError("deck_http_error", f"{e.code} {e.read()[:300]!r}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise DeckError("deck_unreachable", str(e))
    run_id = resp.get("id")
    if not run_id:
        raise DeckError("deck_no_run_id", f"run start returned no id: {resp}")
    return run_id


def await_run(run_id: str) -> dict:
    """Poll a task run until terminal. Returns the full run object on completed.
    Raises DeckInteractionRequired on MFA pause, DeckError on failure/timeout."""
    if not _live():
        return _mock_await(run_id)
    for _ in range(POLL_MAX):
        run = _get(f"/task-runs/{run_id}")
        status = run.get("status")
        if status in ("queued", "running"):
            time.sleep(POLL_SECONDS); continue
        if status == "interaction_required":
            raise DeckInteractionRequired(run_id, run.get("interaction"))
        if status == "completed" and run.get("result") == "success":
            if "output" not in run:
                raise DeckError("deck_no_output", f"completed run has no output: {run}")
            return run
        # failed, or completed-but-not-success
        raise DeckError("deck_task_failed",
                        f"status={status} result={run.get('result')} errors={run.get('errors')}")
    raise DeckError("deck_timeout", f"run {run_id} not terminal after {POLL_MAX*POLL_SECONDS}s")


def run_task(task_id: str, credential_id: str, input_payload: dict) -> dict:
    """Convenience: start + await. Returns the completed run object."""
    run_id = start_run(task_id, input_payload, credential_id)
    return await_run(run_id)


def list_runs(task_id: str) -> list:
    if not _live():
        return []
    return _get(f"/task-runs?task_id={task_id}").get("data", [])


# ---- mock mode ----
_MOCK_STATE = {}

def _mock_start(task_id, input_payload, credential_id):
    rid = f"trun_mock_{len(_MOCK_STATE)+1}"
    # a task id containing 'insight'/'audit'/'bill'/'competitor' picks the sample
    _MOCK_STATE[rid] = (task_id, input_payload)
    return rid

def _mock_await(run_id):
    task_id, inp = _MOCK_STATE.get(run_id, ("", {}))
    t = task_id.lower()
    if "insight" in t or "ig" in t:
        out = {"account": "@mockbrand", "period": inp.get("period", "last_30d"),
               "followers": 4821, "reach": 18730, "impressions": 44210}
    elif "bill" in t or "util" in t or "account" in t:
        out = {"vendor": "Duke Energy", "account": "ACM-4021", "amount": 142.50, "due": "2026-05-15"}
    elif "audit" in t or "content" in t:
        out = {"posts_found": 214, "date_range": "2019..2026", "export_path": "mock://posts.jsonl"}
    elif "compet" in t:
        out = {"target": inp.get("target", "rival.com"),
               "changes": [{"type": "pricing", "was": "$49", "now": "$59"}]}
    else:  # e.g. the Instagram POSTER task -> post output shape
        out = {"post_id": "MOCK123", "post_url": "https://instagram.com/p/MOCK123/"}
    return {"id": run_id, "status": "completed", "result": "success",
            "task_id": task_id, "runtime_ms": 4523, "output": out, "errors": None,
            "interaction": None, "_mock": True}
