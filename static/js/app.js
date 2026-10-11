(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = { folios: [], subs: [] };

  // ---------------------------------------------------------------- helpers

  function toast(message, kind = "ok") {
    const el = $("toast");
    el.className = `toast ${kind}`;
    el.textContent = message;
    clearTimeout(el._t);
    el._t = setTimeout(() => {
      el.className = "toast";
      el.textContent = "";
    }, 5000);
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const text = await res.text();
    const body = text ? JSON.parse(text) : null;
    if (!res.ok) {
      // Error shape from main.py:
      //   {success:false,message:"…",data:null}
      //   {message:"Field Validation Error",errors:{field:"…"}}
      let detail = `HTTP ${res.status}`;
      if (body) {
        if (typeof body.message === "string") detail = body.message;
        if (body.errors && typeof body.errors === "object") {
          detail += "\n" + Object.entries(body.errors)
            .map(([f, m]) => `• ${f}: ${m}`)
            .join("\n");
        }
        if (!detail && typeof body.detail === "string") detail = body.detail;
      }
      throw new Error(detail);
    }
    return body;
  }

  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const userId = () => $("userId").value.trim() || "user-101";

  // ----------------------------------------------------------------- folios

  async function loadFolios() {
    state.folios = await api("/api/folios");

    const opts = state.folios
      .map((f) => `<option value="${esc(f.id)}">${esc(f.name)}</option>`)
      .join("");

    for (const sel of [$("folioSelect"), $("adminFolio")]) {
      const prev = sel.value;
      sel.innerHTML = opts;
      if (prev) sel.value = prev;
    }
    renderOutgoingOptions();
  }

  function renderOutgoingOptions() {
    const folio = state.folios.find((f) => String(f.id) === $("adminFolio").value);
    const sel = $("outgoingTicker");
    if (!folio) { sel.innerHTML = ""; return; }
    sel.innerHTML = folio.stocks
      .map((s) =>
        `<option value="${esc(s.ticker)}">${esc(s.ticker)} (base ${s.base_quantity})</option>`)
      .join("");
  }

  async function loadTickers() {
    const tickers = await api("/api/admin/tickers");
    $("tickerOptions").innerHTML =
      tickers.map((t) => `<option value="${esc(t)}"></option>`).join("");
  }

  // ------------------------------------------------------------- subscribe

  async function subscribe() {
    const btn = $("subscribeBtn");
    btn.disabled = true;
    try {
      const payload = {
        user_id: userId(),
        folio_id: Number($("folioSelect").value),
        multiplier: Number($("multiplier").value),
      };
      const result = await api("/api/subscriptions", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const sub = result.subscription;
      toast(
        `Subscribed ${sub.folio_name} @ ${sub.multiplier}x\n` +
        `${result.orders.length} BUY orders executed.`,
        "ok",
      );
      await refresh();
    } catch (err) {
      toast(err.message, "err");
    } finally {
      btn.disabled = false;
    }
  }

  async function loadSubscriptions() {
    try {
      const subs = await api(
        `/api/users/${encodeURIComponent(userId())}/subscriptions?active_only=true`,
      );
      state.subs = subs;

      const list = $("subscriptionList");
      if (!subs.length) {
        list.innerHTML =
          `<li class="muted">No active subscriptions for ${esc(userId())}.</li>`;
        return;
      }
      list.innerHTML = subs.map((s) => `
        <li class="item">
          <div>
            <div>
              <strong>${esc(s.folio_name || s.folio_id)}</strong>
              <span class="badge">${s.multiplier}x</span>
            </div>
            <div class="muted">
              ${s.positions.length} positions · ${esc(s.id)}
            </div>
          </div>
          <button class="ghost danger" data-exit="${esc(s.id)}">EXIT</button>
        </li>`).join("");

      list.querySelectorAll("[data-exit]").forEach((b) => {
        b.addEventListener("click", () => exitSubscription(b.dataset.exit));
      });
    } catch (err) {
      $("subscriptionList").innerHTML =
        `<li class="muted">${esc(err.message)}</li>`;
    }
  }

  async function exitSubscription(id) {
    try {
      const result = await api(`/api/subscriptions/${encodeURIComponent(id)}/exit`, {
        method: "POST",
      });
      toast(
        `Exited ${result.subscription.folio_name}.\n` +
        `${result.orders.length} SELL orders executed.`,
        "ok",
      );
      await refresh();
    } catch (err) {
      toast(err.message, "err");
    }
  }

  // ------------------------------------------------------------- rebalance

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

      toast(
        `${result.message}\nAPI responded in ${elapsed} ms.`,
        "ok",
      );
      $("rebalanceHint").textContent =
        `${result.outgoing_ticker} → ${result.incoming_ticker} · job ${result.job_id}`;
      $("incomingTicker").value = "";
      $("incomingQty").value = "";

      await Promise.all([loadFolios(), loadJobs(), loadOrders()]);
    } catch (err) {
      toast(err.message, "err");
    } finally {
      btn.disabled = false;
    }
  }

  async function loadJobs() {
    try {
      const jobs = await api("/api/admin/rebalances");
      const list = $("jobList");
      if (!jobs.length) {
        list.innerHTML = `<li class="muted">No jobs yet.</li>`;
        return;
      }
      list.innerHTML = jobs.slice(0, 6).map((j) => `
        <li class="item">
          <div>
            <div>
              ${esc(j.outgoing_ticker)} → <strong>${esc(j.incoming_ticker)}</strong>
              <span class="badge">${esc(j.status)}</span>
            </div>
            <div class="muted">
              ${esc(j.folio_name)} · subs ${j.subscribers_processed}/${j.subscribers_total}
              (skipped ${j.subscribers_skipped}) · orders ${j.orders_created}
            </div>
          </div>
          <span class="muted tick">${esc(j.id)}</span>
        </li>`).join("");
    } catch { /* non-critical */ }
  }

  // ---------------------------------------------------------- order feed

  async function loadOrders() {
    try {
      const page = await api("/api/orders?limit=60");
      const feed = $("orderFeed");
      if (!page.items.length) {
        feed.innerHTML = `<div class="muted">No orders yet.</div>`;
        return;
      }
      const atBottom =
        feed.scrollTop + feed.clientHeight >= feed.scrollHeight - 24;

      feed.innerHTML = page.items.map((o) => `
        <div class="ord">
          <span class="${o.action === "BUY" ? "buy" : "sell"}">${esc(o.action)}</span>
          <span>
            <span class="tick">${esc(o.ticker)}</span> × ${o.quantity}
            <span class="muted">· ${esc(o.user_id)} · ${esc(o.source)}</span>
          </span>
          <span class="muted">${esc(o.status)}</span>
        </div>`).join("");

      if (atBottom) feed.scrollTop = feed.scrollHeight;
    } catch { /* non-critical */ }
  }

  // ------------------------------------------------------------ wiring

  async function refresh() {
    await Promise.all([loadSubscriptions(), loadOrders(), loadJobs()]);
  }

  $("subscribeBtn").addEventListener("click", subscribe);
  $("rebalanceBtn").addEventListener("click", triggerRebalance);
  $("adminFolio").addEventListener("change", renderOutgoingOptions);
  $("userId").addEventListener("change", loadSubscriptions);
  $("userId").addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadSubscriptions();
  });

  (async function init() {
    try {
      await Promise.all([loadFolios(), loadTickers()]);
      await refresh();
      setInterval(refresh, 2000);
    } catch (err) {
      toast(`Init failed: ${err.message}`, "err");
    }
  })();
})();