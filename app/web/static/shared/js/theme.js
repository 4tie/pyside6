/* Theme Management */

export function toggleTheme() {
  const root = document.documentElement;
  const current = root.dataset.theme || "dark";
  const next = current === "dark" ? "light" : "dark";
  root.dataset.theme = next;
  localStorage.setItem("theme", next);
  return next;
}

export function initTheme() {
  const saved = localStorage.getItem("theme") || "dark";
  document.documentElement.dataset.theme = saved;
  return saved;
}

export function getTheme() {
  return document.documentElement.dataset.theme || "dark";
}
