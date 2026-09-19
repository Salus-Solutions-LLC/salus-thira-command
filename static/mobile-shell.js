(() => {
  "use strict";

  const MOBILE_QUERY = "(max-width: 760px)";

  function initializeMobileShell() {
    const sidebar = document.querySelector(".sidebar");
    const topbar = document.querySelector(".topbar");
    if (!sidebar || !topbar || document.querySelector(".mobile-nav-toggle")) return;

    if (!sidebar.id) sidebar.id = "salcapa-navigation";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "mobile-nav-toggle";
    toggle.setAttribute("aria-controls", sidebar.id);
    toggle.setAttribute("aria-expanded", "false");
    toggle.textContent = "Menu";

    const backdrop = document.createElement("button");
    backdrop.type = "button";
    backdrop.className = "mobile-nav-backdrop";
    backdrop.setAttribute("aria-label", "Close navigation");
    backdrop.tabIndex = -1;

    topbar.insertBefore(toggle, topbar.firstChild);
    document.body.appendChild(backdrop);

    const mobile = window.matchMedia(MOBILE_QUERY);

    function setOpen(open, returnFocus = false) {
      const shouldOpen = mobile.matches && open;
      document.body.classList.toggle("mobile-nav-open", shouldOpen);
      toggle.setAttribute("aria-expanded", String(shouldOpen));
      if (mobile.matches) {
        sidebar.setAttribute("aria-hidden", String(!shouldOpen));
      } else {
        sidebar.removeAttribute("aria-hidden");
      }
      if (shouldOpen) {
        const firstControl = sidebar.querySelector("button, summary, a[href]");
        if (firstControl) firstControl.focus();
      } else if (returnFocus && mobile.matches) {
        toggle.focus();
      }
    }

    toggle.addEventListener("click", () => {
      setOpen(!document.body.classList.contains("mobile-nav-open"));
    });
    backdrop.addEventListener("click", () => setOpen(false, true));
    sidebar.addEventListener("click", event => {
      if (event.target.closest("button[data-view]")) setOpen(false);
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && document.body.classList.contains("mobile-nav-open")) {
        setOpen(false, true);
      }
    });

    const synchronize = () => setOpen(false);
    if (typeof mobile.addEventListener === "function") {
      mobile.addEventListener("change", synchronize);
    } else {
      mobile.addListener(synchronize);
    }
    synchronize();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeMobileShell, { once: true });
  } else {
    initializeMobileShell();
  }
})();
