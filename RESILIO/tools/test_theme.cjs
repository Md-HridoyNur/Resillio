/* Optional developer check; Node is NOT a runtime dependency of RESILIO. */
const fs = require("node:fs"),
  vm = require("node:vm"),
  assert = require("node:assert/strict");
const code = fs.readFileSync(
  require("node:path").join(__dirname, "../static/resilio/theme.js"),
  "utf8",
);
function env(saved, systemDark, storageBlocked = false) {
  const listeners = {},
    mediaListeners = {};
  let stored = saved;
  const toggle = {
    textContent: "",
    attrs: {},
    setAttribute(k, v) {
      this.attrs[k] = v;
    },
  };
  const media = {
    matches: systemDark,
    addEventListener(name, fn) {
      mediaListeners[name] = fn;
    },
  };
  const document = {
    documentElement: { dataset: {} },
    addEventListener(n, fn) {
      listeners[n] = fn;
    },
    dispatchEvent() {},
    querySelectorAll() {
      return [toggle];
    },
  };
  const sandbox = {
    document,
    matchMedia: () => media,
    localStorage: {
      getItem() {
        if (storageBlocked) throw Error("blocked");
        return stored;
      },
      setItem(k, v) {
        if (storageBlocked) throw Error("blocked");
        stored = v;
      },
      removeItem() {
        if (storageBlocked) throw Error("blocked");
        stored = null;
      },
    },
    CustomEvent: class {
      constructor(type, data) {
        this.type = type;
        this.detail = data.detail;
      }
    },
  };
  vm.runInNewContext(code, sandbox);
  listeners.DOMContentLoaded();
  return {
    document,
    toggle,
    stored: () => stored,
    click(selector) {
      listeners.click({ target: { closest: (s) => s === selector } });
    },
    system(dark) {
      media.matches = dark;
      mediaListeners.change();
    },
  };
}
let checks = 0;
function test(name, fn) {
  fn();
  checks++;
  console.log("PASS", name);
}
test("first visit follows light system preference", () =>
  assert.equal(
    env(null, false).document.documentElement.dataset.theme,
    "light",
  ));
test("first visit follows dark system preference", () =>
  assert.equal(env(null, true).document.documentElement.dataset.theme, "dark"));
test("system changes apply without manual preference", () => {
  const e = env(null, false);
  e.system(true);
  assert.equal(e.document.documentElement.dataset.theme, "dark");
});
test("manual selection persists and survives reload", () => {
  const e = env(null, false);
  e.click("[data-theme-toggle]");
  assert.equal(e.stored(), "dark");
  assert.equal(
    env(e.stored(), false).document.documentElement.dataset.theme,
    "dark",
  );
});
test("system changes cannot override manual preference", () => {
  const e = env("light", true);
  e.system(true);
  assert.equal(e.document.documentElement.dataset.theme, "light");
});
test("reset to device preference resumes system tracking", () => {
  const e = env("light", true);
  e.click("[data-theme-system]");
  assert.equal(e.stored(), null);
  assert.equal(e.document.documentElement.dataset.theme, "dark");
  e.system(false);
  assert.equal(e.document.documentElement.dataset.theme, "light");
});
test("storage blocked still permits session switching", () => {
  const e = env(null, false, true);
  e.click("[data-theme-toggle]");
  assert.equal(e.document.documentElement.dataset.theme, "dark");
  e.system(false);
  assert.equal(e.document.documentElement.dataset.theme, "dark");
});
test("invalid saved theme falls back to system", () =>
  assert.equal(
    env("invalid", true).document.documentElement.dataset.theme,
    "dark",
  ));
test("accessible current state and label update", () => {
  const e = env("dark", false);
  assert.equal(e.toggle.attrs["aria-pressed"], "true");
  assert.match(e.toggle.attrs["aria-label"], /Current theme: dark/);
  e.click("[data-theme-toggle]");
  assert.equal(e.toggle.attrs["aria-pressed"], "false");
});
console.log(`${checks} theme behavior checks passed.`);
