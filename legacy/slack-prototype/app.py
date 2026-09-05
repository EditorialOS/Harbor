"""Harbor Slack Bot — standalone data-pull product.

One-click "Add to Slack" → onboarding wizard (pick sources, paste keys) →
Harbor posts data summaries to the customer's chosen channel on schedule.

Stack: same as Alex's Slack app (Express pattern), but this is Python/Flask
for standalone portability. Swap to Express if you want to share Alex's VM.

Requires: pip install flask slack-bolt
Env: SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, HARBOR_SLACK_CLIENT_ID,
     HARBOR_SLACK_CLIENT_SECRET (from api.slack.com/apps)
"""
import os, json, threading, datetime
from harbor import core

# ---- Slack bolt wiring (real app) ----
try:
    from slack_bolt import App
    from slack_bolt.adapter.flask import SlackRequestHandler
    from flask import Flask, request, redirect

    bolt = App(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
    )
    flask_app = Flask(__name__)
    handler = SlackRequestHandler(bolt)

    # ---- OAuth install flow ("Add to Slack" button) ----
    @flask_app.route("/slack/install", methods=["GET"])
    def install():
        client_id = os.environ["HARBOR_SLACK_CLIENT_ID"]
        scopes = "chat:write,commands,channels:read"
        return redirect(f"https://slack.com/oauth/v2/authorize?client_id={client_id}"
                        f"&scope={scopes}&redirect_uri={os.environ.get('HARBOR_BASE_URL','')}/slack/oauth")

    @flask_app.route("/slack/oauth", methods=["GET"])
    def oauth_callback():
        # Exchange code for token, store per-workspace — same pattern as Alex's slackOauth.ts
        # In production: POST to slack.com/api/oauth.v2.access, save token+team_id to Postgres
        return "<h1>Harbor installed!</h1><p>Go back to Slack — Harbor will DM you to finish setup.</p>"

    # ---- Slash commands ----
    @bolt.command("/harbor")
    def harbor_command(ack, say, command):
        ack()
        text = (command.get("text") or "").strip()
        if text == "status":
            cat = core.load_catalog()
            lines = [f"*Harbor — {len(cat)} data sources configured*\n"]
            for jid, j in cat.items():
                if j.get("enabled") is not False:
                    lines.append(f"• `{jid}` — {j['label']} [{j['scope']}]")
            say("\n".join(lines))
        elif text.startswith("pull "):
            job_id = text.split()[1]
            say(f"Pulling `{job_id}`… I'll post the results here when done.")
            # Run async so Slack doesn't timeout
            def _run():
                try:
                    rec = core.run_job(job_id, os.environ.get("HARBOR_DEFAULT_CREDENTIAL",""),
                                      {"publication_id": os.environ.get("HARBOR_PUB_ID","")})
                    if rec["status"] == "completed":
                        d = rec["data"]
                        msg = f"*{rec['label']}* — pulled just now\n"
                        if "active_subscribers" in d:
                            msg += f"• Subscribers: {d['active_subscribers']}\n"
                            msg += f"• Avg open rate: {d.get('avg_open_rate',0):.1%}\n"
                            msg += f"• Avg click rate: {d.get('avg_click_rate',0):.1%}\n"
                        if d.get("recent_posts"):
                            msg += f"• Latest: _{d['recent_posts'][0].get('title','?')}_"
                            msg += f" — open {d['recent_posts'][0].get('open_rate',0):.1%}\n"
                        say(msg)
                    else:
                        say(f"Pull failed: {rec.get('error', rec.get('note','unknown'))}")
                except Exception as e:
                    say(f"Error: {e}")
            threading.Thread(target=_run).start()
        elif text == "help":
            say("*Harbor — your data runner*\n"
                "`/harbor status` — what's connected\n"
                "`/harbor pull email-performance` — pull now\n"
                "`/harbor sources` — available data sources\n"
                "Harbor also runs on schedule — numbers arrive before you wake up.")
        else:
            say("`/harbor help` for commands. Or just `/harbor pull email-performance`.")

    # ---- Scheduled morning post ----
    def morning_post(channel, team_token):
        """Called by your scheduler (cron / node-cron on the VM). Posts the summary."""
        from slack_sdk import WebClient
        client = WebClient(token=team_token)
        # Pull all enabled jobs
        results = []
        for jid, j in core.load_catalog().items():
            if j.get("enabled") is not False and not j.get("deck_task","").startswith("REPLACE_"):
                try:
                    rec = core.run_job(jid, os.environ.get("HARBOR_DEFAULT_CREDENTIAL",""),
                                      {"publication_id": os.environ.get("HARBOR_PUB_ID","")})
                    if rec["status"] == "completed":
                        results.append(rec)
                except: pass
        if not results:
            return
        today = datetime.date.today().strftime("%A, %B %d")
        msg = f"*Morning Data — {today}*\n"
        for r in results:
            d = r["data"]
            msg += f"\n📊 *{r['label']}*\n"
            if "active_subscribers" in d:
                msg += f"  Subscribers: {d['active_subscribers']} · "
                msg += f"Open: {d.get('avg_open_rate',0):.1%} · "
                msg += f"Click: {d.get('avg_click_rate',0):.1%}\n"
                if d.get("recent_posts"):
                    p = d["recent_posts"][0]
                    msg += f"  Latest: _{p.get('title','?')}_ — {p.get('open_rate',0):.1%} open\n"
        msg += "\n— Harbor"
        client.chat_postMessage(channel=channel, text=msg)

    @flask_app.route("/slack/events", methods=["POST"])
    def events():
        return handler.handle(request)

    @flask_app.route("/slack/commands", methods=["POST"])
    def commands():
        return handler.handle(request)

    def serve(port=3001):
        flask_app.run(port=port, host="0.0.0.0")

except ImportError:
    def serve(port=3001):
        raise SystemExit("pip install flask slack-bolt slack-sdk  to run the Slack bot.")
    def morning_post(channel, team_token):
        raise SystemExit("pip install flask slack-bolt slack-sdk  to run the Slack bot.")
