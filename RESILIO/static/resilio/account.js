/* Progressive enhancement: account forms work without JavaScript. */
document.querySelectorAll("input[type=password]").forEach((input) => {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "password-toggle";
  button.textContent = "Show password";
  button.setAttribute("aria-controls", input.id);
  button.setAttribute("aria-pressed", "false");
  button.addEventListener("click", () => {
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    button.textContent = show ? "Hide password" : "Show password";
    button.setAttribute("aria-pressed", String(show));
  });
  input.insertAdjacentElement("afterend", button);
});
const role = document.querySelector("[name=role]"),
  org = document.querySelector("[name=organization]");
if (role && org) {
  const hint = () => {
    org.required = role.value === "coordinator";
    org.closest("p").classList.toggle("organization-required", org.required);
  };
  role.addEventListener("change", hint);
  hint();
}
