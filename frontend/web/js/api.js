async function api(path, opts = {}) {
  const init = { credentials: "same-origin", headers: {}, ...opts };
  if (init.body && typeof init.body !== "string") {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(init.body);
  }
  const res = await fetch(path, init);
  if (res.status === 401) {
    if (!location.pathname.endsWith("/login.html")) {
      location.href = "/login.html";
    }
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    let msg = "Request failed";
    try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function logout() {
  try { await api("/api/logout", { method: "POST" }); } catch (_) {}
  location.href = "/login.html";
}

function el(id) { return document.getElementById(id); }

function fmtDate(s) {
  if (!s) return "";
  return s.slice(0, 19).replace("T", " ");
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}
