"""Portable MCP Apps UI for Harbor's authenticated product dashboard."""

HARBOR_APP_URI = "ui://harbor/dashboard-v1.html"

HARBOR_APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root {
      color-scheme: light dark;
      --ink: #17221d;
      --muted: #68736d;
      --paper: #fbfaf6;
      --panel: #ffffff;
      --line: #dfe4df;
      --green: #176b4d;
      --green-soft: #e5f3ec;
      --amber: #9a5a13;
      --amber-soft: #fff0d8;
      --red: #a23c32;
      --red-soft: #fbe9e6;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font: 14px/1.45 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button { font: inherit; }
    .shell { padding: 18px; min-height: 420px; }
    .masthead { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
    .eyebrow { color: var(--green); font-size: 11px; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; }
    h1 { margin: 4px 0 2px; font: 650 25px/1.15 ui-serif, Georgia, serif; }
    .subtle { color: var(--muted); }
    .connection { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); }
    .dot.warn { background: var(--amber); }
    .tabs { display: flex; gap: 4px; margin: 18px 0 14px; border-bottom: 1px solid var(--line); }
    .tab {
      border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--muted);
      cursor: pointer; padding: 9px 11px; font-weight: 650;
    }
    .tab[aria-selected="true"] { border-color: var(--green); color: var(--ink); }
    .view[hidden] { display: none; }
    .signal { border-left: 4px solid var(--green); padding: 2px 0 2px 14px; margin: 8px 0 17px; }
    .signal h2 { margin: 3px 0 0; font: 600 20px/1.3 ui-serif, Georgia, serif; }
    .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; margin-bottom: 14px; }
    .metric, .card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; }
    .metric { padding: 12px; }
    .metric span { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
    .metric strong { display: block; margin-top: 3px; font-size: 20px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .card { padding: 14px; }
    .card h3 { margin: 0 0 8px; font-size: 13px; }
    ul { margin: 0; padding-left: 18px; }
    li + li { margin-top: 6px; }
    .list { display: grid; gap: 8px; }
    .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
    .row-main { min-width: 0; }
    .row-title { font-weight: 700; overflow-wrap: anywhere; }
    .badge { border-radius: 99px; padding: 3px 8px; font-size: 11px; font-weight: 700; background: var(--green-soft); color: var(--green); }
    .badge.warn { background: var(--amber-soft); color: var(--amber); }
    .badge.bad { background: var(--red-soft); color: var(--red); }
    .action { border: 0; border-radius: 9px; background: var(--green); color: white; cursor: pointer; padding: 8px 11px; font-weight: 700; }
    .action:disabled { cursor: wait; opacity: .55; }
    .empty { padding: 26px 12px; text-align: center; color: var(--muted); border: 1px dashed var(--line); border-radius: 12px; }
    .notice { margin-top: 10px; padding: 9px 11px; border-radius: 9px; background: var(--green-soft); color: var(--green); }
    .notice.bad { background: var(--red-soft); color: var(--red); }
    footer { display: flex; justify-content: space-between; gap: 12px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--line); color: var(--muted); font-size: 11px; }
    @media (max-width: 560px) {
      .shell { padding: 14px; }
      .masthead { display: block; }
      .connection { margin-top: 8px; }
      .metrics, .grid { grid-template-columns: 1fr; }
      .tabs { overflow-x: auto; }
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --ink: #edf4ef; --muted: #a7b2ac; --paper: #111713; --panel: #18201b;
        --line: #344039; --green: #79d0aa; --green-soft: #193d2f;
        --amber: #efbd78; --amber-soft: #47331a; --red: #ef9b92; --red-soft: #492825;
      }
    }
  </style>
