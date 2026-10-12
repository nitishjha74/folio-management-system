(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  console.log("[dash] app.js loaded, role =", window.__requireRole);

  // ------------------------------------------------------------- helpers

  function readCookie(name) {
    const pair = document.cookie.split("; ").find((c) => c.startsWith(name + "="));
    return pair ? decodeURIComponent(pair.split("=").slice(1).join("=")) : null;
  }

  async function api(path, options = {}) {
    const csrf = readCookie("folio_csrf_token");
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (csrf) headers["X-CSRF-Token"] = csrf;

    const res = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers,
    });

    const text = await res.text();
    const body = text ? JSON.parse(text) : null;
    if (!res.ok) {
      const msg = body && body.message ? body.message : `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return body;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ------------------------------------------------------------- logout

  async function logout() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch { /* ignore */ }
    window.location.href = "/";
  }

  // ------------------------------------------------------------- init

  async function init() {
    const required = window.__requireRole;
    const fallback = window.__fallbackUrl || "/";

    if (!required) {
      console.error("[dash] window.__requireRole not set — check the HTML");
      return;
    }

    let me;
    try {
      me = await api("/api/auth/me");
      console.log("[dash] me =", me);
    } catch (err) {
      console.warn("[dash] /me failed:", err.message);
      window.location.href = "/";
      return;
    }

    if (me.role !== required) {
      window.location.href = fallback;
      return;
    }

    const who = $("who");
    if (who) who.textContent = me.email || me.user_id;

    const logoutBtn = $("logoutBtn");
    if (logoutBtn) logoutBtn.addEventListener("click", logout);

    if (required === "ADMIN") {
      await loadAdminData();
    } else {
      await loadUserData(me);
    }
  }

  // ------------------------------------------------------------- admin

  async function loadAdminData() {
    const list = $("jobList");
    if (!list) return;
    try {
      const jobs = await api("/api/admin/rebalances");
      if (!jobs.length) {
        list.innerHTML = '<li class="muted">No rebalance jobs yet.</li>';
        return;
      }
      list.innerHTML = jobs.slice(0, 10).map((j) => `
        <li class="list-item">
          <div>
            <strong>${escapeHtml(j.outgoing_ticker)} → ${escapeHtml(j.incoming_ticker)}</strong>
            <span class="badge">${escapeHtml(j.status)}</span>
          </div>
          <div class="muted">
            ${escapeHtml(j.folio_name)} · subs ${j.subscribers_processed}/${j.subscribers_total}
          </div>
        </li>`).join("");
    } catch (err) {
      list.innerHTML = `<li class="muted">${escapeHtml(err.message)}</li>`;
    }
  }

  // ------------------------------------------------------------- user

  async function loadUserData(me) {
    const subList = $("subscriptionList");
    const feed = $("orderFeed");

    if (subList) {
      try {
        const subs = await api(
          `/api/users/${encodeURIComponent(me.user_id)}/subscriptions?active_only=true`
        );
        if (!subs.length) {
          subList.innerHTML = '<li class="muted">No active subscriptions.</li>';
        } else {
          subList.innerHTML = subs.map((s) => `
            <li class="list-item">
              <div>
                <strong>${escapeHtml(s.folio_name || s.folio_id)}</strong>
                <span class="badge">${s.multiplier}x</span>
              </div>
              <div class="muted">${s.positions.length} positions</div>
            </li>`).join("");
        }
      } catch (err) {
        subList.innerHTML = `<li class="muted">${escapeHtml(err.message)}</li>`;
      }
    }

    if (feed) {
      try {
        const page = await api("/api/orders?limit=20");
        if (!page.items.length) {
          feed.innerHTML = '<li class="muted">No orders yet.</li>';
        } else {
          feed.innerHTML = page.items.map((o) => `
            <li class="list-item">
              <div>
                <span class="${o.action === 'BUY' ? 'buy' : 'sell'}">${escapeHtml(o.action)}</span>
                <strong>${escapeHtml(o.ticker)}</strong> × ${o.quantity}
              </div>
              <div class="muted">${escapeHtml(o.source)} · ${escapeHtml(o.status)}</div>
            </li>`).join("");
        }
      } catch (err) {
        feed.innerHTML = `<li class="muted">${escapeHtml(err.message)}</li>`;
      }
    }
  }

  init();
})();