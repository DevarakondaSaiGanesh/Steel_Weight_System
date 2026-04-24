async function mountNav(activePath) {
  let me;
  try { me = await api("/api/me"); }
  catch (_) { return null; }
  if (me.firstLogin && !location.pathname.endsWith("/change-password.html")) {
    location.href = "/change-password.html";
    return null;
  }

  const isAdmin = me.role === "admin";
  const link = (href, icon, label) => {
    const active = activePath === href ? " active" : "";
    return `<li class="nav-item"><a class="nav-link${active}" href="${href}"><i class="bi ${icon}"></i> ${label}</a></li>`;
  };

  const navHtml = `
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
      <div class="container-fluid">
        <a class="navbar-brand fw-bold" href="/"><i class="bi bi-bricks"></i> Steel Weight System</a>
        <button class="navbar-toggler" data-bs-toggle="collapse" data-bs-target="#nav">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="nav">
          <ul class="navbar-nav me-auto mb-2 mb-lg-0">
            ${isAdmin ? link("/admin.html", "bi-speedometer2", "Dashboard") : ""}
            ${isAdmin ? link("/users.html", "bi-people", "Users") : ""}
            ${isAdmin ? link("/admin-projects.html", "bi-folder", "Projects") : ""}
            ${link("/projects.html", "bi-clipboard-data", "My Projects")}
          </ul>
          <span class="navbar-text text-light me-3">
            <i class="bi bi-person-circle"></i> ${escapeHtml(me.username)}
            <span class="badge bg-secondary text-uppercase">${escapeHtml(me.role)}</span>
          </span>
          <button class="btn btn-outline-light btn-sm" onclick="logout()">
            <i class="bi bi-box-arrow-right"></i> Logout
          </button>
        </div>
      </div>
    </nav>`;
  const slot = el("nav-slot");
  if (slot) slot.outerHTML = navHtml;
  return me;
}
