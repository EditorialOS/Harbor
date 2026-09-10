"""Portable MCP Apps UI for Harbor's authenticated intelligence summary."""

HARBOR_APP_URI = "ui://harbor/intelligence-summary-v2.html"

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
    .shell { padding: 0 !important; }
    .masthead {
      padding: 22px 32px;
      border-bottom: 1px solid var(--line);
    }
    .product { font-size: 15px; font-weight: 650; }
    .report { padding: 28px 32px 30px; }
    .report-heading {
      display: flex;
      flex-wrap: wrap;
      gap: .28em;
      font-size: 24px;
      line-height: 1.25;
      font-weight: 400;
      letter-spacing: -.015em;
    }
    .report-name { color: var(--ink); }
    .report-date { color: var(--muted); }
    .metrics {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      padding: 22px 32px;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
    }
    .metric { min-width: 0; padding: 0 24px; }
    .metric:first-child { padding-left: 0; }
    .metric:last-child { padding-right: 0; }
    .metric + .metric { border-left: 1px solid var(--line); }
    .metric-label { color: var(--muted); font-size: 13px; }
    .metric-value { margin-top: 3px; font-size: 20px; line-height: 1.2; font-weight: 650; }
    .insights { display: grid; grid-template-columns: repeat(3, 1fr); padding: 24px 32px 28px; }
    .insight { min-width: 0; padding: 0 24px; }
    .insight:first-child { padding-left: 0; }
    .insight:last-child { padding-right: 0; }
    .insight + .insight { border-left: 1px solid var(--line); }
    .insight-title { margin-bottom: 5px; font-size: 14px; font-weight: 400; }
    .insight-copy { color: var(--muted); font-size: 14px; font-weight: 400; }
    .empty { padding: 36px 32px; color: var(--muted); text-align: center; }
    .error { padding: 24px 32px; color: var(--ink); }
    @media (max-width: 520px) {
      .masthead { padding: 18px 22px; }
      .report { padding: 22px; }
      .report-heading { font-size: 21px; }
      .metrics { padding: 18px 22px; }
      .metric { padding: 0 12px; }
      .metric-label { font-size: 11px; }
      .metric-value { font-size: 18px; }
      .insights { padding: 20px 22px 24px; }
      .insight { padding: 0 12px; }
      .insight-title, .insight-copy { font-size: 12px; }
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

    function formatReportDate(value, timeZone) {
      if (!value) return "Not yet";
      const date = new Date(value);
      if (Number.isNaN(date.valueOf())) return String(value);
      try {
        const parts = new Intl.DateTimeFormat(document.documentElement.lang || "en-US", {
          month: "numeric", day: "2-digit", year: "2-digit", timeZone: timeZone || "UTC"
        }).formatToParts(date);
        const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
        return `${values.month}.${values.day}.${values.year}`;
      } catch (error) {
        return `${date.getUTCMonth() + 1}.${String(date.getUTCDate()).padStart(2, "0")}.${String(date.getUTCFullYear()).slice(-2)}`;
      }
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

      const header = el("header", "masthead");
      header.append(el("div", "product", "Harbor"));
      root.append(header);

      const latest = data.latest_intelligence;
      if (!latest) {
        root.append(el("div", "empty", "No intelligence report yet. Ask ChatGPT to run Newsletter Intelligence."));
        return;
      }

      const intel = latest.intelligence || {};
      const metrics = latest.metrics || {};
      const latestPost = metrics.latest_post || {};

      const report = el("section", "report");
      const reportHeading = el("div", "report-heading");
      reportHeading.append(
        el("span", "report-name", "Intelligence report:"),
        el("span", "report-date", formatReportDate(latest.finished_at, data.workspace?.timezone))
      );
      report.append(reportHeading);
      root.append(report);

      const metricsRow = el("section", "metrics");
      metricsRow.append(
        metric("Subscribers", formatCount(metrics.active_subscribers)),
        metric("Open rate", formatPercent(latestPost.open_rate)),
        metric("Click rate", formatPercent(latestPost.click_rate))
      );
      root.append(metricsRow);

      const insights = el("section", "insights");
      insights.append(
        insight("What changed", first(intel.what_changed, "A prior report is needed to measure change.")),
        insight("Why it matters", first(intel.why_it_matters, "Harbor needs more source data before drawing a reliable conclusion.")),
        insight("Top action", first(intel.recommendations, "No immediate action is recommended."))
      );
      root.append(insights);
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
          appInfo: { name: "Harbor", version: "1.0.0-rc.4" },
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
