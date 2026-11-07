/* Runs before CSS to prevent a theme flash. Storage failure is nonfatal. */
(() => {
  const media = matchMedia("(prefers-color-scheme: dark)");
  let manual = null;
  try {
    manual = localStorage.getItem("resilio-theme");
  } catch (e) {}
  if (!["dark", "light"].includes(manual)) manual = null;
  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    document.dispatchEvent(new CustomEvent("resilio-theme", { detail: theme }));
    document.querySelectorAll("[data-theme-toggle]").forEach((b) => {
      b.textContent = theme === "dark" ? "☀ Light mode" : "☾ Dark mode";
      b.setAttribute("aria-label", `Current theme: ${theme}. Switch theme`);
      b.setAttribute("aria-pressed", String(theme === "dark"));
    });
  }
  apply(manual || (media.matches ? "dark" : "light"));
  media.addEventListener("change", () => {
    if (!manual) apply(media.matches ? "dark" : "light");
  });
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-theme-toggle]")) {
      manual =
        document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      try {
        localStorage.setItem("resilio-theme", manual);
      } catch (e) {}
      apply(manual);
    }
    if (e.target.closest("[data-theme-system]")) {
      manual = null;
      try {
        localStorage.removeItem("resilio-theme");
      } catch (e) {}
      apply(media.matches ? "dark" : "light");
    }
  });
  document.addEventListener("DOMContentLoaded", () =>
    apply(document.documentElement.dataset.theme),
  );
})();
