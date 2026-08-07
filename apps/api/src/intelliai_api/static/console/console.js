/* IntelliAI Console Kit — shared shell, navigation, and API client.
 *
 * Every console page includes this file, declares <body data-page="...">,
 * and provides #iai-sidebar / #iai-topbar mount points inside the shell
 * grid. Navigation lives HERE and only here: adding a service or page to
 * the platform is one entry in NAV (and one in SERVICES if it is an AI
 * service) — no page edits anywhere else.
 *
 * The public product rule applies throughout: customers see IntelliAI
 * services (IntelliAI STT), never foundation-model names.
 */
"use strict";
window.IntelliAI = (function () {
  var KEY_STORAGE = "intelliai_api_key"; /* shared with the playground since launch */

  /* status: "live" = page exists; "soon" = visible in the IA, not yet open. */
  var NAV = [
    { title: null, items: [
      { id: "dashboard", label: "Dashboard", href: "/console", status: "live" }
    ] },
    { title: "Build", items: [
      { id: "keys", label: "API Keys", href: "/console/keys", status: "live" },
      { id: "playground", label: "Playground", href: "/console/playground", status: "live" },
      { id: "services", label: "AI Services", href: "/console/services", status: "soon" }
    ] },
    { title: "Data", items: [
      { id: "samples", label: "Speech Samples", href: "/console/samples", status: "soon" },
      { id: "datasets", label: "Datasets", href: "/console/datasets", status: "soon" }
    ] },
    { title: "Monitor", items: [
      { id: "usage", label: "Usage", href: "/console/usage", status: "soon" },
      { id: "logs", label: "Logs", href: "/console/logs", status: "soon" }
    ] },
    { title: "Organization", items: [
      { id: "settings", label: "Settings", href: "/console/settings", status: "soon" },
      { id: "billing", label: "Billing", href: "/console/billing", status: "soon" }
    ] }
  ];

  /* The platform's public services. The console shows SERVICES, customers
   * never think about foundation models. */
  var SERVICES = [
    {
      name: "IntelliAI STT",
      desc: "Speech to text in English, with Hindi and Arabic in beta - and human-correction capture built in.",
      status: "production",
      href: "/console/playground",
      cta: "Open Playground"
    },
    { name: "IntelliAI TTS", desc: "Natural speech from text.", status: "soon" },
    { name: "IntelliAI OCR", desc: "Text from images and documents.", status: "soon" },
    { name: "IntelliAI Translate", desc: "Translation across Indian and global languages.", status: "soon" },
    { name: "IntelliAI Vision", desc: "Understanding for images and video.", status: "soon" },
    { name: "IntelliAI LLM", desc: "Reasoning and generation APIs.", status: "soon" }
  ];

  /* ── tiny DOM helper: attributes + children, no innerHTML ──── */
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (name) {
        node.setAttribute(name, attrs[name]);
      });
    }
    (children || []).forEach(function (child) {
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  }

  /* ── API key (browser-local only, never sent anywhere but our API) ── */
  function getKey() { return (localStorage.getItem(KEY_STORAGE) || "").trim(); }
  function setKey(value) { localStorage.setItem(KEY_STORAGE, (value || "").trim()); }
  function clearKey() { localStorage.removeItem(KEY_STORAGE); }

  /* ── API client: bearer auth + platform error envelope ─────── */
  function apiJSON(path, options) {
    var opts = Object.assign({}, options);
    opts.headers = Object.assign({}, opts.headers);
    var key = getKey();
    if (key) opts.headers["Authorization"] = "Bearer " + key;
    return fetch(path, opts).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (body) {
        if (!response.ok) {
          var message = (body && body.error && body.error.message) || "Request failed.";
          var error = new Error(message);
          error.status = response.status;
          throw error;
        }
        return body;
      });
    });
  }

  /* ── identity: resolve the organization behind the stored key ──
   * Resolves to the organization object, or null when no key is stored.
   * Rejects (with .status === 401) when the stored key is refused.
   * One request is shared by every surface on the page (chip, dashboard)
   * so they can never disagree; pass fresh=true after changing the key. */
  var identityRequest = null;
  function identity(fresh) {
    if (!getKey()) return Promise.resolve(null);
    if (!identityRequest || fresh) {
      identityRequest = apiJSON("/v1/organization").catch(function (error) {
        identityRequest = null; /* never cache a failure */
        throw error;
      });
    }
    return identityRequest;
  }

  /* ── shell rendering ───────────────────────────────────────── */
  function brand() {
    return el("a", { class: "brand", href: "/console" }, [
      el("span", { class: "brand-mark", "aria-hidden": "true" }, ["iA"]),
      el("span", { class: "brand-name" }, ["IntelliAI", el("small", {}, ["Platform"])])
    ]);
  }

  function navItem(item, page) {
    if (item.status !== "live") {
      return el("span", { class: "nav-item is-soon", "aria-disabled": "true" }, [
        item.label,
        el("span", { class: "badge badge-soon" }, ["Soon"])
      ]);
    }
    var attrs = { class: "nav-item" + (item.id === page ? " is-active" : ""), href: item.href };
    if (item.id === page) attrs["aria-current"] = "page";
    return el("a", attrs, [item.label]);
  }

  function pageTitle(page) {
    var title = "IntelliAI";
    NAV.forEach(function (section) {
      section.items.forEach(function (item) {
        if (item.id === page) title = item.label;
      });
    });
    return title;
  }

  function renderShell() {
    var page = document.body.getAttribute("data-page") || "";
    var sidebar = document.getElementById("iai-sidebar");
    var topbar = document.getElementById("iai-topbar");
    if (!sidebar || !topbar) return;

    sidebar.appendChild(brand());
    var nav = el("nav", { class: "nav", "aria-label": "Platform" });
    NAV.forEach(function (section) {
      var wrap = el("div", { class: "nav-section" });
      if (section.title) wrap.appendChild(el("p", { class: "nav-title" }, [section.title]));
      section.items.forEach(function (item) { wrap.appendChild(navItem(item, page)); });
      nav.appendChild(wrap);
    });
    sidebar.appendChild(nav);
    sidebar.appendChild(el("div", { class: "nav-foot" }, [
      el("a", { class: "nav-item", href: "/docs", target: "_blank", rel: "noopener" }, ["Documentation"])
    ]));

    var menuBtn = el("button", {
      class: "menu-btn",
      "aria-label": "Open navigation",
      "aria-expanded": "false",
      "aria-controls": "iai-sidebar"
    }, ["☰"]);
    function setNavOpen(open) {
      document.body.classList.toggle("nav-open", open);
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    }
    menuBtn.addEventListener("click", function () {
      setNavOpen(!document.body.classList.contains("nav-open"));
    });
    var scrim = el("div", { class: "scrim", "aria-hidden": "true" });
    scrim.addEventListener("click", function () { setNavOpen(false); });
    document.body.appendChild(scrim);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setNavOpen(false);
    });

    var chip = el("a", { class: "chip off", href: "/console", id: "iai-chip" }, [
      el("span", { class: "dot", "aria-hidden": "true" }),
      el("span", { id: "iai-chip-text" }, ["Not connected"])
    ]);
    topbar.appendChild(menuBtn);
    topbar.appendChild(el("h1", { class: "page-title" }, [pageTitle(page)]));
    topbar.appendChild(chip);
  }

  function setChip(state, text) {
    var chip = document.getElementById("iai-chip");
    var label = document.getElementById("iai-chip-text");
    if (!chip || !label) return;
    chip.className = "chip " + state;
    label.textContent = text; /* textContent: org names render inert */
  }

  function refreshIdentity(fresh) {
    return identity(fresh).then(function (org) {
      if (org) setChip("on", org.name);
      else setChip("off", "Not connected");
      return org;
    }).catch(function (error) {
      setChip(error.status === 401 ? "err" : "off",
        error.status === 401 ? "Key rejected" : "Offline");
      return null;
    });
  }

  /* ── services grid (dashboard now, AI Services page later) ─── */
  function renderServices(container) {
    SERVICES.forEach(function (service) {
      var live = service.status === "production";
      var card = el("div", { class: "card service-card" + (live ? "" : " is-soon") }, [
        el("div", { class: "service-head" }, [
          el("h3", {}, [service.name]),
          el("span", { class: "badge " + (live ? "badge-live" : "badge-soon") },
            [live ? "Production" : "Coming Soon"])
        ]),
        el("p", {}, [service.desc])
      ]);
      if (live && service.href) {
        card.appendChild(el("a", { class: "goto", href: service.href }, [service.cta + " →"]));
      }
      container.appendChild(card);
    });
  }

  /* ── copy-to-clipboard for .copy-btn[data-copy-target] ─────── */
  function bindCopyButtons() {
    document.addEventListener("click", function (event) {
      var btn = event.target.closest ? event.target.closest(".copy-btn") : null;
      if (!btn) return;
      var target = document.getElementById(btn.getAttribute("data-copy-target"));
      if (!target) return;
      /* Capture the resting label ONCE, and cancel any pending restore,
       * so rapid clicks can never make a feedback label permanent. */
      if (!btn.dataset.label) btn.dataset.label = btn.textContent;
      function flash(label) {
        btn.textContent = label;
        clearTimeout(btn._copyTimer);
        btn._copyTimer = setTimeout(function () { btn.textContent = btn.dataset.label; }, 1500);
      }
      if (!navigator.clipboard) { flash("Copy failed"); return; }
      navigator.clipboard.writeText(target.textContent).then(
        function () { flash("Copied"); },
        function () { flash("Copy failed"); }
      );
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderShell();
    refreshIdentity();
    bindCopyButtons();
  });

  return {
    NAV: NAV,
    SERVICES: SERVICES,
    el: el,
    getKey: getKey,
    setKey: setKey,
    clearKey: clearKey,
    apiJSON: apiJSON,
    identity: identity,
    refreshIdentity: refreshIdentity,
    renderServices: renderServices
  };
})();
