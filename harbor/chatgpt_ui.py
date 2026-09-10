"""Portable MCP Apps UI for Harbor's authenticated intelligence summary."""

HARBOR_APP_URI = "ui://harbor/intelligence-summary-v1.html"

HARBOR_APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root {
      color-scheme: light;
      --ink: #0d0d0d;
      --muted: #6b6b6b;
      --faint: #9b9b9b;
      --line: #e6e6e6;
      --paper: #ffffff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font: 14px/1.45 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .shell { padding: 18px 20px 16px; }
    .masthead {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--line);
    }
    .product { font-size: 14px; font-weight: 650; }
    .connection { display: inline-flex; align-items: center; gap: 7px; color: var(--muted); font-size: 12px; }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ink); }
    .dot.off { background: var(--faint); }
    .workspace { padding: 18px 0 14px; }
    .workspace-name { font-size: 13px; font-weight: 600; }
    .meta { color: var(--muted); font-size: 12px; }
    .label {
      margin-bottom: 7px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 650;
      letter-spacing: .06em;
      text-transform: uppercase;
    }
    h1 { margin: 0; font-size: 24px; line-height: 1.24; letter-spacing: -.02em; font-weight: 650; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      margin: 18px 0 0;
      padding: 15px 0;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
    }
    .metric { min-width: 0; padding: 0 16px; }
    .metric:first-child { padding-left: 0; }
    .metric + .metric { border-left: 1px solid var(--line); }
    .metric-label { color: var(--muted); font-size: 11px; }
    .metric-value { margin-top: 3px; font-size: 20px; line-height: 1.2; font-weight: 650; }
    .insight { padding: 14px 0; border-bottom: 1px solid var(--line); }
    .insight:last-of-type { border-bottom: 0; padding-bottom: 3px; }
    .insight-title { margin-bottom: 4px; font-size: 12px; font-weight: 650; }
    .insight-copy { color: #303030; }
    .empty { padding: 32px 0; color: var(--muted); text-align: center; }
    .error { padding: 14px 0; color: var(--ink); }
    .footer { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line); color: var(--faint); font-size: 11px; }
    @media (max-width: 520px) {
      .shell { padding: 15px 16px 13px; }
      h1 { font-size: 21px; }
      .metric { padding: 0 10px; }
      .metric-label { font-size: 10px; }
      .metric-value { font-size: 18px; }
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

    function el(tag, className, text) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined && text !== null) node.textContent = String(text);
      return node;
    }

    function first(items, fallback) {
      return Array.isArray(items) && items.length ? items[0] : fallback;
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

    function metric(label, value) {
      const item = el("div", "metric");
      item.append(el("div", "metric-label", label), el("div", "metric-value", value));
      return item;
    }

    function insight(title, copy) {
      const section = el("section", "insight");
      section.append(el("div", "insight-title", title), el("div", "insight-copy", copy));
      return section;
    }

    function render(data) {
      root.replaceChildren();

      const connected = data.connection_status === "ready";
      const header = el("header", "masthead");
      header.append(el("div", "product", "Harbor"));
      const connection = el("div", "connection");
      connection.append(el("span", `dot ${connected ? "" : "off"}`.trim()));
      connection.append(el("span", "", connected ? "Connected" : "Needs attention"));
      header.append(connection);
      root.append(header);

      const latest = data.latest_intelligence;
      if (!latest) {
        root.append(el("div", "empty", "No intelligence report yet. Ask ChatGPT to run Newsletter Intelligence."));
        return;
      }

      const intel = latest.intelligence || {};
      const metrics = latest.metrics || {};
      const latestPost = metrics.latest_post || {};

      const workspace = el("section", "workspace");
      workspace.append(el("div", "workspace-name", data.workspace?.name || "Harbor workspace"));
      workspace.append(el("div", "meta", `${formatDate(latest.finished_at)} · ${data.workspace?.timezone || "UTC"}`));
      root.append(workspace);

      root.append(el("div", "label", "Latest intelligence"));
      root.append(el("h1", "", intel.headline || latest.summary || "Latest report ready"));

      const metricsRow = el("section", "metrics");
      metricsRow.append(
        metric("Subscribers", formatCount(metrics.active_subscribers)),
        metric("Open rate", formatPercent(latestPost.open_rate)),
        metric("Click rate", formatPercent(latestPost.click_rate))
      );
      root.append(metricsRow);

      root.append(
        insight("What changed", first(intel.what_changed, "A prior report is needed to measure change.")),
        insight("Why it matters", first(intel.why_it_matters, "Harbor needs more source data before drawing a reliable conclusion.")),
        insight("Top action", first(intel.recommendations, "No immediate action is recommended."))
      );

      root.append(el("div", "footer", "Detailed recommendations and supporting analysis continue below in the conversation."));
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
          appInfo: { name: "Harbor", version: "1.0.0-rc.3" },
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
        root.replaceChildren(el("div", "error", "Harbor could not load. Refresh the Harbor connection and try again."));
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
