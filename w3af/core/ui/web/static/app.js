"use strict";

(() => {
  const POLL_INTERVAL_MS = 2000;
  const MAX_LOG_ENTRIES = 5000;

  const state = {
    scanId: null,
    scanStatus: null,
    nextLogId: 0,
    plugins: [],
    findings: [],
    urls: [],
    exceptions: [],
    pollTimer: null,
    settled: false,
  };

  const byId = (id) => document.getElementById(id);

  function element(tag, properties = {}, children = []) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(properties)) {
      if (name === "text") {
        node.textContent = value;
      } else if (name === "dataset") {
        Object.assign(node.dataset, value);
      } else if (name in node) {
        node[name] = value;
      } else {
        node.setAttribute(name, value);
      }
    }
    for (const child of children) {
      node.append(child);
    }
    return node;
  }

  class ApiError extends Error {
    constructor(status, message) {
      super(message);
      this.status = status;
    }
  }

  async function api(path, options = {}) {
    const request = { method: options.method || "GET", headers: { Accept: "application/json" } };
    if (options.body !== undefined) {
      request.headers["Content-Type"] = "application/json";
      request.body = JSON.stringify(options.body);
    }
    const response = await fetch(path, request);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new ApiError(response.status, data.message || `HTTP ${response.status}`);
    }
    return data;
  }

  function showNotice(message, kind = "error") {
    const notice = byId("notice");
    notice.textContent = message;
    notice.dataset.kind = kind;
    notice.hidden = false;
  }

  function clearNotice() {
    byId("notice").hidden = true;
  }

  async function run(action) {
    try {
      clearNotice();
      await action();
    } catch (error) {
      showNotice(error.message);
    }
  }

  // Tabs ------------------------------------------------------------------

  function selectTab(tab) {
    for (const other of document.querySelectorAll('[role="tab"]')) {
      const selected = other === tab;
      other.setAttribute("aria-selected", String(selected));
      other.tabIndex = selected ? 0 : -1;
      byId(other.getAttribute("aria-controls")).hidden = !selected;
    }
    tab.focus();
  }

  function setupTabs() {
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => selectTab(tab));
      tab.addEventListener("keydown", (event) => {
        const moves = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: tabs.length - 1 - index };
        if (!(event.key in moves)) {
          return;
        }
        event.preventDefault();
        selectTab(tabs[(index + moves[event.key] + tabs.length) % tabs.length]);
      });
    });
  }

  // Scan configuration ----------------------------------------------------

  function pluginCheckboxes() {
    return Array.from(document.querySelectorAll("#plugin-groups input[type=checkbox]"));
  }

  function selectedPlugins() {
    const selection = {};
    for (const group of state.plugins) {
      selection[group.type] = [];
    }
    for (const checkbox of pluginCheckboxes()) {
      if (checkbox.checked) {
        selection[checkbox.dataset.type].push(checkbox.dataset.name);
      }
    }
    return selection;
  }

  function updateGroupCounts() {
    for (const group of document.querySelectorAll(".plugin-group")) {
      const boxes = group.querySelectorAll("input[type=checkbox]");
      const checked = Array.from(boxes).filter((box) => box.checked).length;
      group.querySelector(".selected-count").textContent = `${checked}/${boxes.length} enabled`;
    }
  }

  function setGroupChecked(type, checked) {
    for (const checkbox of pluginCheckboxes()) {
      if (checkbox.dataset.type === type && !checkbox.closest("li").hidden) {
        checkbox.checked = checked;
      }
    }
    updateGroupCounts();
  }

  async function showPluginInfo(type, name) {
    const plugin = await api(`/plugins/${encodeURIComponent(type)}/${encodeURIComponent(name)}`);
    byId("plugin-dialog-title").textContent = `${type}.${name}`;
    const body = byId("plugin-dialog-body");
    body.replaceChildren(element("p", { text: plugin.description }), element("pre", { text: plugin.long_description }));
    if (plugin.options.length) {
      const list = element("dl");
      for (const option of plugin.options) {
        list.append(
          element("dt", { text: `${option.name} (${option.type})` }),
          element("dd", { text: `${option.description} Default: ${option.value || "(empty)"}` }),
        );
      }
      body.append(element("h3", { text: "Options" }), list);
    }
    byId("plugin-dialog").showModal();
  }

  function pluginItem(type, name) {
    const id = `plugin-${type}-${name}`;
    const checkbox = element("input", { type: "checkbox", id, dataset: { type, name } });
    checkbox.addEventListener("change", updateGroupCounts);
    const info = element("button", {
      type: "button",
      className: "link",
      text: "info",
      "aria-label": `About ${type}.${name}`,
    });
    info.addEventListener("click", () => run(() => showPluginInfo(type, name)));
    return element("li", { dataset: { name } }, [checkbox, element("label", { htmlFor: id, text: name }), info]);
  }

  function pluginGroup(group) {
    const selectAll = element("button", { type: "button", text: "Enable all" });
    selectAll.addEventListener("click", () => setGroupChecked(group.type, true));
    const selectNone = element("button", { type: "button", text: "Disable all" });
    selectNone.addEventListener("click", () => setGroupChecked(group.type, false));

    return element("details", { className: "plugin-group" }, [
      element("summary", {}, [`${group.type} `, element("span", { className: "muted selected-count" })]),
      element("p", { className: "muted type-description", text: group.description }),
      element("div", { className: "plugin-group-actions" }, [selectAll, selectNone]),
      element("ul", { className: "plugin-list" }, group.plugins.map((name) => pluginItem(group.type, name))),
    ]);
  }

  async function loadPlugins() {
    const data = await api("/plugins/");
    state.plugins = data.items;
    byId("plugin-groups").replaceChildren(...state.plugins.map(pluginGroup));
    updateGroupCounts();
  }

  function filterPlugins() {
    const needle = byId("plugin-filter").value.trim().toLowerCase();
    for (const item of document.querySelectorAll(".plugin-list li")) {
      item.hidden = needle !== "" && !item.dataset.name.toLowerCase().includes(needle);
    }
    for (const group of document.querySelectorAll(".plugin-group")) {
      group.open = needle !== "" && group.querySelector(".plugin-list li:not([hidden])") !== null;
    }
  }

  async function loadProfiles() {
    const data = await api("/profiles/");
    const select = byId("profile-select");
    for (const profile of data.items) {
      select.append(element("option", { value: profile.name, text: profile.name }));
    }
  }

  function applyPluginSelection(plugins) {
    for (const checkbox of pluginCheckboxes()) {
      checkbox.checked = (plugins[checkbox.dataset.type] || []).includes(checkbox.dataset.name);
    }
    updateGroupCounts();
  }

  async function selectProfile() {
    const name = byId("profile-select").value;
    if (!name) {
      byId("profile-description").textContent = "";
      byId("profile-content").value = "";
      applyPluginSelection({});
      return;
    }
    const profile = await api(`/profiles/${encodeURIComponent(name)}`);
    byId("profile-description").textContent = profile.description || "";
    byId("profile-content").value = profile.content;
    applyPluginSelection(profile.plugins);
  }

  function targetUrls() {
    return byId("target-urls")
      .value.split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line !== "");
  }

  async function startScan(event) {
    event.preventDefault();
    const urls = targetUrls();
    if (!urls.length) {
      byId("target-urls").focus();
      throw new Error("Enter at least one target URL.");
    }
    const composed = await api("/profiles/compose", {
      method: "POST",
      body: { scan_profile: byId("profile-content").value, plugins: selectedPlugins() },
    });
    const scan = await api("/scans/", {
      method: "POST",
      body: { scan_profile: composed.scan_profile, target_urls: urls },
    });
    resetScanViews();
    state.scanId = scan.id;
    byId("scan-target").textContent = urls.join(", ");
    showNotice(`Scan ${scan.id} started.`, "success");
    selectTab(byId("tab-status"));
    await refresh();
  }

  // Scan state ------------------------------------------------------------

  function resetScanViews() {
    state.settled = false;
    state.nextLogId = 0;
    state.findings = [];
    state.urls = [];
    state.exceptions = [];
    byId("log").replaceChildren();
    byId("status-grid").replaceChildren();
    byId("findings-list").replaceChildren();
    byId("urls-list").replaceChildren();
    byId("exceptions-list").replaceChildren();
    byId("traffic-request").textContent = "";
    byId("traffic-response").textContent = "";
    byId("traffic-id").value = "";
    for (const id of ["findings-count", "urls-count", "exceptions-count"]) {
      byId(id).textContent = "";
    }
  }

  async function findCurrentScan() {
    const data = await api("/scans/");
    const latest = data.items[data.items.length - 1];
    state.scanId = latest ? latest.id : null;
    byId("scan-target").textContent = latest ? latest.target_urls.join(", ") : "";
  }

  function statusEntries(status) {
    if (!status.eta) {
      return [
        ["Status", status.status],
        ["Error", status.exception || "-"],
      ];
    }
    return [
      ["Status", status.status],
      ["Progress", `${status.progress}%`],
      ["Estimated time left", status.eta.all],
      ["Requests per minute", status.rpm],
      ["Requests sent", status.sent_request_count],
      ["Crawl plugin", status.active_plugin.crawl || "-"],
      ["Audit plugin", status.active_plugin.audit || "-"],
      ["Crawling", status.current_request.crawl || "-"],
      ["Auditing", status.current_request.audit || "-"],
      ["Crawl queue", status.queues.crawl.length],
      ["Audit queue", status.queues.audit.length],
      ["Grep queue", status.queues.grep.length],
      ["Error", status.exception || "-"],
    ];
  }

  function renderStatus(status) {
    state.scanStatus = status.status;
    const badge = byId("scan-status");
    badge.textContent = status.status;
    badge.dataset.status = status.status;
    byId("scan-progress").value = status.progress;
    byId("scan-progress-text").textContent = `${status.progress}%`;
    byId("pause-button").disabled = status.status !== "Running";
    byId("resume-button").disabled = status.status !== "Paused";
    byId("stop-button").disabled = !["Running", "Paused"].includes(status.status);
    byId("delete-button").disabled = status.status !== "Stopped";

    const grid = byId("status-grid");
    grid.replaceChildren();
    for (const [term, value] of statusEntries(status)) {
      grid.append(element("dt", { text: term }), element("dd", { text: String(value) }));
    }
    if (status.exception) {
      showNotice(`The scan failed: ${status.exception}`);
    }
  }

  function logEntry(entry) {
    return element("li", { dataset: { type: entry.type } }, [
      element("time", { text: entry.time }),
      entry.message,
    ]);
  }

  function applyLogFilter() {
    const type = byId("log-filter").value;
    for (const item of byId("log").children) {
      item.hidden = type !== "" && item.dataset.type !== type;
    }
  }

  async function refreshLog() {
    const log = byId("log");
    let next = state.nextLogId;
    while (next !== null) {
      const data = await api(`/scans/${state.scanId}/log?id=${next}`);
      log.append(...data.entries.map(logEntry));
      state.nextLogId = next + data.entries.length;
      next = data.next;
    }
    while (log.children.length > MAX_LOG_ENTRIES) {
      log.firstElementChild.remove();
    }
    applyLogFilter();
    if (byId("log-follow").checked) {
      log.scrollTop = log.scrollHeight;
    }
  }

  function itemButton(label, secondary, onSelect) {
    const button = element("button", { type: "button" }, [label, element("span", { className: "secondary", text: secondary })]);
    button.addEventListener("click", () => {
      for (const other of button.closest("ul").querySelectorAll("button")) {
        other.removeAttribute("aria-current");
      }
      button.setAttribute("aria-current", "true");
      run(onSelect);
    });
    return element("li", {}, [button]);
  }

  function renderFindings() {
    const needle = byId("findings-filter").value.trim().toLowerCase();
    const visible = state.findings.filter(
      (finding) => !needle || `${finding.name} ${finding.url || ""}`.toLowerCase().includes(needle),
    );
    byId("findings-list").replaceChildren(
      ...visible.map((finding) => itemButton(finding.name, finding.url || "", () => showFinding(finding.href))),
    );
    byId("findings-count").textContent = state.findings.length ? String(state.findings.length) : "";
  }

  function detailRow(term, value) {
    if (value === null || value === undefined || value === "" || (Array.isArray(value) && !value.length)) {
      return [];
    }
    const description = element("dd");
    if (value instanceof Node) {
      description.append(value);
    } else {
      description.textContent = Array.isArray(value) ? value.join(", ") : String(value);
    }
    return [element("dt", { text: term }), description];
  }

  function trafficLinks(finding) {
    const container = element("span");
    finding.traffic_hrefs.forEach((href, index) => {
      const id = finding.response_ids[index];
      const button = element("button", { type: "button", className: "link", text: `#${id}` });
      button.addEventListener("click", () => run(() => showTraffic(href, id)));
      container.append(button);
    });
    return container;
  }

  function referenceLinks(finding) {
    const list = element("ul");
    for (const reference of finding.references || []) {
      if (!/^https?:\/\//i.test(reference.url)) {
        continue;
      }
      const link = element("a", { href: reference.url, text: reference.title || reference.url, rel: "noreferrer noopener", target: "_blank" });
      list.append(element("li", {}, [link]));
    }
    return list.children.length ? list : null;
  }

  async function showFinding(href) {
    const finding = await api(href);
    const severity = element("span", { className: "severity", text: finding.severity, dataset: { severity: finding.severity } });
    const rows = [
      ...detailRow("Severity", severity),
      ...detailRow("URL", finding.url),
      ...detailRow("Parameter", finding.var),
      ...detailRow("Plugin", finding.plugin_name),
      ...detailRow("CWE", finding.cwe_ids),
      ...detailRow("Fix effort", finding.fix_effort),
      ...detailRow("Requests", finding.traffic_hrefs.length ? trafficLinks(finding) : null),
      ...detailRow("References", referenceLinks(finding)),
    ];
    byId("finding-details").replaceChildren(
      element("h2", { text: finding.name }),
      element("dl", {}, rows),
      element("h3", { text: "Description" }),
      element("p", { text: finding.desc }),
      ...(finding.long_description ? [element("h3", { text: "Details" }), element("p", { text: finding.long_description })] : []),
      ...(finding.fix_guidance ? [element("h3", { text: "Fix guidance" }), element("p", { text: finding.fix_guidance })] : []),
    );
  }

  function renderUrls() {
    const needle = byId("urls-filter").value.trim().toLowerCase();
    const visible = state.urls.filter((url) => !needle || url.toLowerCase().includes(needle));
    byId("urls-list").replaceChildren(...visible.map((url) => element("li", { text: url })));
    byId("urls-count").textContent = state.urls.length ? String(state.urls.length) : "";
  }

  function renderExceptions() {
    byId("exceptions-list").replaceChildren(
      ...state.exceptions.map((item) =>
        itemButton(item.exception, `${item.phase}.${item.plugin} (${item.function_name}:${item.lineno})`, () => showException(item.href)),
      ),
    );
    byId("exceptions-count").textContent = state.exceptions.length ? String(state.exceptions.length) : "";
  }

  async function showException(href) {
    const item = await api(href);
    byId("exception-details").replaceChildren(
      element("h2", { text: item.exception }),
      element("dl", {}, [
        ...detailRow("Plugin", `${item.phase}.${item.plugin}`),
        ...detailRow("Location", `${item.function_name}:${item.lineno}`),
      ]),
      element("pre", { className: "traceback", text: item.traceback, tabIndex: 0 }),
    );
  }

  function decodeMessage(encoded) {
    const binary = atob(encoded);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
  }

  async function showTraffic(href, id) {
    const traffic = await api(href);
    byId("traffic-id").value = id;
    byId("traffic-request").textContent = decodeMessage(traffic.request);
    byId("traffic-response").textContent = decodeMessage(traffic.response);
    selectTab(byId("tab-traffic"));
  }

  async function lookupTraffic(event) {
    event.preventDefault();
    if (state.scanId === null) {
      throw new Error("Start a scan before browsing its traffic.");
    }
    const id = byId("traffic-id").value;
    await showTraffic(`/scans/${state.scanId}/traffic/${encodeURIComponent(id)}`, id);
  }

  async function refreshResults() {
    const [findings, urls, exceptions] = await Promise.all([
      api(`/scans/${state.scanId}/kb/`),
      api(`/scans/${state.scanId}/urls/`),
      api(`/scans/${state.scanId}/exceptions/`),
    ]);
    state.findings = findings.items;
    state.urls = urls.items;
    state.exceptions = exceptions.items;
    renderFindings();
    renderUrls();
    renderExceptions();
  }

  async function refresh() {
    if (state.scanId === null) {
      byId("scan-bar").hidden = true;
      return;
    }
    byId("scan-bar").hidden = false;
    document.querySelector('[data-empty-for="status"]').hidden = true;
    const status = await api(`/scans/${state.scanId}/status`);
    renderStatus(status);
    if (state.settled) {
      return;
    }
    await refreshLog();
    await refreshResults();
    state.settled = status.status === "Stopped";
  }

  function schedulePolling() {
    clearTimeout(state.pollTimer);
    state.pollTimer = setTimeout(async () => {
      try {
        if (state.scanId === null) {
          await findCurrentScan();
        }
        await refresh();
      } catch (error) {
        if (error.status === 404) {
          state.scanId = null;
        } else {
          showNotice(error.message);
        }
      }
      schedulePolling();
    }, POLL_INTERVAL_MS);
  }

  // Scan actions ----------------------------------------------------------

  async function scanAction(action, message) {
    await api(`/scans/${state.scanId}/${action}`);
    state.settled = false;
    showNotice(message, "success");
    await refresh();
  }

  async function deleteScan() {
    await api(`/scans/${state.scanId}`, { method: "DELETE" });
    state.scanId = null;
    resetScanViews();
    document.querySelector('[data-empty-for="status"]').hidden = false;
    showNotice("Scan cleared.", "success");
    await refresh();
  }

  // Start -----------------------------------------------------------------

  async function loadVersion() {
    const version = await api("/version");
    byId("version").textContent = `Version ${version.version} (${version.revision})`;
  }

  function bindEvents() {
    byId("scan-form").addEventListener("submit", (event) => run(() => startScan(event)));
    byId("profile-select").addEventListener("change", () => run(selectProfile));
    byId("plugin-filter").addEventListener("input", filterPlugins);
    byId("log-filter").addEventListener("change", applyLogFilter);
    byId("findings-filter").addEventListener("input", renderFindings);
    byId("urls-filter").addEventListener("input", renderUrls);
    byId("traffic-form").addEventListener("submit", (event) => run(() => lookupTraffic(event)));
    byId("pause-button").addEventListener("click", () => run(() => scanAction("pause", "Scan paused.")));
    byId("resume-button").addEventListener("click", () => run(() => scanAction("resume", "Scan resumed.")));
    byId("stop-button").addEventListener("click", () => run(() => scanAction("stop", "Stopping the scan.")));
    byId("delete-button").addEventListener("click", () => run(deleteScan));
  }

  async function start() {
    setupTabs();
    bindEvents();
    await run(async () => {
      await Promise.all([loadVersion(), loadPlugins(), loadProfiles()]);
      await findCurrentScan();
      await refresh();
    });
    schedulePolling();
  }

  document.addEventListener("DOMContentLoaded", start);
})();
