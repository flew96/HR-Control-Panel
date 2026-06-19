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
