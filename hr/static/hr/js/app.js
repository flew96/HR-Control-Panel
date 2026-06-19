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
