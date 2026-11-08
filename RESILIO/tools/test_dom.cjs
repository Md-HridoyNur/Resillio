/* Optional developer DOM checks, not a visual browser or service-worker test.
   npm install --prefix tools jsdom fake-indexeddb; node tools/test_dom.cjs */
const { JSDOM } = require("jsdom");
const { IDBFactory } = require("fake-indexeddb");
const assert = require("node:assert/strict"),
  fs = require("node:fs"),
  path = require("node:path");
const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "templates/app.html"), "utf8");
const dom = new JSDOM(html, {
  url: "http://localhost/",
  runScripts: "outside-only",
  pretendToBeVisual: true,
});
const w = dom.window,
  d = w.document;
w.indexedDB = new IDBFactory();
w.matchMedia = () => ({ matches: false, addEventListener() {} });
w.setInterval = () => 0;
w.HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
w.HTMLDialogElement.prototype.close = function () {
  this.open = false;
};
const now = new Date().toISOString(),
  calls = [];
let reachable = true,
  nextId = 100,
  privateUser = {
    id: 7,
    username: "volunteer",
    name: "Test",
    email: "",
    area: "mirpur",
    role: "volunteer",
    admin: true,
  };
const pub = {
  items: [
    { id: 1, name: "Drinking water", unit: "L", category: "water" },
    { id: 2, name: "Purification tablets", unit: "tablets", category: "water" },
    { id: 3, name: "Food rations", unit: "packs", category: "food" },
    { id: 4, name: "Blankets", unit: "pieces", category: "shelter" },
    { id: 5, name: "First aid kits", unit: "kits", category: "medical" },
  ],
  offers: [
    {
      id: 1,
      kind: "offer",
      item: 1,
      name: "Drinking water",
      unit: "L",
      category: "water",
      quantity: "50",
      available: "50",
      status: "open",
      area: "mirpur",
      description: "<img src=x onerror=alert(1)>",
      created_at: now,
      updated_at: now,
      demo: true,
    },
  ],
  requests: [
    {
      id: 2,
      kind: "request",
      item: 1,
      name: "Drinking water",
      unit: "L",
      category: "water",
      quantity: "20",
      remaining: "20",
      unallocated: "20",
      status: "open",
      area: "mirpur",
      description: "Water needed",
      urgency: "urgent",
      created_at: now,
      updated_at: now,
    },
  ],
  stats: { offers: 1, requests: 1, urgent: 1, deliveries: 0 },
  analytics: [
    {
      name: "Drinking water",
      unit: "L",
      area: "mirpur",
      available: 50,
      needed: 20,
      unallocated: 20,
    },
  ],
  shelters: [
    {
      id: 1,
      name: "Test Hall",
      area: "mirpur",
      available: 70,
      occupied: 20,
      reserved: 10,
      total: 100,
      description: "Test",
    },
  ],
  synced_at: now,
};
const priv = () => ({
  user: privateUser,
  owned_offers: [1],
  owned_requests: [2],
  assignments: [],
  notifications: [
    {
      id: 9,
      text: "Assigned <script>unsafe</script>",
      read: false,
      created_at: now,
    },
  ],
  reports: [],
  audit: [],
});
const dedup = new Map();
w.fetch = async (url, options = {}) => {
  if (!reachable) throw Error("offline");
  const key = new URL(url, w.location.href);
  let value = {},
    status = 200;
  const payload = options.body ? JSON.parse(options.body) : null;
  calls.push({ url: key.pathname, query: key.search, payload });
  if (key.pathname === "/api/public/") value = pub;
  else if (key.pathname === "/api/me/") value = priv();
  else if (key.pathname === "/api/matches/")
    value = {
      matches: [
        {
          ...pub.offers[0],
          max_quantity: "20",
          reasons: ["Same area", "Can fully cover unallocated need"],
        },
      ],
    };
  else if (key.pathname === "/api/resource/") {
    if (payload.account_id && payload.account_id !== privateUser.id) {
      status = 403;
      value = { error: "Wrong account" };
    } else {
      const id = payload.client_id
        ? dedup.get(payload.client_id) || nextId++
        : nextId++;
      if (payload.client_id) dedup.set(payload.client_id, id);
      value = { ok: true, id };
    }
  } else value = { ok: true, id: 1 };
  return {
    ok: status === 200,
    status,
    json: async () => JSON.parse(JSON.stringify(value)),
  };
};
w.eval(fs.readFileSync(path.join(root, "static/resilio/theme.js"), "utf8"));
for (const file of [
  "localareas.js",
  "geography.js",
  "network.js",
  "fieldops.js",
  "app.js",
])
  require("node:vm").runInContext(
    fs.readFileSync(path.join(root, "static/resilio", file), "utf8"),
    dom.getInternalVMContext(),
  );
