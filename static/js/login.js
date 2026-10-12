(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const { api } = window.folioApi;

  function showError(message) {
    const box = $("errorBox");
    if (!box) return;
    box.textContent = message;
    box.hidden = !message;
  }

  function setLoading(btnId, loading, busyText, idleText) {
    const btn = $(btnId);
    if (!btn) return;
    btn.disabled = loading;
    const label = btn.querySelector(".btn-label");
    const spin = btn.querySelector(".btn-spinner");
    if (label) label.textContent = loading ? busyText : idleText;
    if (spin) spin.hidden = !loading;
  }

  function redirectFor(role) {
    if (role === "ADMIN") {
      window.location.href = "/admin/dashboard";
    } else if (role === "USER") {
      window.location.href = "/user/dashboard";
    } else {
      showError("Your account does not have an authorized role.");
    }
  }

  function wirePasswordToggle() {
    const btn = $("togglePassword");
    const input = $("password");
    if (!btn || !input) return;
    btn.addEventListener("click", () => {
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.textContent = showing ? "Show" : "Hide";
    });
  }

  async function handleLogin(event) {
    event.preventDefault();
    showError("");
    setLoading("loginBtn", true, "Signing in…", "Sign in");

    try {
      const email = $("email").value.trim();
      const password = $("password").value;
      if (!email || !password) throw new Error("Please enter both email and password.");

      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      redirectFor(data.user.role);
    } catch (err) {
      showError(err.message);
    } finally {
      setLoading("loginBtn", false, "Signing in…", "Sign in");
    }
  }

  async function handleRegister(event) {
    event.preventDefault();
    showError("");
    setLoading("registerBtn", true, "Creating…", "Create account");

    try {
      const email = $("email").value.trim();
      const password = $("password").value;
      const fullName = $("fullName") ? $("fullName").value.trim() : "";

      if (!email || !password) throw new Error("Email and password are required.");
      if (password.length < 8) throw new Error("Password must be at least 8 characters.");

      const body = { email, password };
      if (fullName) body.full_name = fullName;

      const data = await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(body),
      });
      redirectFor(data.user.role);   // always USER after register
    } catch (err) {
      showError(err.message);
    } finally {
      setLoading("registerBtn", false, "Creating…", "Create account");
    }
  }

  const yearEl = $("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  wirePasswordToggle();

  if ($("loginForm")) {
    $("loginForm").addEventListener("submit", handleLogin);
    (async () => {
      try {
        const me = await api("/api/auth/me");
        redirectFor(me.role);
      } catch { /* not signed in */ }
    })();
  }

  if ($("registerForm")) {
    $("registerForm").addEventListener("submit", handleRegister);
  }
})();