</head>
<body>
  <main id="root" class="shell" aria-live="polite">
    <div class="empty">Loading Harbor…</div>
  </main>
  <script>
    const root = document.getElementById("root");
    const pending = new Map();
    let requestId = 1;
    let dashboard = null;
    let activeView = "today";

    function el(tag, className, text) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined && text !== null) node.textContent = String(text);
      return node;
    }

    function formatPercent(value) {
      if (value === null || value === undefined) return "—";
      return new Intl.NumberFormat(document.documentElement.lang || "en-US", {
        style: "percent", maximumFractionDigits: 1
      }).format(value);
    }

    function formatCount(value) {
      if (value === null || value === undefined) return "—";
      return new Intl.NumberFormat(document.documentElement.lang || "en-US").format(value);
    }

    function formatDate(value) {
      if (!value) return "Not yet";
      const date = new Date(value);
      return Number.isNaN(date.valueOf()) ? String(value) : new Intl.DateTimeFormat(
        document.documentElement.lang || "en-US", { dateStyle: "medium", timeStyle: "short" }
      ).format(date);
    }

    function badge(text, state) {
      return el("span", `badge ${state || ""}`.trim(), text);
    }

    function listCard(title, items, fallback) {
      const card = el("section", "card");
      card.append(el("h3", "", title));
      if (!items || !items.length) {
        card.append(el("div", "subtle", fallback));
        return card;
      }
      const list = el("ul");
      items.forEach(item => list.append(el("li", "", item)));
      card.append(list);
      return card;
    }

    function todayView(data) {
      const view = el("section", "view");
      const latest = data.latest_intelligence;
      if (!latest) {
        view.append(el("div", "empty", "No completed intelligence report yet. Run Newsletter Intelligence to create the first one."));
        return view;
      }
      const intel = latest.intelligence || {};
      const metrics = latest.metrics || {};
      const latestPost = metrics.latest_post || {};
      const signal = el("section", "signal");
      signal.append(el("div", "eyebrow", `Latest intelligence · ${formatDate(latest.finished_at)}`));
      signal.append(el("h2", "", intel.headline || latest.summary || "Latest report ready"));
      view.append(signal);
      const metricGrid = el("div", "metrics");
      [
        ["Active subscribers", formatCount(metrics.active_subscribers)],
        ["Latest open rate", formatPercent(latestPost.open_rate)],
        ["Latest click rate", formatPercent(latestPost.click_rate)],
      ].forEach(([label, value]) => {
        const metric = el("div", "metric");
        metric.append(el("span", "", label), el("strong", "", value));
        metricGrid.append(metric);
      });
      view.append(metricGrid);
      const grid = el("div", "grid");
      grid.append(
        listCard("What changed", intel.what_changed, "A prior snapshot is needed for change detection."),
        listCard("Why it matters", intel.why_it_matters, "No interpretation is available yet."),
        listCard("Recommendations", intel.recommendations, "No action is recommended yet."),
        listCard("Important anomalies", intel.anomalies, "No material anomaly crossed Harbor’s thresholds.")
      );
      view.append(grid);
      return view;
    }

    function sourcesView(data) {
      const view = el("section", "view list");
      (data.sources || []).forEach(source => {
        const row = el("div", "row");
        const main = el("div", "row-main");
        main.append(el("div", "row-title", source.label || source.provider));
        main.append(el("div", "subtle", source.last_verified_at ? `Verified ${formatDate(source.last_verified_at)}` : "Not verified yet"));
        row.append(main, badge(source.status || "not connected", source.status === "verified" ? "" : "warn"));
        view.append(row);
      });
      if (!(data.sources || []).length) view.append(el("div", "empty", "No source is connected."));
      return view;
    }

    function workersView(data) {
      const view = el("section", "view list");
      (data.workers || []).forEach(worker => {
        const row = el("div", "row");
        const main = el("div", "row-main");
        main.append(el("div", "row-title", worker.label || worker.id));
        main.append(el("div", "subtle", worker.runnable ? "Runs in your private Sprite" : "Unavailable until reconciliation"));
        row.append(main);
        if (worker.enabled && worker.runnable) {
          const button = el("button", "action", "Run now");
          button.type = "button";
          button.onclick = () => runWorker(worker.id, button, view);
          row.append(button);
        } else {
          row.append(badge(worker.enabled ? "Unavailable" : "Disabled", "warn"));
        }
        view.append(row);
      });
      return view;
    }

    function runsView(data) {
      const view = el("section", "view list");
      (data.recent_runs || []).forEach(run => {
        const row = el("div", "row");
        const main = el("div", "row-main");
        main.append(el("div", "row-title", run.summary || run.worker_id));
        main.append(el("div", "subtle", `${formatDate(run.started_at)} · ${run.attempt_count || 0} attempt${run.attempt_count === 1 ? "" : "s"}`));
        const state = run.status === "completed" ? "" : run.status === "failed" ? "bad" : "warn";
        row.append(main, badge(run.status, state));
        view.append(row);
      });
      if (!(data.recent_runs || []).length) view.append(el("div", "empty", "No runs yet."));
      return view;
    }

    function render(data) {
      dashboard = data;
      root.replaceChildren();
      const header = el("header", "masthead");
      const title = el("div");
      title.append(el("div", "eyebrow", "Harbor workspace"));
      title.append(el("h1", "", data.workspace?.name || "Harbor"));
      title.append(el("div", "subtle", data.workspace?.timezone || "UTC"));
      const connected = data.connection_status === "ready";
      const connection = el("div", "connection");
      connection.append(el("span", `dot ${connected ? "" : "warn"}`.trim()));
      connection.append(el("span", "", connected ? "Connected" : "Needs attention"));
      header.append(title, connection);
      root.append(header);

      const tabs = el("nav", "tabs");
      tabs.setAttribute("aria-label", "Harbor dashboard sections");
      const views = { today: todayView, sources: sourcesView, workers: workersView, runs: runsView };
      Object.keys(views).forEach(key => {
        const button = el("button", "tab", key[0].toUpperCase() + key.slice(1));
        button.type = "button";
        button.setAttribute("aria-selected", String(activeView === key));
        button.onclick = () => { activeView = key; render(dashboard); };
        tabs.append(button);
      });
      root.append(tabs, views[activeView](data));
      const footer = el("footer");
      footer.append(el("span", "", "Newsletter Intelligence"), el("span", "", "Tenant-scoped · powered by live source data"));
      root.append(footer);
    }

    function request(method, params) {
      const id = requestId++;
      window.parent.postMessage({ jsonrpc: "2.0", id, method, params }, "*");
      return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
    }

    function notify(method, params) {
      window.parent.postMessage({ jsonrpc: "2.0", method, params }, "*");
    }

    async function connect() {
      try {
        await request("ui/initialize", {
          appInfo: { name: "Harbor", version: "1.0.0-rc.2" },
          appCapabilities: {},
          protocolVersion: "2026-01-26"
        });
        notify("ui/notifications/initialized", {});
        if (window.openai?.toolOutput) render(window.openai.toolOutput);
      } catch (error) {
        if (window.openai?.toolOutput) {
          render(window.openai.toolOutput);
          return;
        }
        root.replaceChildren(el("div", "notice bad", "Harbor could not initialize its dashboard. Refresh the Harbor connection and try again."));
      }
    }

    async function runWorker(workerId, button, view) {
      button.disabled = true;
      button.textContent = "Running…";
      try {
        const result = await request("tools/call", { name: "harbor_run_worker", arguments: { worker_id: workerId } });
        if (result?.isError || result?.structuredContent?.status === "failed") throw new Error("The worker run failed.");
        const refreshed = await request("tools/call", { name: "harbor_dashboard", arguments: {} });
        if (refreshed?.structuredContent) render(refreshed.structuredContent);
      } catch (error) {
        const notice = el("div", "notice bad", error?.message || "Harbor could not start the worker.");
        view.prepend(notice);
        button.disabled = false;
        button.textContent = "Run now";
      }
    }

    window.addEventListener("message", event => {
      if (event.source !== window.parent) return;
      const message = event.data;
      if (!message || message.jsonrpc !== "2.0") return;
      if (message.id !== undefined && pending.has(message.id)) {
        const handler = pending.get(message.id);
        pending.delete(message.id);
        message.error ? handler.reject(message.error) : handler.resolve(message.result);
        return;
      }
      if (message.method === "ui/notifications/tool-result" && message.params?.structuredContent) {
        render(message.params.structuredContent);
      }
    }, { passive: true });

    connect();
  </script>
</body>
</html>"""
