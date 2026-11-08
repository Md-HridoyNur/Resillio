/* Bangladesh map. Personal coordinates remain in memory unless separately shared. */
const geoState = {
  data: null,
  division: "",
  district: "",
  upazila: "",
  view: null,
  map: null,
  timer: null,
  watch: null,
  generation: 0,
  position: null,
  tracking: false,
  detectedDistrict: null,
  onTheme: null,
};
let liveParticipants = [];
function stopNetwork() {
  geoState.generation++;
  clearInterval(geoState.timer);
  geoState.timer = null;
  if (geoState.watch !== null && navigator.geolocation) {
    navigator.geolocation.clearWatch(geoState.watch);
    geoState.watch = null;
  }
  if (geoState.map) {
    if (geoState.map._loaded) {
      const c = geoState.map.getCenter();
      geoState.view = { center: [c.lat, c.lng], zoom: geoState.map.getZoom() };
    }
    geoState.map.stop();
    geoState.map.remove();
    geoState.map = null;
  }
  if (geoState.onTheme)
    document.removeEventListener("resilio-theme", geoState.onTheme);
  geoState.onTheme = null;
}
function pointInRing(x, y, ring) {
  let yes = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i],
      b = ring[j];
    if (
      a[1] > y !== b[1] > y &&
      x < ((b[0] - a[0]) * (y - a[1])) / (b[1] - a[1]) + a[0]
    )
      yes = !yes;
  }
  return yes;
}
function pointInGeometry(lat, lon, geometry) {
  const polygons =
    geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  return polygons.some(
    (p) =>
      pointInRing(lon, lat, p[0]) &&
      !p.slice(1).some((h) => pointInRing(lon, lat, h)),
  );
}
async function loadBangladesh() {
  if (geoState.data) return geoState.data;
  const data = await Promise.all(
    ["divisions", "districts"].map(async (name) => {
      const response = await fetch("/static/resilio/geo/" + name + ".geojson");
      if (!response.ok)
        throw Error(
          "Could not load boundary data. Connect once to install the offline map.",
        );
      return response.json();
    }),
  );
  geoState.data = { divisions: data[0], districts: data[1] };
  return geoState.data;
}
function network() {
  const root = title(
    "Bangladesh relief map",
    "Explore 8 divisions and 64 districts. Locate yourself privately, then choose whether to share a pin.",
  );
  mountNetwork(root, false);
  const modes = el("section", null, "communication-grid");
  for (const [name, text] of [
    [
      "Your location",
      "Use my location asks the browser for permission. The blue pin, accuracy circle and reading time stay on this device until you explicitly share the pin.",
    ],
    [
      "Offline map",
      "Division and district boundaries are bundled for offline use after installation. The optional street background needs internet and is not downloaded for offline use.",
    ],
    [
      "Shared coordination",
      "Signed-in participants can opt in to presence or a precise pin. Server connection and last update times determine what others can see.",
    ],
  ])
    modes.append(
      append(el("article", null, "panel"), el("h3", name), el("p", text)),
    );
  root.append(modes);
}
function mountNetwork(root, compact) {
  const generation = geoState.generation,
    valid = () => generation === geoState.generation && panel.isConnected;
  const panel = el("section", null, "network-panel bangladesh-panel");
  const toolbar = el("div", null, "network-toolbar");
  append(
    toolbar,
    append(
      el("div"),
      el("span", "BANGLADESH / LOCATION INTELLIGENCE", "section-tag"),
      el(
        "h2",
        compact
          ? "Find help. Know your area."
          : "Bangladesh · divisions & districts",
      ),
    ),
  );
  const actions = el("div", null, "map-controls");
  const country = button("All Bangladesh", () => choose("", ""));
  const locate = button(
    "Use my location",
    () => startLocation(),
    "btn-primary",
  );
  const stop = button("Stop location", () => stopLocation());
  stop.hidden = !geoState.tracking;
  append(actions, country, locate, stop);
  toolbar.append(actions);
  panel.append(toolbar);
  const filters = el("div", null, "map-geography-controls");
  const selectors = geoFields(
    filters,
    geoState,
    false,
    (division, district, upazila) => {
      geoState.upazila = upazila || "";
      choose(division, district);
    },
  );
  panel.append(filters);
  const notice = el("p", "Loading geographic boundaries…", "notice");
  notice.id = "mapStatus";
  notice.style.margin = "0";
  panel.append(notice);
  const body = el("div", null, "network-body");
  const stage = el("div", null, "map-stage");
  const mapElement = el("div");
  mapElement.id = "coordinationMap";
  mapElement.setAttribute("role", "region");
  mapElement.setAttribute(
    "aria-label",
    "Bangladesh geographic map. Use division and district selectors or the adjacent list as alternatives.",
  );
  stage.append(mapElement);
  const caption = el(
    "p",
    "Real geographic boundaries · No automatic GPS access · District summary markers are approximate",
    "map-caption",
  );
  stage.append(caption);
  const list = el("div", null, "participant-list");
  list.setAttribute("aria-label", "Selected area resources and participants");
  body.append(stage, list);
  panel.append(body);
  const legend = el("div", null, "geo-legend");
  for (const [label, kind] of [
    ["Your device position", "self"],
    ["Shared participant", "person"],
    ["District resource summary", "resource"],
    ["Shelter / district level", "shelter"],
  ])
    legend.append(el("span", label, "geo-key " + kind));
  panel.append(legend);
  const locationInfo = el("div", null, "location-info");
  locationInfo.id = "locationInfo";
  panel.append(locationInfo);
  const tools = el("div", null, "actions map-footer-actions");
  const streets = button("Street background (online)", () => toggleStreets());
  streets.setAttribute("aria-pressed", "false");
  tools.append(streets);
  if (state.private) {
    const u = state.private.user;
    tools.append(
      button(
        u.share_presence ? "Stop sharing my presence" : "Share my presence",
        async () => {
          if (u.share_presence) {
            await api("presence", { enabled: false });
            u.share_presence = false;
            u.share_location = false;
            liveParticipants = [];
            await refresh(false);
            renderScreen();
            message("Presence and shared pin removed.");
          } else
            await actionForm(
              "Share presence",
              [
                {
                  name: "label",
                  label: "Display label for signed-in participants (optional)",
                  maxlength: 40,
                },
              ],
              async (d) => api("presence", { enabled: true, label: d.label }),
              "Area-level presence enabled. A precise pin is still private.",
            );
        },
      ),
    );
    const share = button(
      u.share_location ? "Stop sharing my pin" : "Share my pin",
      async () => {
        if (u.share_location) {
          await api("location", { enabled: false });
          u.share_location = false;
          await refresh(false);
          renderScreen();
          message(
            "Shared coordinates removed from the server. Your local blue pin is unchanged.",
          );
          return;
        }
        if (
          !geoState.position ||
          Date.now() - geoState.position.timestamp > 120000
        )
          throw Error("Use my location first to capture a fresh reading.");
        await actionForm(
          "Share a precise location",
          [
            {
              name: "confirmation",
              label:
                "Signed-in participants can see your precise pin and accuracy while it is fresh. Type SHARE to opt in.",
              required: true,
            },
          ],
          async (d) => {
            if (d.confirmation !== "SHARE")
              throw Error("Type SHARE to confirm.");
            if (!u.share_presence) await api("presence", { enabled: true });
            await publishPosition();
            u.share_location = true;
          },
          "Precise pin shared with signed-in participants. You can stop sharing at any time.",
        );
      },
    );
    tools.append(share);
    const profile = el("a", "Set my home district", "button");
    profile.href = "#profile";
    tools.append(profile);
  } else {
    const sign = el("a", "Sign in to share presence", "button");
    sign.href = "/access/";
    tools.append(sign);
  }
  if (compact) {
    const full = el("a", "Open full map →", "button");
    full.href = "#network";
    tools.append(full);
  }
  panel.append(tools);
  const attribution = el("p", null, "geo-attribution");
  append(
    attribution,
    el("span", "Boundaries: geoBoundaries; district source BBS / OCHA ROAP. "),
  );
  const source = el("a", "Sources & licences");
  source.href = "/static/resilio/geo/ATTRIBUTION.txt";
  source.target = "_blank";
  source.rel = "noopener";
  attribution.append(source);
  panel.append(attribution);
  root.append(panel);
  let map = null,
    divisionLayer = null,
    districtLayer = null,
    recordLayer = null,
    peopleLayer = null,
    selfLayer = null,
    streetLayer = null,
    geoData = null;
  const colors = [
    "#3979ca",
    "#a06bc4",
    "#14937e",
    "#d08d23",
    "#cb6279",
    "#658c36",
    "#5a82b8",
    "#a66d3b",
  ];
  function css(name) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
  }
  function regionVisible(record) {
    let division = record.division,
      district = record.district;
    if (record.location && geoData) {
      const area = geoData.districts.features.find((f) =>
        pointInGeometry(
          Number(record.location.latitude),
          Number(record.location.longitude),
          f.geometry,
        ),
      );
      district = area?.properties.code;
      division = area?.properties.division;
    }
    return (
      (!geoState.division || division === geoState.division) &&
      (!geoState.district || district === geoState.district) &&
      (!geoState.upazila ||
        record.last_seen ||
        record.upazila === geoState.upazila)
    );
  }
  function choose(division, district) {
    if (geoState.district !== (district || "")) geoState.upazila = "";
    geoState.division = division || "";
    geoState.district = district || "";
    selectors.division.value = geoState.division;
    const options = geoCatalog().districts.filter(
      (d) => !division || districtDivision(d) === division,
    );
    selectors.district.replaceChildren();
    const option = el("option", "All / not selected");
    option.value = "";
    selectors.district.append(option);
    options.forEach((d) => {
      const o = el("option", d.name);
      o.value = d.code;
      selectors.district.append(o);
    });
    selectors.district.value = geoState.district;
    selectors.refreshLocality();
    selectors.upazila.value = geoState.upazila || "";
    drawAreas(true);
    drawRecords();
    drawExactPlaces();
    drawPeople();
    renderList();
  }
  function popup(title, text) {
    return append(
      el("div", null, "geo-popup"),
      el("strong", title),
      el("p", text),
    );
  }
  function drawAreas(fit = false) {
    if (!map || !geoData) return;
    if (divisionLayer) map.removeLayer(divisionLayer);
    if (districtLayer) map.removeLayer(districtLayer);
    divisionLayer = L.geoJSON(geoData.divisions, {
      style: (f) => {
        const i = geoCatalog().divisions.findIndex(
          (d) => d.code === f.properties.code,
        );
        const selected =
          !geoState.division || geoState.division === f.properties.code;
        return {
          color: css("--text"),
          weight: 1.3,
          fillColor: colors[(i + 8) % 8],
          fillOpacity: geoState.division ? (selected ? 0.1 : 0.05) : 0.32,
          opacity: selected ? 0.75 : 0.22,
        };
      },
      onEachFeature: (f, l) => {
        l.bindTooltip(
          popup(f.properties.name, "Division · click to explore districts"),
          { sticky: true },
        );
        l.on("click", () => choose(f.properties.code, ""));
      },
    }).addTo(map);
    districtLayer = L.geoJSON(geoData.districts, {
      filter: (f) =>
        !geoState.division || f.properties.division === geoState.division,
      style: (f) => ({
        color:
          f.properties.code === geoState.district ? "#b91c1c" : css("--border"),
        weight: f.properties.code === geoState.district ? 3 : 1,
        fillColor:
          f.properties.code === geoState.district
            ? "#f8a23c"
            : css("--available"),
        fillOpacity:
          f.properties.code === geoState.district
            ? 0.3
            : geoState.division
              ? 0.09
              : 0.015,
      }),
      onEachFeature: (f, l) => {
        l.bindTooltip(
          popup(f.properties.name, "District · click to view resources"),
          { sticky: true },
        );
        l.on("click", () => choose(f.properties.division, f.properties.code));
      },
    }).addTo(map);
    if (fit) {
      let bounds = divisionLayer.getBounds();
      if (geoState.district) {
        const f = geoData.districts.features.find(
          (f) => f.properties.code === geoState.district,
        );
        if (f) bounds = L.geoJSON(f).getBounds();
      } else if (geoState.division) {
        const f = geoData.divisions.features.find(
          (f) => f.properties.code === geoState.division,
        );
        if (f) bounds = L.geoJSON(f).getBounds();
      }
      map.fitBounds(bounds, {
        padding: [25, 25],
        animate: false,
      });
    }
  }
  function drawRecords() {
    if (!map) return;
    if (recordLayer) map.removeLayer(recordLayer);
    recordLayer = L.layerGroup().addTo(map);
    for (const district of geoCatalog().districts) {
      const rows = [
        ...(state.public?.offers || []),
        ...(state.public?.requests || []),
      ].filter((r) => r.district === district.code && r.status === "open");
      const shelters = (state.public?.shelters || []).filter(
        (s) => s.district === district.code,
      );
      if (!rows.length && !shelters.length) continue;
      if (
        (geoState.division &&
          districtDivision(district) !== geoState.division) ||
        (geoState.district && district.code !== geoState.district)
      )
        continue;
      const offers = rows.filter(
          (r) => r.kind === "offer" && Number(r.available) > 0,
        ).length,
        requests = rows.filter((r) => r.kind === "request").length;
      const marker = L.circleMarker([district.latitude, district.longitude], {
        radius: 10 + Math.min(rows.length, 10),
        color: css("--surface"),
        weight: 2,
        fillColor: requests ? "#c3342b" : "#177c4c",
        fillOpacity: 0.9,
      });
      marker.bindPopup(
        popup(
          district.name,
          `${offers} available offers · ${requests} open requests · ${shelters.length} shelters. District-level summary, not exact pickup positions.`,
        ),
      );
      marker.on("click", () =>
        choose(districtDivision(district), district.code),
      );
      marker.addTo(recordLayer);
    }
  }
  function drawExactPlaces() {
    if (!map || !recordLayer) return;
    if (geoState.focusPin && (!geoState.focusPin.private || state.private)) {
      const p = geoState.focusPin;
      L.circleMarker([Number(p.latitude), Number(p.longitude)], {
        radius: 10,
        color: "#fff",
        weight: 3,
        fillColor: "#a31c92",
        fillOpacity: 1,
      })
        .bindPopup(popup(p.name, p.label || "Saved creator-provided location"))
        .addTo(recordLayer);
    }
    const records = [
      ...(state.public?.offers || []),
      ...(state.public?.requests || []),
    ].filter(regionVisible);
    for (const r of records) {
      const pin = storedPin(r);
      if (!pin) continue;
      L.circleMarker([Number(pin.latitude), Number(pin.longitude)], {
        radius: 7,
        color: "#fff",
        weight: 2,
        fillColor: r.kind === "offer" ? "#177c4c" : "#c3342b",
        fillOpacity: 1,
      })
        .bindPopup(
          popup(
            r.name,
            (pin.label || r.area) +
              " · Creator-provided exact pin" +
              (r.kind === "request" ? " · Authorized users only" : ""),
          ),
        )
        .addTo(recordLayer);
    }
    for (const s of (state.public?.shelters || []).filter(regionVisible)) {
      if (!s.pin) continue;
      L.circleMarker([Number(s.pin.latitude), Number(s.pin.longitude)], {
        radius: 9,
        color: "#fff",
        weight: 2,
        fillColor: "#147d65",
        fillOpacity: 1,
      })
        .bindPopup(
          popup(
            s.name,
            (s.pin.label || s.area) +
              " · " +
              s.available +
              " available spaces · Creator-provided facility pin",
          ),
        )
        .addTo(recordLayer);
    }
  }
  function drawPeople() {
    if (!map) return;
    if (peopleLayer) map.removeLayer(peopleLayer);
    peopleLayer = L.layerGroup().addTo(map);
    for (const p of liveParticipants) {
      if (!regionVisible(p)) continue;
      const loc = p.location;
      const district = districtInfo(p.district);
      if (!loc && !district) continue;
      const lat = loc ? Number(loc.latitude) : district.latitude,
        lon = loc ? Number(loc.longitude) : district.longitude;
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
      const point = L.circleMarker([lat, lon], {
        radius: 7,
        color: css("--surface"),
        weight: 2,
        fillColor: css("--officer"),
        fillOpacity: 1,
      });
      point.bindPopup(
        popup(
          p.label,
          `${p.role} · ${loc ? "Shared device pin, accuracy ±" + Math.round(loc.accuracy) + " m; reading " + ago(loc.updated_at) : "District-level position only, not GPS"} · Last seen ${ago(p.last_seen)}`,
        ),
      );
      point.addTo(peopleLayer);
      if (loc)
        L.circle([lat, lon], {
          radius: Number(loc.accuracy) || 1,
          color: css("--officer"),
          weight: 1,
          fillOpacity: 0.08,
        }).addTo(peopleLayer);
    }
  }
  function drawSelf(center = false) {
    if (!map) return;
    if (selfLayer) map.removeLayer(selfLayer);
    selfLayer = L.layerGroup().addTo(map);
    const p = geoState.position;
    if (!p) return;
    L.circle([p.latitude, p.longitude], {
      radius: p.accuracy || 1,
      color: "#1875e7",
      weight: 1,
      fillColor: "#3b9af5",
      fillOpacity: 0.15,
    }).addTo(selfLayer);
    const marker = L.circleMarker([p.latitude, p.longitude], {
      radius: 9,
      color: "#fff",
      weight: 3,
      fillColor: "#1875e7",
      fillOpacity: 1,
    }).addTo(selfLayer);
    marker.bindPopup(
      popup(
        "You are here",
        `Browser-reported position · Accuracy ±${Math.round(p.accuracy)} m · ${new Date(p.timestamp).toLocaleTimeString()}. ${state.private?.user.share_location ? "Sharing is enabled." : "Only visible on this device."}`,
      ),
    );
    if (center)
      map.setView([p.latitude, p.longitude], p.accuracy > 2000 ? 11 : 15, {
        animate: false,
      });
  }
  function renderLocation() {
    locationInfo.replaceChildren();
    const p = geoState.position;
    if (!p) {
      locationInfo.append(
        el(
          "p",
          "Your location is private by default. Select Use my location to request browser permission.",
          "muted",
        ),
      );
      return;
    }
    const district = districtInfo(geoState.detectedDistrict);
    append(
      locationInfo,
      el(
        "strong",
        district
          ? "Your detected district: " + district.name
          : "Your device position",
      ),
      el(
        "p",
        `${p.latitude.toFixed(6)}, ${p.longitude.toFixed(6)} · Accuracy ±${Math.round(p.accuracy)} m · Captured ${new Date(p.timestamp).toLocaleTimeString()}`,
      ),
      el(
        "p",
        geoState.tracking
          ? "Device updates are active while this map is open. Sharing with others is a separate choice."
          : "Last reading only. Device updates are stopped.",
        "muted",
      ),
    );
    if (district)
      locationInfo.append(
        button("View resources in " + district.name, () =>
          choose(districtDivision(district), district.code),
        ),
      );
    if (!district)
      locationInfo.append(
        el(
          "p",
          "No district boundary matched this reading. The position may be outside Bangladesh, near a boundary, or too imprecise. Select your district manually.",
          "muted",
        ),
      );
  }
  function renderList() {
    list.replaceChildren();
    const district = districtInfo(geoState.district),
      division = geoCatalog().divisions.find(
        (d) => d.code === geoState.division,
      );
    append(
      list,
      el("h3", district?.name || division?.name || "Bangladesh"),
      el(
        "p",
        district
          ? "District selected"
          : division
            ? "Division selected"
            : "8 divisions · 64 districts",
        "meta",
      ),
    );
    const districts = geoCatalog().districts.filter(
      (d) => !geoState.division || districtDivision(d) === geoState.division,
    );
    if (!geoState.district) {
      const select = el("div", null, "district-shortcuts");
      districts.forEach((d) =>
        select.append(
          button(d.name, () => choose(districtDivision(d), d.code)),
        ),
      );
      list.append(select);
    }
    const records = [
      ...(state.public?.requests || []),
      ...(state.public?.offers || []),
    ].filter(regionVisible);
    list.append(el("h3", "Resource activity"));
    if (!records.length)
      list.append(el("p", "No records in this selection.", "muted"));
    records.forEach((r) => {
      const row = append(
        el("div", null, "participant-row"),
        el("strong", r.name + " · " + r.kind),
        el(
          "span",
          `${r.kind === "offer" ? num(r.available) : num(r.remaining)} ${r.unit} · ${r.area}`,
        ),
        el(
          "p",
          r.district_name || "District not selected — not plotted",
          "meta",
        ),
      );
      if (r.kind === "request" && r.status === "open")
        row.append(button("View compatible offers", () => matches(r)));
      list.append(row);
    });
    const shelters = (state.public?.shelters || []).filter(regionVisible);
    if (shelters.length) {
      list.append(el("h3", "Shelters"));
      shelters.forEach((s) =>
        list.append(
          append(
            el("div", null, "participant-row"),
            el("strong", s.name),
            el("span", `${s.available} available spaces · ${s.area}`),
          ),
        ),
      );
    }
    list.append(
      el(
        "h3",
        `Shared participants (${liveParticipants.filter(regionVisible).length})`,
      ),
    );
    liveParticipants
      .filter(regionVisible)
      .forEach((p) =>
        list.append(
          append(
            el("div", null, "participant-row"),
            el("strong", p.label),
            el("span", p.role + " · " + p.area),
            el(
              "p",
              p.location
                ? "Shared pin · " + ago(p.location.updated_at)
                : p.district
                  ? "District only · " + ago(p.last_seen)
                  : "No map position shared",
              "meta",
            ),
          ),
        ),
      );
  }
  async function publishPosition() {
    const p = geoState.position;
    if (!p || Date.now() - p.timestamp > 120000)
      throw Error("Capture a fresh device location before sharing.");
    await api("location", {
      enabled: true,
      latitude: p.latitude,
      longitude: p.longitude,
      accuracy: p.accuracy,
      captured_at: new Date(p.timestamp).toISOString(),
    });
  }
  function receivePosition(position, center = false) {
    if (!valid()) return;
    geoState.position = {
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy: position.coords.accuracy,
      timestamp: position.timestamp,
    };
    geoState.detectedDistrict =
      geoData?.districts.features.find((f) =>
        pointInGeometry(
          position.coords.latitude,
          position.coords.longitude,
          f.geometry,
        ),
      )?.properties.code || null;
    locate.disabled = false;
    locate.textContent = "Center on my location";
    stop.hidden = false;
    drawSelf(center);
    renderLocation();
  }
  function locationError(error) {
    if (!valid()) return;
    locate.disabled = false;
    locate.textContent = "Use my location";
    notice.textContent =
      error.code === 1
        ? "Location permission was denied. You can still choose a division and district manually."
        : error.code === 2
          ? "The device could not determine a location. Try outdoors or select your district manually."
          : "Location capture timed out. Retry or select your district manually.";
    notice.className = "notice warning";
    if (!geoState.position) geoState.tracking = false;
  }
  function startLocation() {
    if (!window.isSecureContext)
      throw Error(
        "Device location requires HTTPS or localhost. On a phone using a laptop HTTP address, select the district manually or configure trusted HTTPS.",
      );
    if (!navigator.geolocation)
      throw Error(
        "This browser does not provide device location. Select your district manually.",
      );
    if (geoState.position && geoState.tracking) {
      drawSelf(true);
      return;
    }
    locate.disabled = true;
    locate.textContent = "Locating…";
    navigator.geolocation.getCurrentPosition(
      (position) => {
        if (!valid()) return;
        geoState.tracking = true;
        receivePosition(position, true);
        geoState.watch = navigator.geolocation.watchPosition(
          (p) => receivePosition(p),
          locationError,
          { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 },
        );
      },
      locationError,
      { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 },
    );
  }
  function stopLocation() {
    if (geoState.watch !== null && navigator.geolocation)
      navigator.geolocation.clearWatch(geoState.watch);
    geoState.watch = null;
    geoState.tracking = false;
    geoState.position = null;
    geoState.detectedDistrict = null;
    stop.hidden = true;
    locate.textContent = "Use my location";
    drawSelf();
    renderLocation();
    notice.textContent =
      "Local device tracking stopped. Use Stop sharing my pin separately to remove any pin already shared with the server.";
  }
  function toggleStreets() {
    if (!map) return;
    if (streetLayer) {
      map.removeLayer(streetLayer);
      streetLayer = null;
      streets.setAttribute("aria-pressed", "false");
      return;
    }
    if (!navigator.onLine)
      throw Error(
        "Street background needs internet. The bundled boundary map remains available offline.",
      );
    streetLayer = L.tileLayer(
      "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
      },
    );
    let warned = false;
    streetLayer.on("tileerror", () => {
      if (valid() && !warned) {
        warned = true;
        notice.textContent =
          "Street tiles could not load. The bundled Bangladesh boundaries are still available.";
      }
    });
    streetLayer.addTo(map);
    streetLayer.bringToBack();
    streets.setAttribute("aria-pressed", "true");
  }
  async function loadPresence() {
    if (!valid()) return;
    if (state.private && state.online) {
      try {
        if (state.private.user.share_presence) await api("presence", {});
        if (
          state.private.user.share_location &&
          geoState.tracking &&
          geoState.position &&
          Date.now() - geoState.position.timestamp < 120000
        )
          await publishPosition();
        const data = await api("presence");
        if (!valid()) return;
        liveParticipants = data.participants || [];
      } catch (e) {
        liveParticipants = [];
        notice.textContent =
          "Live sharing is unavailable. The map and your private device location can still be used.";
      }
    } else liveParticipants = [];
    if (valid()) {
      drawPeople();
      renderList();
      renderLocation();
    }
  }
  renderLocation();
  renderList();
  (async () => {
    try {
      geoData = await loadBangladesh();
      if (!valid()) return;
      if (!window.L)
        throw Error(
          "Map renderer unavailable. Use the division/district selectors and list.",
        );
      map = L.map(mapElement, {
        zoomControl: true,
        scrollWheelZoom: false,
        zoomAnimation: false,
        fadeAnimation: false,
        markerZoomAnimation: false,
        attributionControl: true,
        maxZoom: 19,
        minZoom: 5,
      });
      geoState.map = map;
      map.attributionControl.addAttribution(
        'Boundaries: <a href="https://www.geoboundaries.org/" target="_blank" rel="noopener">geoBoundaries</a> / BBS / OCHA',
      );
      L.control.scale({ imperial: false }).addTo(map);
      drawAreas(!geoState.view);
      if (geoState.view)
        map.setView(geoState.view.center, geoState.view.zoom, {
          animate: false,
        });
      drawRecords();
      drawExactPlaces();
      drawSelf();
      notice.textContent = state.online
        ? "Bangladesh geographic boundaries loaded. Select an area or use your device location."
        : "Offline public snapshot · bundled geographic boundaries available. Live participant sharing needs the server.";
      await loadPresence();
      if (geoState.tracking && navigator.geolocation) {
        geoState.watch = navigator.geolocation.watchPosition(
          (p) => receivePosition(p),
          locationError,
          { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 },
        );
      }
      geoState.onTheme = () => {
        drawAreas();
        drawRecords();
        drawExactPlaces();
        drawPeople();
        drawSelf();
      };
      document.addEventListener("resilio-theme", geoState.onTheme);
      geoState.timer = setInterval(loadPresence, 15000);
      setTimeout(() => {
        if (valid()) map.invalidateSize();
      }, 100);
    } catch (e) {
      if (valid()) {
        notice.textContent = e.message;
        notice.className = "notice warning";
        renderList();
      }
    }
  })();
}
