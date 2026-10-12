(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const { api, escapeHtml, toast, requireRole } = window.folioApi;

  let me = null;
  let folios = [];

  async function loadFolios() {
    folios = await api("/api/folios");
    $("folioSelect").innerHTML = folios
      .map((f) => `<option value="${f.id}">${escapeHtml(f.name)}</option>`)
      .join("");
  }

  async function loadSubscriptions() {
    const list = $("subscriptionList");
    try {
      const subs = await api(
        `/api/users/${encodeURIComponent(me.user_id)}/subscriptions?active_only=true`
      );
      if (!subs.length) {
        list.innerHTML = '<li class="muted">No active subscriptions.</li>';
        return;
      }
      list.innerHTML = subs.map((s) => `
        <li class="list-item">
          <div>
            <div>
              <strong>${escapeHtml(s.folio_name || s.folio_id)}</strong>
              <span class="badge">${s.multiplier}x</span>
            </div>
            <div class="muted">${s.positions.length} positions · ${escapeHtml(s.id)}</div>
          </div>
          <button class="exit-btn" data-exit="${escapeHtml(s.id)}">EXIT</button>
        </li>`).join("");

      list.querySelectorAll("[data-exit]").forEach((b) =>
        b.addEventListener("click", () => exitSubscription(b.dataset.exit)));
    } catch (err) {
      list.innerHTML = `<li class="muted">${escapeHtml(err.message)}</li>`;
    }
  }

  async function loadOrders() {
    const feed = $("orderFeed");
    try {
      const page = await api("/api/orders?limit=40");
      if (!page.items.length) {
        feed.innerHTML = '<li class="muted">No orders yet.</li>';
        return;
      }
      feed.innerHTML = page.items.map((o) => `
        <li class="list-item">
          <div>
            <span class="${o.action === "BUY" ? "buy" : "sell"}">${escapeHtml(o.action)}</span>
            <span class="tick">${escapeHtml(o.ticker)}</span> × ${o.quantity}
            <span class="muted">· ${escapeHtml(o.source)}</span>
          </div>
          <span class="muted">${escapeHtml(o.status)}</span>
        </li>`).join("");
    } catch (err) {
      feed.innerHTML = `<li class="muted">${escapeHtml(err.message)}</li>`;
    }
  }

  async function subscribe() {
    const btn = $("subscribeBtn");
    btn.disabled = true;
    try {
      const payload = {
        user_id: me.user_id,
        folio_id: Number($("folioSelect").value),
        multiplier: Number($("multiplier").value),
      };
      const result = await api("/api/subscriptions", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      toast(
        `Subscribed ${result.subscription.folio_name} @ ${result.subscription.multiplier}x\n` +
        `${result.orders.length} BUY orders executed.`,
        "ok",
      );
      await Promise.all([loadSubscriptions(), loadOrders()]);
    } catch (err) {
      toast(err.message, "err");
    } finally {
      btn.disabled = false;
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
      await Promise.all([loadSubscriptions(), loadOrders()]);
    } catch (err) {
      toast(err.message, "err");
    }
  }

  async function init() {
    me = await requireRole("USER");
    if (!me) return;

    $("subscribeBtn").addEventListener("click", subscribe);

    await Promise.all([loadFolios(), loadSubscriptions(), loadOrders()]);
    setInterval(() => { loadSubscriptions(); loadOrders(); }, 5000);
  }

  init();
})();