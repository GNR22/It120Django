/*
 * Dark/Light theme toggle with localStorage persistence.
 * Defaults to dark mode when no preference has been saved yet.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "sms-theme";
  var root = document.documentElement;
  var toggleBtn = document.getElementById("theme-toggle");
  if (!toggleBtn) { return; }

  var label = toggleBtn.querySelector(".theme-toggle-label");

  function applyTheme(theme) {
    var normalized = theme === "light" ? "light" : "dark";
    root.setAttribute("data-theme", normalized);

    var isLight = normalized === "light";
    toggleBtn.setAttribute("aria-pressed", String(isLight));
    toggleBtn.setAttribute(
      "aria-label",
      isLight ? "Switch to dark mode" : "Switch to light mode"
    );
    if (label) {
      label.textContent = isLight ? "Dark" : "Light";
    }
  }

  function getCurrentTheme() {
    return root.getAttribute("data-theme") === "light" ? "light" : "dark";
  }

  toggleBtn.addEventListener("click", function () {
    var next = getCurrentTheme() === "dark" ? "light" : "dark";
    applyTheme(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (e) {}
  });

  applyTheme(getCurrentTheme());
})();

