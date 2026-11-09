export function focusComposer() {
  document.getElementById("new-project")?.scrollIntoView({ behavior: "smooth", block: "center" });
  window.setTimeout(
    () => document.getElementById("clip-instructions")?.focus({ preventScroll: true }),
    350,
  );
}