const wait = async (fn) => {
  for (let i = 0; i < 100; i++) {
    if (fn()) return;
    await new Promise((r) => setTimeout(r, 10));
  }
  throw Error("Timed out waiting for DOM");
};
const clickText = (text, selector = "button") => {
  const b = [...d.querySelectorAll(selector)].find(
    (n) => n.textContent === text,
  );
  assert.ok(b, "Missing " + text);
  b.click();
  return b;
};
let checks = 0;
const pass = (name) => {
  checks++;
  console.log("PASS", name);
};
(async () => {
  await wait(() => d.querySelectorAll(".resource-card").length === 2);
  assert.match(d.querySelector("#account").textContent, /volunteer/);
  pass("overview renders fetched records and authenticated navigation");
  assert.equal(
    d.querySelectorAll(".resource-card img,.resource-card script").length,
    0,
  );
  assert.match(d.querySelector(".resource-grid").textContent, /<img/);
  pass("untrusted descriptions render as text, not HTML");
  const search = [...d.querySelectorAll(".filter-bar input")][0];
  search.value = "not-found";
  search.dispatchEvent(new w.Event("input"));
  assert.equal(d.querySelectorAll(".resource-card").length, 0);
  search.value = "";
  search.dispatchEvent(new w.Event("input"));
  pass("search changes the board through DOM events");
  clickText("+ Request assistance");
  assert.ok(d.querySelector("#editor").open);
  const form = d.querySelector("#resourceForm");
  form.elements.namedItem("quantity").value = "2";
  form.elements.namedItem("area").value = "Mirpur";
  form.elements.namedItem("district").value = "dhaka";
  form.elements.namedItem("district").dispatchEvent(new w.Event("change"));
  form.dispatchEvent(
    new w.SubmitEvent("submit", { bubbles: true, cancelable: true }),
  );
  await wait(() => !d.querySelector("#editor").open);
  const saved = calls.find((c) => c.url === "/api/resource/");
  assert.equal(saved.payload.item, "1");
  assert.equal(saved.payload.kind, "request");
  assert.equal(saved.payload.account_id, 7);
  assert.match(saved.payload.client_id, /^[0-9a-f-]{36}$/);
  pass(
    "request dialog submits canonical fields, account ID and stable identifier",
  );
  clickText("Offer supplies");
  assert.ok(d.querySelector("#urgencyLabel").hidden);
  assert.ok(!d.querySelector("#expiryLabel").hidden);
  assert.ok(d.querySelector("#saveLocal").hidden);
  d.querySelector("[data-close=editor]").click();
  pass("offer form exposes expiry and disables offline offer creation");
  d.querySelector("#crisisToggle").click();
  assert.equal(d.querySelectorAll(".crisis-action").length, 4);
  clickText("Water / L");
  assert.ok(!d.querySelector("#crisis").open);
  assert.ok(d.querySelector("#editor").open);
  assert.equal(form.elements.namedItem("urgency").value, "urgent");
  assert.equal(form.elements.namedItem("item").value, "1");
  d.querySelector("[data-close=editor]").click();
  pass(
    "crisis category opens prefilled urgent request without stacking dialogs",
  );
  clickText("View compatible offers");
  await wait(() =>
    d.querySelector("#actionForm").textContent.includes("Same area"),
  );
  assert.match(d.querySelector("#actionForm").textContent, /maximum 20/);
  d.querySelector("[data-close=actionDialog]").click();
  pass("compatible offer panel renders explanations and quantity bounds");
  for (const screen of [
    "activity",
    "volunteer",
    "shelters",
    "notifications",
    "administration",
    "profile",
  ]) {
    w.location.hash = screen;
    await new Promise((r) => setTimeout(r, 20));
    assert.ok(d.querySelector("#screen h1"));
    assert.ok(d.querySelector("#screen").textContent.length > 30);
  }
  pass("all authenticated operation screens render");
  w.location.hash = "overview";
  await wait(() => d.querySelectorAll(".resource-card").length === 2);
  reachable = false;
  clickText("+ Request assistance");
  form.elements.namedItem("quantity").value = "3";
  form.elements.namedItem("area").value = "uttara";
  form.elements.namedItem("district").value = "dhaka";
  form.elements.namedItem("district").dispatchEvent(new w.Event("change"));
  clickText("Save request on device");
  await wait(() => !d.querySelector("#editor").open);
  w.location.hash = "sync";
  await wait(() =>
    d.querySelector("#screen").textContent.includes("Pending sync"),
  );
  pass("offline request is persisted in IndexedDB and shown as pending");
  reachable = true;
  clickText("Retry synchronization");
  await wait(() =>
    d.querySelector("#screen").textContent.includes("Confirmed server request"),
  );
  const before = dedup.size;
  clickText("Verify same server ID");
  await new Promise((r) => setTimeout(r, 40));
  assert.equal(dedup.size, before);
  pass("sync retry reuses the stable ID and displays server confirmation");
  const countBefore = calls.filter((c) => c.url === "/api/resource/").length;
  privateUser = { ...privateUser, id: 8 };
  clickText("Verify same server ID");
  await new Promise((r) => setTimeout(r, 40));
  assert.equal(
    calls.filter((c) => c.url === "/api/resource/").length,
    countBefore,
  );
  assert.match(d.querySelector("#status").textContent, /account/);
  pass("wrong-account synchronization stops before resource submission");
  assert.equal(d.querySelectorAll("dialog[open]").length, 0);
  pass("closed dialogs are removed from active dialog state");
  console.log(
    `${checks} DOM behavior checks passed. Native layout, focus and service-worker APIs require a real browser.`,
  );
  w.close();
})().catch((error) => {
  console.error(error);
  w.close();
  process.exitCode = 1;
});
