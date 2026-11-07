/* Server-mediated presence. Decorative motion never implies GPS or P2P links. */
let mapFrame = null,
  mapTimer = null,
  mapObserver = null,
  mapContext = null,
  mapGeneration = 0;
let mapMode = "live",
  liveParticipants = [];
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
function stopNetwork() {
  mapGeneration++;
  if (mapFrame) cancelAnimationFrame(mapFrame);
  clearInterval(mapTimer);
  mapObserver?.disconnect();
  mapFrame = null;
  mapTimer = null;
  mapObserver = null;
  mapContext = null;
}
function network() {
  const root = title(
    "Live coordination map",
    "See shared areas and people recently seen by this relief-center server.",
  );
  mountNetwork(root, false);
  const modes = el("section", null, "communication-grid");
  for (const [label, description] of [
    [
      "Internet available",
      "Browsers connect to the hosted Django server. Requests, stock and delivery updates are saved in its database.",
    ],
    [
      "Same Wi-Fi · no internet",
      "Phones connect to the laptop server through the same router or hotspot. The server passes updates between participants.",
    ],
    [
      "Server unreachable",
      "Public information comes from the last cached snapshot. New help requests stay on the device until the creating account reconnects and synchronizes.",
    ],
  ]) {
    modes.append(
      append(
        el("article", null, "panel"),
        el("h3", label),
        el("p", description),
      ),
    );
  }
  root.append(
    modes,
    el(
      "p",
      "Separate relief-center servers, Bluetooth transfer and phone-to-phone relaying are future extensions.",
      "muted",
    ),
  );
}
function mountNetwork(root, compact) {
  const generation = mapGeneration;
  const panel = el("section", null, "network-panel");
  const toolbar = el("div", null, "network-toolbar");
  const titleBlock = append(
    el("div"),
    el("span", "RELIEF-CENTER CONNECTIONS", "section-tag"),
    el("h2", compact ? "Your community, connected" : "Connected participants"),
  );
  const controls = el("div", null, "map-controls");
  const live = button("Live activity", () => switchMode("live"));
  const demo = button("Demo animation", () => switchMode("demo"));
  live.setAttribute("aria-pressed", String(mapMode === "live"));
  demo.setAttribute("aria-pressed", String(mapMode === "demo"));
  append(controls, live, demo);
  append(toolbar, titleBlock, controls);
  panel.append(toolbar);
  const banner = el("div", null, "notice");
  banner.id = "mapStatus";
  banner.style.margin = "0";
  panel.append(banner);
  const body = el("div", null, "network-body"),
    stage = el("div", null, "map-stage"),
    canvas = el("canvas");
  canvas.id = "coordinationMap";
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    "Schematic area diagram of server-connected participants. A participant list follows.",
  );
  stage.append(canvas);
  const caption = el(
    "p",
    "Schematic positions, not GPS. Moving dots are visual animation; links connect participants to the server.",
    "map-caption",
  );
  stage.append(caption);
  const list = el("div", null, "participant-list");
  list.setAttribute("aria-label", "Participants and areas");
  body.append(stage, list);
  panel.append(body);
  const legend = el("div", null, "map-legend");
  append(
    legend,
    el("span", "Shared area"),
    el("span", "Participant / officer"),
  );
  panel.append(legend);
  const actions = el("div", null, "actions");
  actions.style.padding = "15px 20px";
  if (state.private) {
    const u = state.private.user;
    actions.append(
      button(
        u.share_presence ? "Stop sharing my presence" : "Share my presence",
        async () => {
          if (u.share_presence) {
            await api("presence", { enabled: false });
            u.share_presence = false;
            liveParticipants = liveParticipants.filter(
              (p) => p.label !== u.public_label,
            );
            await load();
            message("Presence sharing stopped.");
            await refresh(false);
            renderScreen();
          } else {
            await actionForm(
              "Share presence with signed-in participants",
              [
                {
                  name: "label",
                  label:
                    "Public display label (optional, maximum 40 characters)",
                  maxlength: 40,
                },
              ],
              async (d) => {
                await api("presence", { enabled: true, label: d.label });
                state.private.user.share_presence = true;
              },
              "Presence sharing enabled. Your label, role and chosen area can appear to signed-in participants.",
            );
          }
        },
      ),
    );
    const profile = el("a", "Set my area in Profile", "button");
    profile.href = "#profile";
    actions.append(profile);
  } else {
    const signin = el(
      "a",
      "Sign in to share presence",
      "button account-signin",
    );
    signin.href = "/access/";
    actions.append(signin);
  }
  if (compact) {
    const full = el("a", "Open full map →", "button");
    full.href = "#network";
    actions.append(full);
  }
  panel.append(actions);
  root.append(panel);
  let ctx = null;
  if (typeof window.CanvasRenderingContext2D !== "undefined")
    try {
      ctx = canvas.getContext("2d");
    } catch (e) {}
  if (!ctx) {
    canvas.hidden = true;
    stage.insertBefore(
      el(
        "p",
        "Diagram unavailable in this browser. Use the area and participant list.",
        "notice",
      ),
      caption,
    );
  }
  const areas = () =>
    [
      ...new Set(
        [
          ...(state.public?.offers || []),
          ...(state.public?.requests || []),
          ...(state.public?.shelters || []),
        ]
          .map((r) => r.area)
          .concat(liveParticipants.map((p) => p.area)),
      ),
    ]
      .filter(Boolean)
      .sort();
  const demoPeople = () =>
    Array.from({ length: 10 }, (_, i) => ({
      key: "demo-" + i,
      label: "Demo participant " + (i + 1),
      role: i % 3 === 0 ? "NGO / Relief Officer" : "Volunteer",
      area:
        (areas().length ? areas() : ["mirpur", "uttara", "dhanmondi"])[
          i % Math.max(areas().length, 1)
        ] || "mirpur",
    }));
  function people() {
    return mapMode === "demo" ? demoPeople() : liveParticipants;
  }
  function redrawList() {
    list.replaceChildren();
    const data = people();
    list.append(
      el(
        "h3",
        mapMode === "demo"
          ? "Fictional participants"
          : `${data.length} recently seen participant${data.length === 1 ? "" : "s"}`,
      ),
    );
    if (!data.length)
      list.append(
        el(
          "p",
          state.private
            ? "No opted-in participants have been seen in the last 75 seconds. Share your presence to appear here."
            : "Sign in to view opted-in participants. Public areas are shown below.",
          "muted",
        ),
      );
    data.forEach((p) =>
      append(
        list,
        append(
          el("div", null, "participant-row"),
          el("strong", p.label),
          el("span", `${p.role} · ${p.area}`),
          el(
            "p",
            mapMode === "demo"
              ? "Simulation"
              : `Last heartbeat ${ago(p.last_seen)}`,
            "meta",
          ),
        ),
      ),
    );
    list.append(el("h3", "Area resource list"));
    areas().forEach((area) => {
      const offers = (state.public?.offers || []).filter(
        (o) => o.area === area && Number(o.available) > 0,
      ).length;
      const needs = (state.public?.requests || []).filter(
        (r) => r.area === area && r.status === "open",
      ).length;
      list.append(
        append(
          el("div", null, "participant-row"),
          el("strong", area),
          el("span", `${offers} available offers / ${needs} open requests`),
        ),
      );
    });
  }
  async function load() {
    if (generation !== mapGeneration || !panel.isConnected) return;
    if (state.private && state.online) {
      try {
        if (state.private.user.share_presence) await api("presence", {});
        const data = await api("presence");
        if (generation !== mapGeneration) return;
        liveParticipants = data.participants || [];
      } catch (e) {
        liveParticipants = [];
      }
    } else liveParticipants = [];
    banner.textContent =
      mapMode === "demo"
        ? "SIMULATION · Fictional moving participants. This mode does not represent actual users or locations."
        : !state.online
          ? "Server unreachable · Live presence is unavailable. Area records may be cached."
          : state.private
            ? "LIVE SERVER ACTIVITY · Opted-in participants seen in the last 75 seconds. Presence updates every 15 seconds."
            : "PUBLIC AREA VIEW · Sign in to see opted-in server participants, or explore the labeled demo animation.";
    banner.className = "notice " + (mapMode === "demo" ? "warning" : "");
    redrawList();
  }
  function switchMode(mode) {
    mapMode = mode;
    live.setAttribute("aria-pressed", String(mode === "live"));
    demo.setAttribute("aria-pressed", String(mode === "demo"));
    load();
  }
  function draw(time) {
    if (generation !== mapGeneration || !panel.isConnected) return;
    if (!ctx) return;
    const w = canvas.clientWidth || 700,
      h = canvas.clientHeight || 440,
      dpr = Math.min(devicePixelRatio || 1, 2);
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const css = getComputedStyle(document.documentElement),
      color = (n) => css.getPropertyValue(n).trim();
    ctx.fillStyle = color("--bg");
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = color("--border");
    ctx.globalAlpha = 0.17;
    ctx.lineWidth = 0.5;
    for (let x = 0; x < w; x += 32) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 32) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    const hubs = areas();
    if (!hubs.length) hubs.push("Set an area");
    const center = { x: w / 2, y: h / 2 };
    const radius = Math.min(w * 0.31, h * 0.3);
    const positions = hubs.map((name, i) => ({
      name,
      x: center.x + Math.cos((i / hubs.length) * Math.PI * 2 - 1) * radius,
      y: center.y + Math.sin((i / hubs.length) * Math.PI * 2 - 1) * radius,
    }));
    positions.forEach((hub) => {
      ctx.beginPath();
      ctx.moveTo(center.x, center.y);
      ctx.lineTo(hub.x, hub.y);
      ctx.strokeStyle = color("--available");
      ctx.globalAlpha = 0.45;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.arc(hub.x, hub.y, 29, 0, Math.PI * 2);
      ctx.fillStyle = color("--surface");
      ctx.fill();
      ctx.strokeStyle = color("--available");
      ctx.stroke();
      ctx.fillStyle = color("--text");
      ctx.font = "bold 12px ResilioUI, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(
        hub.name.length > 20 ? hub.name.slice(0, 18) + "…" : hub.name,
        hub.x,
        hub.y + 47,
      );
      ctx.fillStyle = color("--available");
      ctx.font = "18px ResilioDisplay";
      ctx.fillText(
        String(
          (state.public?.offers || []).filter(
            (o) => o.area === hub.name && Number(o.available) > 0,
          ).length,
        ),
        hub.x,
        hub.y + 6,
      );
    });
    const participants = people();
    participants.forEach((p, i) => {
      const hub =
        positions.find((h) => h.name === p.area) ||
        positions[i % positions.length];
      const t = (reduced.matches ? 0 : time * 0.00012) + i * 2.4,
        r = 43 + (i % 3) * 9;
      const px = Math.max(12, Math.min(w - 12, hub.x + Math.cos(t) * r)),
        py = Math.max(12, Math.min(h - 30, hub.y + Math.sin(t) * r));
      ctx.beginPath();
      ctx.moveTo(center.x, center.y);
      ctx.lineTo(px, py);
      ctx.strokeStyle = color("--officer");
      ctx.globalAlpha = 0.16;
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.arc(px, py, 6, 0, Math.PI * 2);
      ctx.fillStyle = color("--officer");
      ctx.fill();
      ctx.strokeStyle = color("--surface");
      ctx.lineWidth = 2;
      ctx.stroke();
    });
    ctx.fillStyle = color("--surface");
    ctx.strokeStyle = color("--urgent");
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(center.x - 48, center.y - 24, 96, 48, 8);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = color("--text");
    ctx.textAlign = "center";
    ctx.font = "bold 11px ResilioUI, sans-serif";
    ctx.fillText("RELIEF SERVER", center.x, center.y + 4);
    ctx.fillStyle = color("--muted");
    ctx.font = "11px ResilioUI";
    ctx.textAlign = "left";
    ctx.fillText(
      mapMode === "demo"
        ? "SIMULATION / VISUAL MOTION"
        : "SCHEMATIC / SERVER-MEDIATED",
      15,
      25,
    );
    mapFrame = requestAnimationFrame(draw);
  }
  load();
  mapTimer = setInterval(load, 15000);
  if (ctx) {
    mapContext = ctx;
    mapFrame = requestAnimationFrame(draw);
  }
}
