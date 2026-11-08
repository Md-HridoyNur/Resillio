"use strict";
const $ = (s) => document.querySelector(s),
  $$ = (s) => [...document.querySelectorAll(s)];
const state = {
  public: null,
  private: null,
  lastAccount: null,
  online: false,
  screen: "overview",
  filters: {
    search: "",
    category: "",
    area: "",
    urgency: "",
    availability: "",
    division: "",
    district: "",
    upazila: "",
  },
};
function el(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined && text !== null) n.textContent = String(text);
  if (cls) n.className = cls;
  return n;
}
function button(text, fn, cls = "") {
  const b = el("button", text, cls);
  b.type = "button";
  b.addEventListener("click", () => {
    try {
      Promise.resolve(fn()).catch((error) => message(error.message, true));
    } catch (error) {
      message(error.message, true);
    }
  });
  return b;
}
function append(parent, ...nodes) {
  nodes.forEach((n) => parent.append(n));
  return parent;
}
function message(text, error = false) {
  const n = $("#status");
  n.hidden = false;
  n.textContent = text;
  n.className = error ? "notice warning" : "notice";
}
function ago(date) {
  const m = Math.max(0, Math.floor((Date.now() - new Date(date)) / 60000));
  return m < 1
    ? "just now"
    : m < 60
      ? `${m} min ago`
      : m < 1440
        ? `${Math.floor(m / 60)} h ago`
        : `${Math.floor(m / 1440)} d ago`;
}
function num(x) {
  return Number(x).toLocaleString(undefined, { maximumFractionDigits: 2 });
}
function cookie(name) {
  return (
    document.cookie
      .split("; ")
      .find((x) => x.startsWith(name + "="))
      ?.split("=")[1] || ""
  );
}
async function api(action, data) {
  const options = {
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: "application/json" },
  };
  if (data !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.headers["X-CSRFToken"] = cookie("csrftoken");
    options.body = JSON.stringify(data);
  }
  let r;
  try {
    r = await fetch("/api/" + action + "/", options);
  } catch (e) {
    const error = new Error(
      "Server unreachable. Save a help request on this device or retry when connected.",
    );
    error.network = true;
    throw error;
  }
  let result;
  try {
    result = await r.json();
  } catch (e) {
    throw new Error(
      "The server returned an unexpected response. Reload to refresh your session, then retry.",
    );
  }
  if (!r.ok) {
    const error = new Error(result.error || "Action failed.");
    error.fields = result.fields;
    error.status = r.status;
    throw error;
  }
  return result;
}
let dbPromise;
function db() {
  if (!window.indexedDB)
    return Promise.reject(
      new Error("Device storage is unavailable in this browser."),
    );
  if (!dbPromise)
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open("resilio-offline-v1", 1);
      req.onupgradeneeded = () => {
        req.result.createObjectStore("queue", { keyPath: "client_id" });
        req.result.createObjectStore("meta");
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(new Error("Could not open device storage."));
    });
  return dbPromise;
}
async function storage(store, method, ...args) {
  const d = await db();
  return new Promise((resolve, reject) => {
    const tx = d.transaction(
      store,
      method === "get" || method === "getAll" ? "readonly" : "readwrite",
    );
    const r = tx.objectStore(store)[method](...args);
    tx.oncomplete = () => resolve(r.result);
    tx.onerror = () =>
      reject(
        new Error("Device storage failed. Check browser storage permissions."),
      );
    tx.onabort = tx.onerror;
  });
}
function clientId() {
  // UUID format without relying unconditionally on crypto.randomUUID (HTTPS-only).
  const bytes = new Uint8Array(16);
  if (window.crypto?.getRandomValues) crypto.getRandomValues(bytes);
  else for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const h = [...bytes].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
async function refresh(render = true) {
  try {
    const reconnect = !!state.public && !state.online;
    const pub = await api("public");
    state.public = pub;
    state.online = true;
    if (reconnect)
      message("Server connection restored. Public information refreshed.");
    try {
      await storage("meta", "put", pub, "public");
    } catch (e) {}
    $("#connection").textContent = "● Server reachable";
  } catch (error) {
    state.online = false;
    $("#connection").textContent = "○ Server unreachable";
    if (!state.public) {
      try {
        state.public = await storage("meta", "get", "public");
      } catch (e) {}
    }
    message(
      "Cached public information · Last successful sync: " +
        (state.public
          ? new Date(state.public.synced_at).toLocaleString()
          : "never") +
        ". Availability may have changed.",
      true,
    );
  }
  try {
    const privateData = await api("me");
    state.private = privateData;
    state.lastAccount = privateData.user.id;
    try {
      await storage("meta", "put", state.lastAccount, "lastAccount");
    } catch (e) {}
  } catch (e) {
    state.private = null;
    if (e.status === 401) {
      state.lastAccount = null;
      try {
        await storage("meta", "delete", "lastAccount");
      } catch (err) {}
    }
  }
  updateAccount();
  if (render) renderScreen();
}
function updateAccount() {
  const u = state.private?.user;
  $("#account").textContent = u
    ? `${u.username} / ${u.admin ? "Administrator" : u.role === "coordinator" ? "NGO Officer" : u.role === "volunteer" ? "Volunteer" : "Community"}`
    : !state.online && state.lastAccount
      ? `Offline device / account #${state.lastAccount}`
      : "Public access";
  $("#account").hidden = !u && !state.lastAccount;
  $("#logout").hidden = !u;
  const allowed = {
    activity: !!u,
    volunteer: !!u && (u.role === "volunteer" || u.admin),
    coordination: !!u && (u.role === "coordinator" || u.admin),
    notifications: !!u,
    administration: !!u?.admin,
    profile: !!u,
  };
  Object.entries(allowed).forEach(([key, show]) => {
    const link = document.querySelector(`#navigation a[href="#${key}"]`);
    if (link) link.hidden = !show;
  });
  $("#loginLink").hidden = !!u;
  $("#registerLink").hidden = !!u;
  const count = state.private?.notifications.filter((n) => !n.read).length || 0;
  $("#notificationsLink").textContent =
    "Notifications" + (count ? ` (${count})` : "");
}
function requireLogin() {
  if (state.private) return true;
  const root = $("#screen");
  append(
    root,
    el("h1", "Sign in to coordinate"),
    el(
      "p",
      "Your activity, assignments and notifications are private. Sign in when the server is reachable.",
    ),
  );
  const a = el("a", "Sign in", "button btn-primary");
  a.href = "/accounts/login/";
  root.append(a);
  return false;
}
function title(name, sub) {
  const root = $("#screen");
  root.append(el("span", "RESILIO / COMMUNITY", "section-tag"), el("h1", name));
  if (sub) root.append(el("p", sub, "muted"));
  return root;
}
function renderScreen() {
  if (typeof stopNetwork === "function") stopNetwork();
  state.screen = location.hash.slice(1) || "overview";
  $("#screen").replaceChildren();
  $$("#navigation a").forEach((a) => {
    const active = a.hash === "#" + state.screen;
    a.classList.toggle("active", active);
    if (active) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  const screens = {
    overview,
    emergencies: emergencyDesk,
    announcements: announcementDesk,
    network,
    coordination: officerDesk,
    activity,
    volunteer: volunteerDesk,
    shelters,
    notifications,
    sync: syncCenter,
    administration,
    profile,
  };
  Promise.resolve((screens[state.screen] || overview)()).catch((e) =>
    message(e.message, true),
  );
}
function empty(root, text = "No records yet.") {
  root.append(el("p", text, "empty"));
}
function recordOwned(r) {
  return !!state.private?.[
    r.kind === "offer" ? "owned_offers" : "owned_requests"
  ]?.includes(r.id);
}
function card(r) {
  const c = el("article", null, "resource-card " + r.kind);
  const head = el("div", null, "card-top");
  append(head, el("h3", r.name), el("span", r.kind.toUpperCase(), "badge"));
  append(
    c,
    head,
    el(
      "p",
      r.kind === "offer"
        ? `${num(r.available)} ${r.unit}`
        : `${num(r.remaining)} ${r.unit}`,
      "quantity",
    ),
  );
  c.append(
    el(
      "p",
      r.kind === "offer"
        ? `Available from ${num(r.quantity)} ${r.unit} offered`
        : `Still needed · ${num(r.unallocated)} ${r.unit} unallocated`,
      "muted",
    ),
  );
  c.append(
    el(
      "div",
      `${r.area}${r.district_name ? ", " + r.district_name : ""} · ${r.status}${r.urgency ? " / " + r.urgency : ""} · updated ${ago(r.updated_at)}`,
      "meta",
    ),
  );
  if (r.demo) c.append(el("span", "FICTIONAL DEMONSTRATION DATA", "badge"));
  if (r.description) c.append(el("p", r.description, "card-description"));
  if (r.expires_at)
    c.append(
      el("p", "Expires " + new Date(r.expires_at).toLocaleString(), "meta"),
    );
  const actions = el("div", null, "card-actions");
  if (r.kind === "request" && r.status === "open")
    actions.append(button("View compatible offers", () => matches(r), "good"));
  if ((recordOwned(r) || state.private?.user.admin) && r.status === "open") {
    actions.append(
      button("Edit", () => openEditor(r.kind, r)),
      button(
        "Cancel record",
        () =>
          actionForm(
            "Cancel record",
            [
              {
                name: "confirmation",
                label: "Type CANCEL to confirm",
                required: true,
              },
            ],
            async (d) => {
              if (d.confirmation !== "CANCEL")
                throw Error("Type CANCEL to confirm.");
              await api("cancel", { kind: r.kind, id: r.id });
            },
          ),
        "danger",
      ),
    );
  }
  if (state.private)
    actions.append(
      button("Report", () =>
        actionForm(
          "Report this post",
          [{ name: "reason", label: "Reason", required: true, maxlength: 500 }],
          (d) => api("report", { kind: r.kind, id: r.id, ...d }),
        ),
      ),
    );
  recordFieldTools(c, r, actions);
  append(c, actions);
  return c;
}
function filtered() {
  const f = state.filters;
  return [
    ...(state.public?.requests || []),
    ...(state.public?.offers || []),
  ].filter(
    (r) =>
      (!f.search ||
        (r.name + " " + r.description)
          .toLowerCase()
          .includes(f.search.toLowerCase())) &&
      (!f.category || r.category === f.category) &&
      (!f.division || r.division === f.division) &&
      (!f.district || r.district === f.district) &&
      (!f.upazila || r.upazila === f.upazila) &&
      (!f.area ||
        r.area.includes(f.area.toLowerCase().trim().replace(/\s+/g, " "))) &&
      (!f.urgency || r.urgency === f.urgency) &&
      (!f.availability ||
        (f.availability === "available"
          ? r.kind === "offer" && Number(r.available) > 0
          : f.availability === "needed"
            ? r.kind === "request" &&
              r.status === "open" &&
              Number(r.unallocated) > 0
            : r.status === f.availability)),
  );
}
function overview() {
  const root = $("#screen"),
    pub = state.public;
  const hero = el("section", null, "hero");
  append(
    hero,
    el("span", "COMMUNITY POWERED · RESOURCE COORDINATION", "section-tag"),
    el("h1", "RESILIO", "hero-title"),
    el("h2", "Help reaches further. Together."),
    el(
      "p",
      "Request essential supplies. Share what you have. Coordinate accountable deliveries with your community.",
    ),
  );
  const actions = el("div", null, "hero-actions");
  append(
    actions,
    button("+ Request assistance", () => openEditor("request"), "btn-primary"),
    button("Offer supplies", () => openEditor("offer")),
  );
  append(hero, actions);
  const heroCopy = el("div", null, "hero-copy");
  while (hero.firstChild) heroCopy.append(hero.firstChild);
  hero.append(heroCopy);
  const welcome = el("div", null, "welcome-portals");
  if (!state.private) {
    welcome.append(
      el("span", "FIND YOUR WORKSPACE", "section-tag"),
      el("h3", "Join the coordinated response"),
    );
    for (const [key, label, desc] of [
      ["admin", "Administrator", "Manage approvals and oversee the response"],
      [
        "coordinator",
        "NGO / Relief Officer",
        "Coordinate resources and volunteer teams",
      ],
      [
        "volunteer",
        "Volunteer",
        "Take assignments and deliver essential supplies",
      ],
    ]) {
      const a = el(
        "a",
        null,
        "portal-card " +
          (key === "admin"
            ? "admin-portal"
            : key === "volunteer"
              ? "volunteer-portal"
              : "officer-portal"),
      );
      a.href = "/accounts/login/?portal=" + key;
      append(
        a,
        append(el("div"), el("h3", label), el("p", desc)),
        el("span", "→"),
      );
      welcome.append(a);
    }
    const community = el(
      "a",
      "Community / Donor: request help or offer supplies →",
      "strong-link",
    );
    community.href = "/register/?role=community";
    welcome.append(community);
  } else {
    const u = state.private.user;
    append(
      welcome,
      el("span", "YOUR RESPONSE WORKSPACE", "section-tag"),
      el(
        "h3",
        u.admin
          ? "Administrator"
          : u.role === "coordinator"
            ? "NGO / Relief Officer"
            : u.role === "volunteer"
              ? "Volunteer"
              : "Community / Donor",
      ),
      el("p", u.organization || "Every verified delivery makes a difference."),
    );
    const desk = el("a", "Open my workspace →", "button account-signin");
    desk.href = u.admin
      ? "#administration"
      : u.role === "coordinator"
        ? "#coordination"
        : u.role === "volunteer"
          ? "#volunteer"
          : "#activity";
    welcome.append(desk);
    if (u.role === "coordinator" && !u.approved)
      welcome.append(
        el(
          "p",
          "Officer approval pending. You can post your own requests and offers while an administrator reviews your application.",
          "notice role-notice",
        ),
      );
  }
  hero.append(welcome);
  root.append(hero);
  if (!pub) {
    empty(
      root,
      "No server data or cached public snapshot is available. Connect once to load the item catalog.",
    );
    return;
  }
  const stats = el("div", null, "stats");
  [
    ["Available offers", pub.stats.offers],
    ["Open requests", pub.stats.requests],
    ["Urgent needs", pub.stats.urgent],
    ["Confirmed deliveries", pub.stats.deliveries],
  ].forEach(([label, n]) =>
    append(
      stats,
      append(
        el("div", null, "stat-card"),
        el("span", n, "stat-num"),
        el("span", label, "stat-label"),
      ),
    ),
  );
  root.append(stats);
  if (typeof mountNetwork === "function") mountNetwork(root, true);
  const heading = el("div", null, "section-header");
  append(
    heading,
    el("h2", "Resource board"),
    el("span", "Public records · refresh every 30 seconds", "meta"),
  );
  root.append(heading);
  const tabs = el("div", null, "category-tabs");
  ["", "water", "food", "medical", "shelter"].forEach((cat) => {
    const b = button(cat || "All categories", () => {
      state.filters.category = cat;
      overviewRerender();
    });
    b.setAttribute("aria-pressed", String(state.filters.category === cat));
    tabs.append(b);
  });
  root.append(tabs);
  const filters = el("div", null, "filter-bar");
  const controls = [
    ["search", "Search item or description"],
    ["area", "Area"],
    ["urgency", "Urgency", ["", "normal", "urgent", "critical"]],
    [
      "availability",
      "Availability",
      ["", "available", "needed", "open", "fulfilled", "cancelled"],
    ],
  ];
  controls.forEach(([key, label, options]) => {
    const l = el("label", label),
      n = el(options ? "select" : "input");
    if (options)
      options.forEach((o) => {
        const opt = el("option", o || "All");
        opt.value = o;
        n.append(opt);
      });
    n.value = state.filters[key];
    n.addEventListener(options ? "change" : "input", () => {
      state.filters[key] = n.value;
      renderBoard();
    });
    append(l, n);
    filters.append(l);
  });
  const geoFilters = el("div", null, "form-grid");
  geoFilters.style.gridColumn = "1 / -1";
  geoFields(geoFilters, state.filters, false, (division, district, upazila) => {
    state.filters.upazila = upazila;
    state.filters.division = division;
    state.filters.district = district;
    renderBoard();
  });
  filters.append(geoFilters);
  root.append(filters);
  const board = el("div", null, "resource-grid");
  board.id = "board";
  root.append(board);
  renderBoard();
  const h = el("div", null, "section-header");
  h.append(el("h2", "Supply vs demand"));
  root.append(
    h,
    el(
      "p",
      "Per canonical item, unit and normalized area. Needed quantities include active reservations until receipt is confirmed.",
      "muted",
    ),
  );
  const charts = el("div", null, "charts-grid");
  pub.analytics.forEach((row) => {
    const c = el("article", null, "chart-card");
    append(
      c,
      el("h3", row.name),
      el("p", `${row.area} · ${row.unit}`, "meta"),
      el(
        "p",
        `${num(row.available)} ${row.unit} available / ${num(row.needed)} ${row.unit} needed`,
      ),
    );
    const max = Math.max(row.available, row.needed, 1);
    [
      ["Available supply", row.available, ""],
      ["Unconfirmed need", row.needed, "need"],
    ].forEach(([label, value, cls]) => {
      const track = el("div", null, "bar-track");
      track.setAttribute("role", "img");
      track.setAttribute("aria-label", `${label}: ${num(value)} ${row.unit}`);
      const fill = el("div", null, "bar-fill " + cls);
      fill.style.width = (value / max) * 100 + "%";
      append(track, fill);
      append(c, track);
    });
    c.append(
      el("p", `Unallocated need: ${num(row.unallocated)} ${row.unit}`, "meta"),
    );
    if (row.available < row.unallocated)
      c.append(el("p", "Supply shortage against unallocated need", "warning"));
    charts.append(c);
  });
  if (!pub.analytics.length) empty(charts, "No open supply or demand records.");
  root.append(charts);
}
function overviewRerender() {
  if (state.screen === "overview") {
    $("#screen").replaceChildren();
    overview();
  }
}
function renderBoard() {
  const board = $("#board");
  if (!board) return;
  board.replaceChildren();
  filtered().forEach((r) => board.append(card(r)));
  if (!board.children.length)
    empty(board, "No records match these combined filters.");
}
function activity() {
  const root = title(
    "My Activity",
    "Your requests, donor inventory and involved deliveries.",
  );
  if (!requireLogin()) return;
  const actions = el("div", null, "actions");
  append(
    actions,
    button("Request assistance", () => openEditor("request"), "btn-primary"),
    button("Offer supplies", () => openEditor("offer")),
  );
  root.append(actions);
  ["request", "offer"].forEach((kind) => {
    root.append(
      el("h2", kind === "request" ? "My requests" : "Donor inventory"),
    );
    const grid = el("div", null, "resource-grid");
    (state.public?.[kind === "request" ? "requests" : "offers"] || [])
      .filter(recordOwned)
      .forEach((r) => grid.append(card(r)));
    if (!grid.children.length) empty(grid);
    root.append(grid);
  });
  root.append(el("h2", "Involved deliveries"));
  assignments(root, state.private.assignments);
}
function assignments(root, list) {
  if (!list.length) {
    empty(
      root,
      "No assignments yet. Volunteers can reserve compatible offers from an open request.",
    );
    return;
  }
  const grid = el("div", null, "resource-grid");
  list.forEach((a) => {
    const c = el("article", null, "panel");
    append(
      c,
      el("h3", `Assignment #${a.id} · ${a.name}`),
      el(
        "p",
        `${num(a.quantity)} ${a.unit} reserved · ${a.status.replaceAll("_", " ")}`,
      ),
      el(
        "p",
        `Offer #${a.offer} → Request #${a.request} · Volunteer ${a.volunteer}`,
        "meta",
      ),
    );
    if (["awaiting_confirmation", "delivered"].includes(a.status))
      c.append(
        el(
          "p",
          `${num(a.delivered_quantity)} ${a.unit} ${a.status === "delivered" ? "confirmed" : "submitted for confirmation"}`,
        ),
      );
    const controls = el("div", null, "actions"),
      u = state.private.user;
    const transition = async (t, quantity) => {
      await api("transition", { id: a.id, transition: t, quantity });
      message("Server confirmed assignment update.");
      await refresh();
    };
    if (u.admin || u.can_coordinate || u.id === a.volunteer_id) {
      if (a.status === "assigned")
        controls.append(
          button("Start delivery", () => transition("start"), "btn-primary"),
        );
      if (a.status === "in_progress")
        controls.append(
          button(
            "Submit delivered quantity",
            () =>
              actionForm(
                "Submit delivery",
                [
                  {
                    name: "quantity",
                    label: `Actual delivered (${a.unit}), maximum ${a.quantity}`,
                    type: "number",
                    min: ".01",
                    max: a.quantity,
                    step: ".01",
                    required: true,
                  },
                ],
                (d) =>
                  api("transition", {
                    id: a.id,
                    transition: "submit",
                    quantity: d.quantity,
                  }),
              ),
            "good",
          ),
        );
      if (["assigned", "in_progress"].includes(a.status))
        controls.append(
          button(
            "Cancel assignment",
            () =>
              actionForm(
                "Release reservation",
                [
                  {
                    name: "confirmation",
                    label: "Type CANCEL",
                    required: true,
                  },
                ],
                (d) => {
                  if (d.confirmation !== "CANCEL")
                    throw Error("Type CANCEL to confirm.");
                  return api("transition", { id: a.id, transition: "cancel" });
                },
              ),
            "danger",
          ),
        );
    }
    if (
      a.status === "awaiting_confirmation" &&
      (u.admin || u.id === a.requester_id)
    )
      controls.append(
        button(
          "Confirm receipt",
          () =>
            actionForm(
              "Confirm receipt",
              [
                {
                  name: "confirmation",
                  label: `Type RECEIVED to confirm ${a.delivered_quantity} ${a.unit}`,
                  required: true,
                },
              ],
              (d) => {
                if (d.confirmation !== "RECEIVED")
                  throw Error("Type RECEIVED to confirm.");
                return api("transition", { id: a.id, transition: "confirm" });
              },
            ),
          "btn-primary",
        ),
      );
    controls.append(button("Assignment messages", () => assignmentThread(a)));
    append(c, controls);
    grid.append(c);
  });
  root.append(grid);
}
function volunteerDesk() {
  const root = title(
    "Volunteer Desk",
    "Assigned → In progress → Awaiting confirmation → Delivered",
  );
  if (!requireLogin()) return;
  const u = state.private.user;
  if (u.role !== "volunteer" && !u.admin) {
    empty(
      root,
      "A volunteer account is required to reserve and coordinate deliveries. Your receipt confirmations are in My Activity.",
    );
    return;
  }
  root.append(
    el(
      "p",
      "Open a request on the overview and choose a compatible offer to reserve supply.",
      "muted",
    ),
  );
  assignments(
    root,
    state.private.assignments.filter((a) => u.admin || a.volunteer_id === u.id),
  );
}
async function matches(r) {
  if (!state.private) {
    message("Sign in to view recommendations and reserve supplies.", true);
    return;
  }
  const dialog = $("#actionDialog");
  $("#actionTitle").textContent = `Compatible offers · Request #${r.id}`;
  $("#actionError").textContent = "";
  const form = $("#actionForm");
  form.onsubmit = (e) => e.preventDefault();
  form.replaceChildren(el("p", "Loading recommendations…"));
  dialog.showModal();
  try {
    const response = await fetch(
      "/api/matches/?request=" + encodeURIComponent(r.id),
      { cache: "no-store", credentials: "same-origin" },
    );
    const data = await response.json();
    if (!response.ok)
      throw Error(data.error || "Could not load recommendations.");
    form.replaceChildren();
    if (!data.matches.length)
      empty(form, "No compatible offers currently have available stock.");
    data.matches.forEach((o) => {
      const c = el("article", null, "panel");
      append(
        c,
        el("h3", `${o.name} · Offer #${o.id}`),
        el("p", `${num(o.available)} ${o.unit} available · ${o.area}`),
        el("p", o.reasons.join(" · "), "muted"),
      );
      if (
        state.private.user.role === "volunteer" ||
        state.private.user.admin ||
        state.private.user.can_coordinate
      ) {
        const label = el(
            "label",
            `Reserve quantity (${o.unit}), maximum ${o.max_quantity}`,
          ),
          input = el("input");
        input.type = "number";
        input.min = ".01";
        input.step = ".01";
        input.max = o.max_quantity;
        input.value = o.max_quantity;
        label.append(input);
        let assignee = null;
        if (state.private.user.can_coordinate || state.private.user.admin) {
          const label = el("label", "Assign to volunteer"),
            select = el("select");
          const mine = el("option", "Coordinate this delivery myself");
          mine.value = "";
          select.append(mine);
          (state.private.volunteers || []).forEach((v) => {
            const opt = el("option", v.username);
            opt.value = v.id;
            select.append(opt);
          });
          label.append(select);
          c.append(label);
          assignee = select;
        }
        append(
          c,
          label,
          button(
            "Reserve supply",
            async () => {
              try {
                const result = await api("reserve", {
                  offer: o.id,
                  request: r.id,
                  quantity: input.value,
                  volunteer: assignee?.value || null,
                });
                dialog.close();
                message(`Server confirmed assignment #${result.id}.`);
                await refresh();
              } catch (e) {
                $("#actionError").textContent = e.message;
              }
            },
            "btn-primary",
          ),
        );
      } else
        c.append(
          el(
            "p",
            "Volunteer coordination is required to reserve supply.",
            "muted",
          ),
        );
      form.append(c);
    });
  } catch (e) {
    $("#actionError").textContent = e.message;
    form.replaceChildren();
  }
}
async function actionForm(
  name,
  fields,
  save,
  successText = "Server confirmed the save.",
) {
  const dialog = $("#actionDialog");
  if (dialog.open) dialog.close();
  $("#actionTitle").textContent = name;
  $("#actionError").textContent = "";
  const form = $("#actionForm");
  form.replaceChildren();
  fields.forEach((field) => {
    const label = el("label", field.label),
      input = el(
        field.options ? "select" : field.multiline ? "textarea" : "input",
      );
    input.name = field.name;
    if (field.options)
      field.options.forEach((o) => {
        const option = el("option", Array.isArray(o) ? o[1] : o);
        option.value = Array.isArray(o) ? o[0] : o;
        input.append(option);
      });
    Object.entries(field).forEach(([k, v]) => {
      if (!["label", "options", "name", "multiline"].includes(k))
        input.setAttribute(k, v);
    });
    label.append(input);
    form.append(label);
  });
  const submit = el("button", "Save on server", "btn-primary");
  submit.type = "submit";
  form.append(submit);
  form.onsubmit = async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      await save(Object.fromEntries(new FormData(form)));
      dialog.close();
      message(successText);
      await refresh();
    } catch (e) {
      $("#actionError").textContent = e.message;
    } finally {
      submit.disabled = false;
    }
  };
  dialog.showModal();
}
function shelters() {
  const root = title(
    "Shelters",
    "Facility capacity is separate from blankets, tents and other resource offers.",
  );
  if (state.private?.user.admin || state.private?.user.can_coordinate)
    root.append(
      button(
        "Add shelter",
        () =>
          actionForm(
            "Add shelter",
            [
              {
                name: "name",
                label: "Facility name",
                required: true,
                maxlength: 120,
              },
              { name: "area", label: "Area", required: true, maxlength: 100 },
              {
                name: "district",
                label: "District",
                required: true,
                options: [
                  ["", "Select district"],
                  ...geoCatalog().districts.map((d) => [d.code, d.name]),
                ],
              },
              {
                name: "total",
                label: "Total capacity",
                type: "number",
                min: 1,
                step: 1,
                required: true,
              },
              {
                name: "description",
                label: "Description",
                multiline: true,
                maxlength: 2000,
              },
            ],
            (d) => api("shelter", d),
          ),
        "btn-primary",
      ),
    );
  const filters = el("div", null, "form-grid");
  const listRoot = el("div");
  root.append(filters, listRoot);
  const selection = {};
  const controls = geoFields(
    filters,
    {},
    false,
    (division, district, upazila) => {
      selection.division = division;
      selection.district = district;
      selection.upazila = upazila;
      drawShelters();
    },
  );
  root.append(
    el(
      "p",
      "Distances use your last device reading and exact saved facility pins. They are straight-line distances, not road routes.",
      "muted",
    ),
  );
  let byDistance = false;
  root.append(
    button("Sort by distance", () => {
      if (!geoState.position)
        throw Error("Use my location on the Live map first.");
      byDistance = !byDistance;
      drawShelters();
    }),
  );
  function drawShelters() {
    listRoot.replaceChildren();
    const grid = el("div", null, "shelter-grid");
    const rows = (state.public?.shelters || []).filter(
      (s) =>
        (!selection.division || s.division === selection.division) &&
        (!selection.district || s.district === selection.district) &&
        (!selection.upazila || s.upazila === selection.upazila),
    );
    if (byDistance)
      rows.sort(
        (a, b) =>
          (pointDistance(a.pin) ?? Infinity) -
          (pointDistance(b.pin) ?? Infinity),
      );
    rows.forEach((s) => {
      const c = el("article", null, "panel");
      append(
        c,
        el("h2", s.name),
        el("p", s.area, "meta"),
        el("p", `${s.available} spaces available`, "quantity"),
        el(
          "p",
          `${s.occupied} occupied + ${s.reserved} reserved / ${s.total} total`,
        ),
        el("p", s.description),
      );
      if (s.pin) {
        c.append(button("View exact pin", () => showSavedPin(s.pin, s.name)));
        const distance = pointDistance(s.pin);
        if (distance !== null)
          c.append(
            el("p", distance.toFixed(1) + " km straight-line distance", "meta"),
          );
      } else c.append(el("p", "Distance unavailable — no exact pin", "meta"));
      if (state.private?.user.can_coordinate)
        c.append(button("Set shelter location", () => shelterLocationForm(s)));
      if (s.demo) c.append(el("p", "FICTIONAL DEMONSTRATION DATA", "badge"));
      if (state.private?.user.admin || state.private?.user.can_coordinate)
        c.append(
          button("Update capacity use", () =>
            actionForm(
              s.name,
              [
                {
                  name: "operation",
                  label: "Operation",
                  options: [
                    ["check_in", "Check in unreserved guests"],
                    ["check_out", "Check out guests"],
                    ["reserve", "Reserve spaces"],
                    ["release", "Release reserved spaces"],
                    ["convert", "Check in reserved guests"],
                  ],
                },
                {
                  name: "quantity",
                  label: "Number of spaces",
                  type: "number",
                  min: 1,
                  step: 1,
                  required: true,
                },
              ],
              (d) => api("shelter", { id: s.id, ...d }),
            ),
          ),
        );
      grid.append(c);
    });
    if (!grid.children.length) empty(grid, "No facilities recorded.");
    listRoot.append(grid);
  }
  drawShelters();
}
function notifications() {
  const root = title(
    "Notifications",
    "Updates generated from saved assignments, receipt confirmations and reviews.",
  );
  if (!requireLogin()) return;
  const list = state.private.notifications;
  if (!list.length) empty(root, "No notifications yet.");
  list.forEach((n) => {
    const c = el(
      "article",
      null,
      "panel " + (!n.read ? "notification-unread" : ""),
    );
    append(c, el("p", n.text), el("p", ago(n.created_at), "meta"));
    if (!n.read)
      c.append(
        button("Mark read", async () => {
          await api("read", { id: n.id });
          await refresh();
        }),
      );
    root.append(c);
  });
}
function administration() {
  const root = title(
    "Administration",
    "Review reports, moderate records, maintain shelters and inspect operational history.",
  );
  if (!requireLogin()) return;
  if (!state.private.user.admin) {
    empty(root, "Administrator permission is required.");
    return;
  }
  root.append(el("h2", "NGO / Officer approvals"));
  (state.private.officers || []).forEach((o) => {
    const card = el("article", null, "panel approval-card");
    const info = append(
      el("div"),
      el("h3", o.user__username + " · " + o.organization),
      el(
        "p",
        `${o.area || "Area not set"} · ${o.approved ? "Approved officer" : "Awaiting approval"}`,
        "muted",
      ),
    );
    card.append(
      info,
      button(
        o.approved ? "Revoke officer access" : "Approve officer",
        () =>
          actionForm(
            "Officer access",
            [
              {
                name: "confirmation",
                label: `Type ${o.approved ? "REVOKE" : "APPROVE"} to confirm`,
                required: true,
              },
            ],
            async (d) => {
              if (d.confirmation !== (o.approved ? "REVOKE" : "APPROVE"))
                throw Error("Enter the confirmation word.");
              await api("approve", { id: o.id, approved: !o.approved });
            },
          ),
        o.approved ? "" : "btn-primary",
      ),
    );
    root.append(card);
  });
  if (!(state.private.officers || []).length)
    empty(root, "No officer applications yet.");
  const link = el("a", "Open Django administration", "button");
  link.href = "/admin/";
  root.append(
    link,
    el(
      "p",
      "Moderate records using their Edit and Cancel controls on the overview. Active allocations must be resolved first. Shelter operations have their own capacity controls.",
      "muted",
    ),
    el("h2", "Reports"),
  );
  (state.private.reports || []).forEach((r) => {
    const p = el("article", null, "panel");
    append(
      p,
      el(
        "h3",
        `Report #${r.id} · ${r.offer_id ? "Offer #" + r.offer_id : "Request #" + r.request_id}`,
      ),
      el("p", r.reason),
      el("p", r.decision || "Awaiting review", "muted"),
    );
    if (!r.reviewed_at)
      p.append(
        button("Record decision", () =>
          actionForm(
            "Review report",
            [
              {
                name: "decision",
                label:
                  "Decision and reasoning (does not automatically delete the post)",
                required: true,
                maxlength: 500,
              },
            ],
            (d) => api("review", { id: r.id, ...d }),
          ),
        ),
      );
    root.append(p);
  });
  if (!state.private.reports.length) empty(root, "No reports to review.");
  root.append(
    el("h2", "Operational information"),
    el(
      "p",
      `Confirmed deliveries: ${state.public?.stats.deliveries || 0} · Open requests: ${state.public?.stats.requests || 0}. Volunteer activity and stock changes are confirmed by the shared relief-center server.`,
    ),
    el("h2", "Audit history"),
  );
  const wrap = el("div", null, "table-wrap"),
    table = el("table"),
    head = el("tr");
  ["When", "Actor", "Action", "Target", "Detail"].forEach((t) =>
    head.append(el("th", t)),
  );
  table.append(head);
  state.private.audit.forEach((a) => {
    const row = el("tr");
    [
      new Date(a.created_at).toLocaleString(),
      a.actor__username || "system",
      a.action,
      a.target,
      a.detail,
    ].forEach((t) => row.append(el("td", t)));
    table.append(row);
  });
  append(wrap, table);
  root.append(wrap);
}
function profile() {
  const root = title("Profile");
  if (!requireLogin()) return;
  const u = state.private.user;
  root.append(
    el(
      "p",
      `Username: ${u.username} · Role: ${u.admin ? "Administrator" : u.role === "coordinator" ? "NGO / Relief Officer" : u.role === "volunteer" ? "Volunteer" : "Community / Donor"}`,
    ),
  );
  const form = el("form", null, "panel");
  [
    ["name", "Display name"],
    ["email", "Email"],
    ["area", "Area"],
  ].forEach(([name, label]) => {
    const l = el("label", label),
      input = el("input");
    input.name = name;
    input.value = u[name] || "";
    input.type = name === "email" ? "email" : "text";
    input.maxLength = name === "email" ? 254 : name === "name" ? 150 : 100;
    append(l, input);
    form.append(l);
  });
  const geo = el("div", null, "form-grid");
  geoFields(geo, u);
  form.append(geo);
  const submit = el("button", "Save profile", "btn-primary");
  form.append(submit);
  form.onsubmit = async (e) => {
    e.preventDefault();
    submit.disabled = true;
    try {
      await api("profile", Object.fromEntries(new FormData(form)));
      message("Profile saved on server.");
      await refresh();
    } catch (err) {
      message(err.message, true);
    } finally {
      submit.disabled = false;
    }
  };
  root.append(form);
}
let activeClientId;
function openEditor(kind, r = null, category = null) {
  if (!state.public) {
    message("Connect once to load the canonical item catalog.", true);
    return;
  }
  if (
    !state.private &&
    !(kind === "request" && !state.online && state.lastAccount)
  ) {
    message(
      "Sign in before creating a request or offer. For offline requests, sign in once on this device first.",
      true,
    );
    return;
  }
  if (!state.public.items?.length) {
    message(
      state.private?.user.admin
        ? "The item catalog is empty. Run manage.py initialize_catalog with your project Python, then refresh."
        : "Resource items have not been configured. Ask an administrator to initialize the item catalog, then refresh.",
      true,
    );
    return;
  }
  const form = $("#resourceForm");
  form.reset();
  $("#resourcePinFields").replaceChildren();
  pinFields(
    $("#resourcePinFields"),
    r ? storedPin(r) : null,
    kind === "request" ? "private" : "public",
  );
  geoFields(
    $("#resourceGeography"),
    r || {
      district: state.private?.user.district || geoState.detectedDistrict,
      division: state.private?.user.division,
      upazila: state.private?.user.upazila,
    },
    true,
  );
  form.elements.namedItem("id").value = r?.id || "";
  form.elements.namedItem("kind").value = kind;
  activeClientId = clientId();
  $("#editorError").textContent = "";
  $$("[data-error]").forEach((n) => (n.textContent = ""));
  $("#editorTitle").textContent =
    (r ? "Edit " : category ? "Urgent " : "New ") +
    (kind === "offer" ? "supply offer" : "help request");
  const select = form.elements.namedItem("item");
  select.replaceChildren();
  state.public.items.forEach((i) => {
    const o = el("option", `${i.name} (${i.unit})`);
    o.value = i.id;
    select.append(o);
  });
  if (r) {
    for (const name of ["item", "quantity", "area", "description", "urgency"])
      if (r[name] !== undefined && form.elements.namedItem(name))
        form.elements.namedItem(name).value = r[name];
    if (r.expires_at) {
      const date = new Date(r.expires_at);
      form.elements.namedItem("expires_at").value = new Date(
        date - date.getTimezoneOffset() * 60000,
      )
        .toISOString()
        .slice(0, 16);
    }
  } else {
    form.elements.namedItem("area").value = state.private?.user.area || "";
    if (category) {
      const i = state.public.items.find((i) => i.category === category);
      if (i) select.value = i.id;
      form.elements.namedItem("urgency").value = "urgent";
      form.elements.namedItem("quantity").value = "1";
    }
  }
  $("#urgencyLabel").hidden = kind === "offer";
  $("#expiryLabel").hidden = kind === "request";
  $("#saveLocal").hidden = kind === "offer" || !!r;
  select.onchange = () => {
    $("#unitHint").textContent =
      "Unit: " +
      (state.public.items.find((i) => i.id === Number(select.value))?.unit ||
        "");
  };
  select.onchange();
  $("#editor").showModal();
}
function formPayload() {
  const form = $("#resourceForm");
  if (!form.reportValidity()) return null;
  const d = Object.fromEntries(new FormData(form));
  if (d.expires_at) d.expires_at = new Date(d.expires_at).toISOString();
  if (d.kind === "request" && !d.id) {
    d.client_id = activeClientId;
    d.account_id = state.private?.user.id || state.lastAccount;
  }
  return d;
}
async function saveLocal(payload, stateName = "Pending sync", error = "") {
  if (!payload) return;
  if (payload.kind !== "request" || payload.id)
    throw Error("Only new help requests can be saved locally.");
  if (!payload.account_id)
    throw Error("Sign in on this device once before saving offline requests.");
  const old = await storage("queue", "get", payload.client_id);
  await storage("queue", "put", {
    ...payload,
    state: old?.state === "Synced" ? "Synced" : stateName,
    error,
    server_id: old?.server_id || null,
    created_at: old?.created_at || new Date().toISOString(),
  });
  $("#editor").close();
  message(
    "Request stored on this device. Server confirmation is pending; synchronize with the same identifier.",
  );
  if (state.screen === "sync") renderScreen();
}
$("#resourceForm").onsubmit = async (e) => {
  e.preventDefault();
  const d = formPayload();
  if (!d) return;
  const submit = e.submitter || $("#resourceForm button[type=submit]");
  submit.disabled = true;
  try {
    const result = await api("resource", d);
    $("#editor").close();
    message(`Saved on server as ${d.kind} #${result.id}.`);
    await refresh();
  } catch (error) {
    $("#editorError").textContent = error.message;
    Object.entries(error.fields || {}).forEach(([name, value]) => {
      const target = $(`[data-error="${name}"]`);
      if (target) target.textContent = value.join(" ");
    });
    if (error.network && d.kind === "request" && !d.id) {
      try {
        await saveLocal(
          d,
          "Pending sync",
          "Server unreachable during save. Retry with the same identifier.",
        );
      } catch (err) {
        $("#editorError").textContent = err.message;
      }
    }
  } finally {
    submit.disabled = false;
  }
};
$("#saveLocal").onclick = async () => {
  try {
    await saveLocal(formPayload());
  } catch (e) {
    $("#editorError").textContent = e.message;
  }
};
async function syncEntry(entry) {
  const me = await api("me");
  if (me.user.id !== Number(entry.account_id))
    throw Error("Sign in as the account that created this entry.");
  try {
    const response = await api("resource", entry);
    entry.state = "Synced";
    entry.server_id = response.id;
    entry.error = "";
    await storage("queue", "put", entry);
    message(`Synchronized as server request #${response.id}.`);
  } catch (e) {
    entry.state = "Failed";
    entry.error = e.message;
    await storage("queue", "put", entry);
    throw e;
  }
  await refresh();
}
async function syncCenter() {
  const root = title(
    "Sync Center",
    "Local help requests stay on this device. Removing a local entry does not cancel any request already saved on the server.",
  );
  await offlineReadiness(root);
  root.append(
    el(
      "p",
      "Only the creating account can synchronize its entries. A retry uses the same identifier and returns the same server request ID. Private API responses and passwords are never cached.",
      "muted",
    ),
  );
  const features = el(
    "p",
    `IndexedDB: ${window.indexedDB ? "available" : "unavailable"} · Service worker: ${"serviceWorker" in navigator && window.isSecureContext ? "supported in this context" : "requires supported browser and HTTPS or localhost"}`,
    "notice",
  );
  root.append(features);
  const entries = await storage("queue", "getAll");
  const current = state.private?.user.id || state.lastAccount;
  if (!current) {
    empty(root, "Sign in to see this account’s local entries.");
    return;
  }
  const mine = entries.filter((e) => Number(e.account_id) === Number(current));
  if (!mine.length) empty(root, "No local requests for this account.");
  mine.forEach((entry) => {
    const c = el("article", null, "panel");
    append(
      c,
      el(
        "h3",
        `${state.public?.items.find((i) => i.id === Number(entry.item))?.name || "Item #" + entry.item} · ${entry.state}`,
      ),
      el("p", `${entry.quantity} · ${entry.area}`),
      el("p", `Client ID: ${entry.client_id}`, "meta"),
    );
    if (entry.server_id)
      c.append(el("p", `Confirmed server request #${entry.server_id}`, "good"));
    if (entry.error) c.append(el("p", entry.error, "warning"));
    const controls = el("div", null, "actions");
    controls.append(
      button(
        entry.state === "Synced"
          ? "Verify same server ID"
          : "Retry synchronization",
        async () => {
          await syncEntry(entry);
        },
      ),
    );
    controls.append(
      button("Remove local entry", () =>
        actionForm(
          "Remove local copy",
          [
            {
              name: "confirmation",
              label: "Type REMOVE. This will not cancel a server request.",
              required: true,
            },
          ],
          async (d) => {
            if (d.confirmation !== "REMOVE")
              throw Error("Type REMOVE to confirm.");
            await storage("queue", "delete", entry.client_id);
          },
          "Local copy removed. Server records were not changed.",
        ),
      ),
    );
    append(c, controls);
    root.append(c);
  });
}
$("#crisisToggle").onclick = () => {
  const buttons = $("#crisisButtons");
  buttons.replaceChildren();
  [
    ["water", "Water / L"],
    ["food", "Food / packs"],
    ["medical", "Medical supplies"],
    ["shelter", "Shelter supplies"],
  ].forEach(([cat, label]) =>
    buttons.append(
      button(
        label,
        () => {
          $("#crisis").close();
          openEditor("request", null, cat);
        },
        "crisis-action",
      ),
    ),
  );
  $("#crisis").showModal();
};
$$("[data-close]").forEach(
  (b) => (b.onclick = () => document.getElementById(b.dataset.close).close()),
);
$("#logout").onclick = async () => {
  try {
    const r = await fetch("/accounts/logout/", {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken") },
      credentials: "same-origin",
    });
    if (!r.ok) throw Error("Sign out failed.");
    state.private = null;
    state.lastAccount = null;
    try {
      await storage("meta", "delete", "lastAccount");
    } catch (storageError) {}
    location.href = "/";
  } catch (e) {
    message(e.message, true);
  }
};
window.addEventListener("hashchange", renderScreen);
window.addEventListener("online", () => refresh());
window.addEventListener("offline", () => {
  state.online = false;
  $("#connection").textContent = "○ Server unreachable";
  message(
    "Network disconnected. New requests can be saved on this device.",
    true,
  );
});
(async () => {
  try {
    state.lastAccount = await storage("meta", "get", "lastAccount");
  } catch (e) {}
  await refresh();
  if ("serviceWorker" in navigator && window.isSecureContext)
    try {
      await navigator.serviceWorker.register("/sw.js");
    } catch (e) {
      message(
        "Offline assets could not be installed. Device request storage remains available if IndexedDB works.",
        true,
      );
    }
})();
setInterval(() => {
  if (
    !document.hidden &&
    !document.querySelector("dialog[open]") &&
    state.screen !== "profile"
  )
    refresh();
}, 30000);
// Keep Tab navigation inside the active modal, including at its two boundaries.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Tab") return;
  const dialog = document.querySelector("dialog[open]");
  if (!dialog) return;
  const controls = [
    ...dialog.querySelectorAll(
      'button,a[href],input:not([type=hidden]),select,textarea,[tabindex]:not([tabindex="-1"])',
    ),
  ].filter((n) => !n.disabled && n.getClientRects().length);
  if (!controls.length) {
    event.preventDefault();
    dialog.focus();
    return;
  }
  const first = controls[0],
    last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});

function officerDesk() {
  const root = title(
    "NGO / Relief Officer Desk",
    "Coordinate compatible supplies, volunteer assignments and shelter capacity.",
  );
  if (!requireLogin()) return;
  const u = state.private.user;
  if (!u.admin && !u.can_coordinate) {
    root.append(
      el(
        "p",
        u.role === "coordinator"
          ? "Your officer application is awaiting administrator approval. Community posting remains available from My Activity."
          : "Approved NGO / relief officer access is required.",
        "notice role-notice",
      ),
    );
    return;
  }
  const summary = el("div", null, "panel officer-summary");
  append(
    summary,
    el("h2", u.organization || "Relief coordination"),
    el(
      "p",
      `${state.private.assignments.filter((a) => !["delivered", "cancelled"].includes(a.status)).length} active assignments across the relief center.`,
    ),
  );
  root.append(summary);
  const actions = el("div", null, "actions");
  const resources = el(
    "a",
    "Allocate from resource board",
    "button account-signin",
  );
  resources.href = "#overview";
  const capacity = el("a", "Manage shelter spaces", "button");
  capacity.href = "#shelters";
  append(actions, resources, capacity);
  root.append(actions, el("h2", "Volunteer assignments"));
  assignments(root, state.private.assignments);
}
