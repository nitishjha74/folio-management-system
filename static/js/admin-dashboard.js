(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const { api, escapeHtml, toast, requireRole } = window.folioApi;

  let folios = [];

  async function loadFolios() {
    folios = await api("/api/folios");
    const opts = folios
      .map((f) => `<option value="${f.id}">${escapeHtml(f.name)}</option>`)
      .join("");
    const sel = $("adminFolio");
    const prev = sel.value;
    sel.innerHTML = opts;
    if (prev) sel.value = prev;
    renderOutgoingOptions();
  }

  function renderOutgoingOptions() {
    const folio = folios.find((f) => String(f.id) === $("adminFolio").value);
    const sel = $("outgoingTicker");
    if (!folio) { sel.innerHTML = ""; return; }
    sel.innerHTML = folio.stocks
      .map((s) =>
        `<option value="${escapeHtml(s.ticker)}">${escapeHtml(s.ticker)} (base ${s.base_quantity})</option>`)
      .join("");
  }

  async function loadTickers() {
    const tickers = await api("/api/admin/tickers");
    $("tickerOptions").innerHTML =
      tickers.map((t) => `<option value="${escapeHtml(t)}"></option>`).join("");
  }

  async function loadJobs() {
    const list = $("jobList");
    try {
      const jobs = await api("/api/admin/rebalances");
      if (!jobs.length) {
        list.innerHTML = '<li class="muted">No rebalance jobs yet.</li>';
        return;
      }
      list.innerHTML = jobs.slice(0, 10).map((j) => `
        <li class="list-item">
          <div>
            <div>
              ${escapeHtml(j.outgoing_ticker)} → <strong>${escapeHtml(j.incoming_ticker)}</strong>
              <span class="badge">${escapeHtml(j.status)}</span>
            </div>
            <div class="muted">
              ${escapeHtml(j.folio_name)} ·
              subs ${j.subscribers_processed}/${j.subscribers_total}
              (skipped ${j.subscribers_skipped}) ·
              orders ${j.orders_created}
            </div>
          </div>
          <span class="muted tick">${escapeHtml(j.id)}</span>
        </li>`).join("");
    } catch (err) {
      list.innerHTML = `<li class="muted">${escapeHtml(err.message)}</li>`;
    }
  }

  async function triggerRebalance() {
    const btn = $("rebalanceBtn");
    btn.disabled = true;
    try {
      const rawQty = $("incomingQty").value.trim();
      const payload = {
        folio_id: Number($("adminFolio").value),
        outgoing_ticker: $("outgoingTicker").value,
        incoming_ticker: $("incomingTicker").value.trim().toUpperCase(),
      };
      if (rawQty) payload.incoming_base_quantity = Number(rawQty);

      const started = performance.now();
      const result = await api("/api/admin/rebalance", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const elapsed = Math.round(performance.now() - started);

      toast(`${result.message}\nAPI responded in ${elapsed} ms.`, "ok");
      $("rebalanceHint").textContent =
        `${result.outgoing_ticker} → ${result.incoming_ticker} · job ${result.job_id}`;
      $("incomingTicker").value = "";
      $("incomingQty").value = "";

      await Promise.all([loadFolios(), loadJobs()]);
    } catch (err) {
      toast(err.message, "err");
    } finally {
      btn.disabled = false;
    }
  }

  async function init() {
    const me = await requireRole("ADMIN");
    if (!me) return;

    $("adminFolio").addEventListener("change", renderOutgoingOptions);
    $("rebalanceBtn").addEventListener("click", triggerRebalance);

    await Promise.all([loadFolios(), loadTickers(), loadJobs()]);
    setInterval(loadJobs, 5000);
  }

  init();
})();