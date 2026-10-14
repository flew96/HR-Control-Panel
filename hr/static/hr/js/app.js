const applyTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    const label = document.querySelector("[data-theme-label]");
    const toggle = document.querySelector("[data-theme-toggle]");
    if (label) {
        label.textContent = theme === "dark" ? "Светлая" : "Тёмная";
    }
    if (toggle) {
        toggle.setAttribute(
            "aria-label",
            theme === "dark" ? "Включить светлую тему" : "Включить тёмную тему",
        );
    }
};

applyTheme(document.documentElement.dataset.theme || "light");

document.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-theme-toggle]");
    if (!toggle) {
        return;
    }
    const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    try { localStorage.setItem("hr-theme", theme); } catch {}
    applyTheme(theme);
});

document.addEventListener("change", (event) => {
    const target = event.target;
    if (!target.matches("[data-select-all]")) {
        return;
    }

    const group = target.getAttribute("data-select-all");
    document
        .querySelectorAll(`[data-checkbox-group="${group}"]`)
        .forEach((checkbox) => {
            checkbox.checked = target.checked;
        });
});

document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-tab-target]");
    if (!button) {
        return;
    }

    const tabs = button.closest("[data-tabs]");
    if (!tabs) {
        return;
    }

    const target = button.getAttribute("data-tab-target");
    document.querySelectorAll("[data-tab-target]").forEach((item) => {
        item.classList.toggle("active", item === button);
    });
    document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
        panel.classList.toggle("active", panel.getAttribute("data-tab-panel") === target);
    });
});
