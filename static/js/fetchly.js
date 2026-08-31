(() => {
  const root = document.documentElement;
  const themes = ["system", "light", "dark"];
  root.dataset.theme = localStorage.getItem("fetchly-theme") || "system";

  document.addEventListener("click", async (event) => {
    const themeButton = event.target.closest("[data-theme-toggle]");
    if (themeButton) {
      const next = themes[(themes.indexOf(root.dataset.theme) + 1) % themes.length];
      root.dataset.theme = next;
      localStorage.setItem("fetchly-theme", next);
      themeButton.setAttribute("aria-label", `Tema: ${next}. Ganti tema`);
      return;
    }

    if (event.target.closest("[data-paste]")) {
      const input = document.querySelector("#media-url");
      try {
        input.value = await navigator.clipboard.readText();
        input.dispatchEvent(new Event("input", { bubbles: true }));
      } catch {
        input.focus();
      }
    }
  });

  document.body.addEventListener("htmx:afterSwap", (event) => {
    event.detail.target.querySelector("h2, [role='status'], [role='alert']")?.focus?.();
  });

  if (document.body.dataset.hasIdentity === "false" && crypto.subtle) {
    const material = [navigator.userAgent, navigator.language, navigator.hardwareConcurrency,
      Intl.DateTimeFormat().resolvedOptions().timeZone].join("|");
    crypto.subtle.digest("SHA-256", new TextEncoder().encode(material)).then((digest) => {
      const fingerprint = [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
      const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
      return fetch("/identity", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": csrf },
        body: new URLSearchParams({ fingerprint }),
      });
    });
  }
})();
