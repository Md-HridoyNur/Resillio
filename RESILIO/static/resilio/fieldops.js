/* Field tools: saved pins, emergency cases, bulletins, messages and offline readiness. */
function userText(tag, text, cls) {
  const n = el(tag, text, cls);
  n.dataset.userContent = "true";
  n.textContent = text || "";
  return n;
}
function placeName(r) {
  const u = (geoCatalog().upazilas || LOCAL_AREAS.upazilas).find(
    (x) => x.code === r.upazila,
  );
  return [u?.name, r.district_name || districtInfo(r.district)?.name, r.area]
    .filter(Boolean)
    .join(" · ");
}
function pointDistance(pin) {
  const p = geoState.position;
  if (!p || !pin) return null;
  const rad = (x) => (x * Math.PI) / 180,
    a = rad(Number(pin.latitude) - p.latitude),
    b = rad(Number(pin.longitude) - p.longitude);
  const h =
    Math.sin(a / 2) ** 2 +
    Math.cos(rad(p.latitude)) *
      Math.cos(rad(Number(pin.latitude))) *
      Math.sin(b / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
}
function storedPin(r) {
  return r.kind === "request"
    ? state.private?.request_pins?.[String(r.id)] || null
    : r.pin;
}
function pinFields(parent, pin = null, scope = "public") {
  const section = el("fieldset", null, "pin-fields");
  section.append(el("legend", "Optional exact location"));
  section.append(
    el(
      "p",
      scope === "private"
        ? "This pin is private to you, authorized officers and the volunteer assigned to this case."
        : "This saved pickup or shelter pin will be visible on the public map.",
      "muted",
    ),
  );
  const grid = el("div", null, "form-grid");
  const inputs = {};
  for (const [name, label, min, max] of [
    ["latitude", "Latitude", -90, 90],
    ["longitude", "Longitude", -180, 180],
  ]) {
    const l = el("label", label),
      input = el("input");
    input.name = name;
    input.type = "number";
    input.step = "0.000001";
    input.min = min;
    input.max = max;
    input.value = pin?.[name] || "";
    inputs[name] = input;
    l.append(input);
    grid.append(l);
  }
  section.append(grid);
  const label = el("label", "Place / landmark"),
    input = el("input");
  input.name = "pin_label";
  input.maxLength = 160;
  input.value = pin?.label || "";
  label.append(input);
  section.append(label);
  const consentLabel = el("label", null, "check-label"),
    consent = el("input");
  consent.type = "checkbox";
  consent.name = "pin_consent";
  consent.value = "yes";
  consent.checked = !!pin;
  append(
    consentLabel,
    consent,
    el(
      "span",
      scope === "private"
        ? "I agree to share this pin with authorized coordination users."
        : "I agree to publish this facility / pickup pin.",
    ),
  );
  section.append(consentLabel);
  const set = (lat, lon) => {
    inputs.latitude.value = Number(lat).toFixed(6);
    inputs.longitude.value = Number(lon).toFixed(6);
  };
  const actions = el("div", null, "actions");
  actions.append(
    button("Choose on map", () =>
      pickPoint(pin, (point) => set(point.lat, point.lng)),
    ),
  );
  actions.append(
    button("Use device location", () => {
      if (!window.isSecureContext || !navigator.geolocation)
        throw Error(
          "Location requires HTTPS or localhost. You can choose a point on the map.",
        );
      navigator.geolocation.getCurrentPosition(
        (p) => set(p.coords.latitude, p.coords.longitude),
        () =>
          message(
            "Location unavailable. Choose a map point or enter coordinates manually.",
            true,
          ),
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 15000 },
      );
    }),
  );
  actions.append(
    button("Clear pin", () => {
      inputs.latitude.value = inputs.longitude.value = "";
      input.value = "";
      consent.checked = false;
    }),
  );
  section.append(actions);
  parent.append(section);
  return section;
}
async function pickPoint(initial, save) {
  let dialog = document.querySelector("#pinDialog");
  if (dialog) dialog.remove();
  dialog = el("dialog");
  dialog.id = "pinDialog";
  dialog.setAttribute("aria-labelledby", "pinTitle");
  const h = el("h2", "Choose a location");
  h.id = "pinTitle";
  const mapNode = el("div", null, "pin-picker-map");
  const info = el(
    "p",
    "Click the map to set a pin. Zoom in before confirming.",
    "notice",
  );
  const actions = el("div", null, "actions");
  const cancel = button("Cancel", () => dialog.close());
  const confirm = button(
    "Use selected point",
    () => {
      if (!point) throw Error("Click a point on the map first.");
      save(point);
      dialog.close();
    },
    "btn-primary",
  );
  confirm.disabled = true;
  append(actions, cancel, confirm);
  append(dialog, h, info, mapNode, actions);
  document.body.append(dialog);
  dialog.showModal();
  let map = null,
    point = null,
    marker = null;
  dialog.addEventListener(
    "close",
    () => {
      if (map) {
        map.stop();
        map.remove();
      }
      dialog.remove();
    },
    { once: true },
  );
  try {
    const data = await loadBangladesh();
    if (!dialog.open) return;
    map = L.map(mapNode, {
      zoomAnimation: false,
      fadeAnimation: false,
      markerZoomAnimation: false,
    });
    const layer = L.geoJSON(data.districts, {
      style: {
        color: "#576a80",
        weight: 1,
        fillColor: "#d5e6e0",
        fillOpacity: 0.6,
      },
    }).addTo(map);
    map.fitBounds(layer.getBounds());
    const set = (latlng) => {
      point = latlng;
      if (marker) marker.remove();
      marker = L.circleMarker(point, {
        radius: 8,
        color: "#fff",
        weight: 3,
        fillColor: "#bd251b",
        fillOpacity: 1,
      }).addTo(map);
      info.textContent = `${point.lat.toFixed(6)}, ${point.lng.toFixed(6)}`;
      confirm.disabled = false;
    };
    map.on("click", (e) => set(e.latlng));
    if (initial) {
      set(L.latLng(Number(initial.latitude), Number(initial.longitude)));
      map.setView(point, 13);
    }
    const street = button("Street background (online)", () => {
      if (!navigator.onLine)
        throw Error("Internet is needed for street tiles.");
      if (!map.hasLayer(tiles)) tiles.addTo(map).bringToBack();
      else map.removeLayer(tiles);
    });
    const tiles = L.tileLayer(
      "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
    );
    actions.prepend(street);
    map.invalidateSize();
  } catch (e) {
    info.textContent = e.message;
  }
}
function showSavedPin(pin, name) {
  geoState.focusPin = { ...pin, name, private: true };
  geoState.view = {
    center: [Number(pin.latitude), Number(pin.longitude)],
    zoom: 15,
  };
  location.hash = "#network";
  if (state.screen === "network") renderScreen();
  message(
    name +
      " · saved creator-provided location. Enable the street background for roads.",
  );
}
function recordFieldTools(c, r, actions) {
  if (r.status !== "open") return;
  const fresh =
    !!r.confirmed_at &&
    Date.now() - new Date(r.confirmed_at).getTime() < 86400000;
  c.append(
    el(
      "p",
      fresh
        ? "Recently confirmed (within 24 hours)"
        : "Needs reconfirmation — availability may have changed",
      fresh ? "meta good" : "meta warning",
    ),
  );
  if (r.confirmed_at)
    c.append(
      el(
        "p",
        "Last confirmed: " + new Date(r.confirmed_at).toLocaleString(),
        "meta",
      ),
    );
  const pin = storedPin(r);
  if (pin)
    actions.append(button("View exact pin", () => showSavedPin(pin, r.name)));
  if ((recordOwned(r) || state.private?.user.admin) && r.status === "open")
    actions.append(
      button("Still needed / available", async () => {
        await api("reconfirm", { kind: r.kind, id: r.id });
        await refresh();
        message("Availability reconfirmed.");
      }),
    );
}
function emergencyDesk() {
  const root = title(
    "Emergency assistance",
    "Received → Acknowledged → Team assigned → Resolved",
  );
  root.append(
    el(
      "p",
      "Sends a case to RESILIO coordinators. This does not automatically dispatch government emergency services. An acknowledgement is required before assuming your case was reviewed.",
      "notice warning",
    ),
  );
  if (!requireLogin()) return;
  root.append(
    button("Request urgent assistance", () => emergencyForm(), "btn-primary"),
  );
  const items = state.private.emergencies || [];
  if (!items.length) empty(root, "No emergency cases visible to your account.");
  const grid = el("div", null, "resource-grid");
  for (const x of items) {
    const c = el("article", null, "panel emergency-card");
    append(
      c,
      el("h2", `#${x.id} · ${x.kind}`),
      el("strong", x.status.replaceAll("_", " ").toUpperCase(), "badge"),
      el("p", `${x.people} people · ${placeName(x)}`),
      userText("p", x.description),
      el(
        "p",
        x.assigned_name
          ? "Assigned volunteer: " + x.assigned_name
          : "No team assigned yet.",
        "meta",
      ),
      el("p", "Updated " + ago(x.updated_at), "meta"),
    );
    if (x.contact) c.append(userText("p", x.contact, "contact-detail"));
    if (x.pin)
      c.append(
        button("View exact pin", () =>
          showSavedPin(x.pin, "Emergency case #" + x.id),
        ),
      );
    const controls = el("div", null, "actions");
    if (state.private.user.can_coordinate) {
      if (x.status === "received")
        controls.append(
          button("Acknowledge", () => emergencyMove(x, "acknowledge")),
        );
      if (x.status === "acknowledged")
        controls.append(
          button("Assign volunteer", () =>
            actionForm(
              "Assign emergency case",
              [
                {
                  name: "volunteer",
                  label: "Volunteer",
                  required: true,
                  options: [
                    ["", "Select volunteer"],
                    ...(state.private.volunteers || []).map((v) => [
                      v.id,
                      v.username,
                    ]),
                  ],
                },
              ],
              (d) => api("emergency", { id: x.id, transition: "assign", ...d }),
            ),
          ),
        );
      if (x.status === "assigned")
        controls.append(
          button("Mark resolved", () =>
            actionForm(
              "Resolve emergency case",
              [
                {
                  name: "confirmation",
                  label: "Type RESOLVED after checking the outcome.",
                  required: true,
                },
              ],
              (d) => {
                if (d.confirmation !== "RESOLVED")
                  throw Error("Type RESOLVED to confirm.");
                return api("emergency", { id: x.id, transition: "resolve" });
              },
            ),
          ),
        );
    }
    if (
      !["resolved", "cancelled"].includes(x.status) &&
      (state.private.user.id === x.owner_id ||
        state.private.user.can_coordinate)
    )
      controls.append(
        button("Cancel case", () =>
          actionForm(
            "Cancel emergency case",
            [{ name: "confirmation", label: "Type CANCEL", required: true }],
            (d) => {
              if (d.confirmation !== "CANCEL")
                throw Error("Type CANCEL to confirm.");
              return api("emergency", { id: x.id, transition: "cancel" });
            },
          ),
        ),
      );
    c.append(controls);
    grid.append(c);
  }
  root.append(grid);
}
async function emergencyMove(x, transition) {
  await api("emergency", { id: x.id, transition });
  await refresh();
}
function emergencyForm() {
  const dialog = $("#actionDialog"),
    form = $("#actionForm");
  form.replaceChildren();
  $("#actionTitle").textContent = "Request urgent assistance";
  $("#actionError").textContent = "";
  const geo = el("div", null, "form-grid");
  geoFields(geo, state.private.user, true);
  form.append(geo);
  const fields = [
    ["kind", "Emergency type", "select"],
    ["people", "Number of people", "number"],
    ["area", "Local area / landmark", "text"],
    ["contact", "Contact details (authorized users only)", "text"],
    ["description", "Describe the assistance needed", "textarea"],
  ];
  for (const [name, label, type] of fields) {
    const l = el("label", label),
      input = el(
        type === "select"
          ? "select"
          : type === "textarea"
            ? "textarea"
            : "input",
      );
    input.name = name;
    input.required = !["contact"].includes(name);
    if (type === "select") {
      for (const x of ["medical", "trapped", "evacuation", "flood", "other"]) {
        const o = el("option", x);
        o.value = x;
        input.append(o);
      }
    } else if (type !== "textarea") input.type = type;
    if (type === "number") {
      input.min = 1;
      input.max = 10000;
      input.value = 1;
    }
    input.maxLength =
      name === "description" ? 2000 : name === "contact" ? 80 : 100;
    l.append(input);
    form.append(l);
  }
  pinFields(form, null, "private");
  const note = el(
    "p",
    "Wait for a server case number. Offline submission is not received by coordinators.",
    "notice warning",
  );
  form.append(note);
  const submit = el("button", "Send emergency case", "btn-primary");
  submit.type = "submit";
  form.append(submit);
  const cid = clientId();
  form.onsubmit = async (e) => {
    e.preventDefault();
    submit.disabled = true;
    try {
      const result = await api("emergency", {
        ...Object.fromEntries(new FormData(form)),
        client_id: cid,
      });
      dialog.close();
      await refresh();
      message(
        "Server received emergency case #" +
          result.id +
          ". Await coordinator acknowledgement.",
      );
    } catch (error) {
      $("#actionError").textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  };
  dialog.showModal();
}
function announcementDesk() {
  const root = title(
    "Area announcements",
    "Distribution schedules, shelter notices and updates issued by approved RESILIO officers.",
  );
  if (!state.online)
    root.append(
      el(
        "p",
        "Offline announcement snapshot. Notices may have changed or been withdrawn since the last update.",
        "notice warning",
      ),
    );
  const filters = el("div", null, "form-grid");
  let selected = state.private?.user.district || "";
  let selectedDivision = selected
    ? districtDivision(districtInfo(selected))
    : "";
  const board = el("div", null, "resource-grid");
  const draw = () => {
    board.replaceChildren();
    const rows = (state.public?.announcements || [])
      .filter((x) => x.active && new Date(x.expires_at).getTime() > Date.now())
      .filter(
        (x) =>
          !x.district ||
          (selected
            ? x.district === selected
            : !selectedDivision ||
              districtDivision(districtInfo(x.district)) === selectedDivision),
      );
    if (!rows.length) empty(board, "No current announcements for this area.");
    rows.forEach((x) => {
      const c = el("article", null, "panel");
      append(
        c,
        userText("h2", x.title),
        userText("p", x.body),
        el("p", x.issuer + " · " + x.author, "badge"),
        el(
          "p",
          (districtInfo(x.district)?.name || "All Bangladesh") +
            " · Expires " +
            new Date(x.expires_at).toLocaleString(),
          "meta",
        ),
      );
      if (
        state.private?.user.admin ||
        (state.private?.announcements_authored || []).some((a) => a.id === x.id)
      )
        c.append(
          button("Withdraw announcement", () =>
            actionForm(
              "Withdraw announcement",
              [
                {
                  name: "confirmation",
                  label: "Type WITHDRAW",
                  required: true,
                },
              ],
              (d) => {
                if (d.confirmation !== "WITHDRAW")
                  throw Error("Type WITHDRAW to confirm.");
                return api("announcement", { id: x.id });
              },
            ),
          ),
        );
      board.append(c);
    });
  };
  const scopeControls = geoFields(
    filters,
    { district: selected },
    false,
    (division, district) => {
      selectedDivision = division;
      selected = district;
      draw();
    },
  );
  scopeControls.upazila.closest("label").remove();
  root.append(filters);
  if (state.private?.user.can_coordinate)
    root.append(
      button(
        "Publish announcement",
        () =>
          actionForm(
            "Publish announcement",
            [
              {
                name: "district",
                label: "Audience district",
                options: [
                  ["", "All Bangladesh"],
                  ...geoCatalog().districts.map((d) => [d.code, d.name]),
                ],
              },
              { name: "title", label: "Title", required: true, maxlength: 160 },
              {
                name: "body",
                label: "Announcement",
                required: true,
                multiline: true,
                maxlength: 3000,
              },
              {
                name: "expires_at",
                label: "Expiry (within seven days)",
                type: "datetime-local",
                required: true,
              },
            ],
            (d) =>
              api("announcement", {
                ...d,
                expires_at: new Date(d.expires_at).toISOString(),
              }),
          ),
        "btn-primary",
      ),
    );
  root.append(board);
  draw();
}
async function assignmentThread(assignment) {
  const dialog = $("#actionDialog"),
    form = $("#actionForm");
  $("#actionTitle").textContent = "Assignment messages #" + assignment.id;
  $("#actionError").textContent = "";
  form.replaceChildren();
  const list = el("div", null, "message-thread");
  const status = el("p", "Loading messages…", "muted");
  const label = el("label", "Message to assignment participants"),
    input = el("textarea");
  input.name = "body";
  input.maxLength = 1500;
  input.required = true;
  label.append(input);
  const submit = el("button", "Send message", "btn-primary");
  submit.type = "submit";
  const reload = button("Refresh messages", async () => {
    try {
      render(await get());
    } catch (e) {
      $("#actionError").textContent = e.message;
    }
  });
  append(form, status, list, label, submit, reload);
  let cid = clientId();
  const get = async (before) => {
    const response = await fetch(
      "/api/messages/?assignment=" +
        assignment.id +
        (before ? "&before=" + before : ""),
      { credentials: "same-origin", cache: "no-store" },
    );
    const d = await response.json();
    if (!response.ok) throw Error(d.error);
    return d;
  };
  let before = null;
  const render = (r, prepend = false) => {
    const nodes = r.messages.map((x) =>
      append(
        el("article", null, "thread-message"),
        el("strong", x.sender),
        userText("p", x.body),
        el("small", new Date(x.created_at).toLocaleString()),
      ),
    );
    if (!prepend) list.replaceChildren(...nodes);
    else list.prepend(...nodes);
    before = r.before;
    older.hidden = !r.has_more;
    status.textContent =
      "Private to assignment participants and authorized coordinators.";
  };
  const older = button("Load older messages", async () => {
    try {
      render(await get(before), true);
    } catch (e) {
      $("#actionError").textContent = e.message;
    }
  });
  older.hidden = true;
  form.insertBefore(older, label);
  form.onsubmit = async (e) => {
    e.preventDefault();
    submit.disabled = true;
    try {
      await api("message", {
        assignment: assignment.id,
        body: input.value,
        client_id: cid,
      });
      input.value = "";
      cid = clientId();
      render(await get());
    } catch (error) {
      $("#actionError").textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  };
  dialog.showModal();
  try {
    render(await get());
  } catch (error) {
    $("#actionError").textContent = error.message;
  }
}
async function offlineReadiness(root) {
  const box = el("section", null, "panel offline-readiness");
  box.append(el("h2", "Offline readiness"));
  root.append(box);
  let assets = false;
  try {
    if ("caches" in window) {
      const cacheNames = (await caches.keys()).filter((k) =>
        k.startsWith("resilio-assets-"),
      );
      const latest = cacheNames
        .sort(
          (a, b) => Number(a.split("v").at(-1)) - Number(b.split("v").at(-1)),
        )
        .at(-1);
      if (latest) {
        const c = await caches.open(latest);
        assets = (
          await Promise.all(
            [
              "/static/resilio/offline.html",
              "/static/resilio/geo/districts.geojson",
              "/static/resilio/geo/divisions.geojson",
              "/static/resilio/fieldops.js",
              "/static/resilio/localareas.js",
              "/static/resilio/i18n.js",
              "/static/resilio/fonts/bengali.ttf",
              "/static/resilio/app.js",
              "/static/resilio/app.css",
              "/static/resilio/geography.js",
              "/static/resilio/network.js",
              "/static/resilio/vendor/leaflet/leaflet.js",
              "/static/resilio/vendor/leaflet/leaflet.css",
            ].map((p) => c.match(p)),
          )
        ).every(Boolean);
      }
    }
  } catch (e) {}
  const rows = await storage("queue", "getAll").catch(() => []);
  append(
    box,
    el(
      "p",
      assets
        ? "Boundary map saved for offline use"
        : "Offline map is not fully installed. Connect and reload this site.",
      assets ? "good" : "warning",
    ),
    el(
      "p",
      state.online
        ? "Server reachable"
        : "Server unreachable — live coordination unavailable",
      state.online ? "good" : "warning",
    ),
    el(
      "p",
      "Last public update: " +
        (state.public?.synced_at
          ? new Date(state.public.synced_at).toLocaleString()
          : "No snapshot saved"),
    ),
    el(
      "p",
      "Pending requests: " +
        rows.filter(
          (x) =>
            x.state !== "Synced" &&
            Number(x.account_id) ===
              Number(state.private?.user.id || state.lastAccount),
        ).length,
    ),
    el(
      "p",
      "Exact participant locations, emergency cases and assignment messages require a valid session and reachable server. Offline street tiles are not included.",
      "muted",
    ),
  );
  box.append(button("Check readiness again", () => renderScreen()));
}
function shelterLocationForm(s) {
  const form = $("#actionForm"),
    dialog = $("#actionDialog");
  $("#actionTitle").textContent = "Set shelter location";
  $("#actionError").textContent = "";
  form.replaceChildren();
  const geo = el("div", null, "form-grid");
  geoFields(geo, s, true);
  form.append(geo);
  const label = el("label", "Local area / landmark"),
    input = el("input");
  input.name = "area";
  input.value = s.area;
  input.required = true;
  input.maxLength = 100;
  label.append(input);
  form.append(label);
  pinFields(form, s.pin, "public");
  const submit = el("button", "Save on server", "btn-primary");
  submit.type = "submit";
  form.append(submit);
  form.onsubmit = async (e) => {
    e.preventDefault();
    submit.disabled = true;
    try {
      await api("shelter_place", {
        id: s.id,
        ...Object.fromEntries(new FormData(form)),
      });
      dialog.close();
      await refresh();
      message("Shelter location saved.");
    } catch (error) {
      $("#actionError").textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  };
  dialog.showModal();
}
