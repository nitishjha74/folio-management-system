(() => {
  "use strict";

  function readCookie(name) {
    const pair = document.cookie.split("; ").find((c) => c.startsWith(name + "="));
    return pair ? decodeURIComponent(pair.split("=").slice(1).join("=")) : null;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
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
      let msg = `HTTP ${res.status}`;
      if (body) {
        if (typeof body.message === "string") msg = body.message;
        if (body.errors && typeof body.errors === "object") {
          msg += "\n" + Object.entries(body.errors)
            .map(([f, m]) => `• ${f}: ${m}`).join("\n");
        }
      }
      throw new Error(msg);
    }
    return body;
  }

  function toast(message, kind = "ok") {
    const el = document.getElementById("toast");
    if (!el) return;
    el.className = `toast ${kind}`;
    el.textContent = message;
    clearTimeout(el._t);
    el._t = setTimeout(() => {
      el.className = "toast";
      el.textContent = "";
    }, 5000);
  }

  async function logout() {
    try { await api("/api/auth/logout", { method: "POST" }); } catch {}
    window.location.href = "/";
  }

  async function requireRole(role) {
    let me;
    try {
      me = await api("/api/auth/me");
    } catch {
      window.location.href = "/";
      return null;
    }
    if (me.role !== role) {
      window.location.href = me.role === "ADMIN" ? "/admin/dashboard" : "/user/dashboard";
      return null;
    }
    const who = document.getElementById("who");
    if (who) who.textContent = me.email || me.user_id;
    const btn = document.getElementById("logoutBtn");
    if (btn) btn.addEventListener("click", logout);
    return me;
  }

  // Expose on window for the page-specific scripts
  window.folioApi = { api, escapeHtml, readCookie, toast, logout, requireRole };
})();