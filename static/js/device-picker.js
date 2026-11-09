/* Draft selection only. Permissions, eligibility and saving remain in Django. */
(function (root) {
  "use strict";
  function createSelection(initial = [], limit = 200) {
    let identifiers = [...new Set(initial.map(String))];
    return {
      values: () => identifiers.slice(),
      has: id => identifiers.includes(String(id)),
      remove(id) { identifiers = identifiers.filter(value => value !== String(id)); },
      add(values) {
        const added = [...new Set(values.map(String))].filter(id => !identifiers.includes(id));
        if (identifiers.length + added.length > limit) return {added: [], limitExceeded: true};
        identifiers = [...added.slice().reverse(), ...identifiers];
        return {added, limitExceeded: false};
      }
    };
  }

  function bindPicker(document) {
    const grid = document.getElementById("device-grid");
    if (!grid) return;
    const modal = document.getElementById("device-picker-modal");
    const addButton = document.getElementById("device-add");
    const search = document.getElementById("device-picker-search");
    const code = document.getElementById("device-picker-code");
    const cards = new Map(Array.from(grid.querySelectorAll("[data-device-card]"), card => [card.dataset.deviceId, card]));
    const limit = Number(grid.dataset.limit);
    const selection = createSelection([...cards.keys()], limit);
    const requests = new WeakMap();
    let opened = false, generation = 0;

    function announce(text) {
      document.getElementById("device-selection-status").textContent = text;
      document.getElementById("device-picker-status").textContent = text;
    }
    function update() {
      const text = `${selection.values().length} / ${limit} equipos seleccionados`;
      document.getElementById("device-selection-count").textContent = text;
      document.getElementById("device-picker-count").textContent = text;
      modal.querySelectorAll("[data-picker-device]").forEach(checkbox => {
        checkbox.checked = selection.has(checkbox.value);
      });
    }
    function remove(id) {
      selection.remove(id);
      cards.get(id)?.remove();
      cards.delete(id);
      update();
      announce("Equipo quitado de la selección. El mantenimiento aún no se ha guardado.");
    }
    function addTemplates(templates) {
      const available = new Map(Array.from(templates, item => [item.dataset.pickerCard, item]));
      const result = selection.add([...available.keys()]);
      if (result.limitExceeded) {
        announce(`La selección supera ${limit} equipos. No se agregó ninguno de este grupo; acota el filtro o quita equipos.`);
      } else {
        result.added.forEach(id => {
          const card = available.get(id).content.firstElementChild.cloneNode(true);
          card.querySelector('input[type="hidden"]').name = grid.dataset.fieldName;
          cards.set(id, card);
          addButton.after(card);
        });
        const label = result.added.length === 1 ? cards.get(result.added[0]).dataset.deviceLabel : "";
        announce(result.added.length
          ? `${result.added.length} equipo${result.added.length === 1 ? "" : "s"} agregado${result.added.length === 1 ? "" : "s"}${label ? ": " + label : ""}. Guarda el mantenimiento para confirmar.`
          : "Los equipos ya estaban agregados. No se duplicaron.");
      }
      update();
    }
    grid.addEventListener("click", event => {
      const button = event.target.closest("[data-remove-device]");
      if (!button) return;
      event.preventDefault();
      remove(button.value);
      addButton.focus();
    });
    modal.addEventListener("change", event => {
      const checkbox = event.target.closest("[data-picker-device]");
      if (!checkbox) return;
      if (checkbox.checked) {
        addTemplates(Array.from(modal.querySelectorAll("template[data-picker-card]"))
          .filter(item => item.dataset.pickerCard === checkbox.value));
      } else remove(checkbox.value);
    });
    modal.addEventListener("show.bs.modal", () => { opened = true; generation++; });
    modal.addEventListener("shown.bs.modal", () => {
      document.getElementById("picker-search").focus();
      search.requestSubmit();
    });
    modal.addEventListener("hide.bs.modal", () => {
      opened = false;
      generation++;
      modal.querySelectorAll("[hx-get]").forEach(element => root.htmx?.trigger(element, "htmx:abort"));
    });
    modal.addEventListener("htmx:beforeRequest", event => { requests.set(event.detail.xhr, generation); });
    modal.addEventListener("htmx:beforeSwap", event => {
      if (!opened || requests.get(event.detail.xhr) !== generation) event.detail.shouldSwap = false;
    });
    modal.addEventListener("htmx:afterSwap", event => {
      if (!opened) return;
      const target = event.detail.target;
      if (target.id === "device-picker-scan-result" || target.id === "device-picker-bulk-result") {
        const result = target.querySelector("[data-picker-selection]");
        if (result) {
          addTemplates(result.querySelectorAll("template[data-picker-card]"));
          result.remove();
        }
      }
      update();
    });
    const scanner = root.BitacoraScanner.bind({
      modal,
      camera: document.getElementById("picker-camera-reader"),
      fileReader: document.getElementById("picker-file-reader"),
      fileInput: document.getElementById("picker-qr-file"),
      startButton: document.getElementById("picker-camera-start"),
      stopButton: document.getElementById("picker-camera-stop"),
      status: text => { document.getElementById("picker-camera-status").textContent = text; },
      onResult(text) {
        if (!opened) return;
        code.elements.query.value = text;
        code.requestSubmit();
      }
    });
    code.addEventListener("submit", scanner.stop);
    document.getElementById("maintenance-form").addEventListener("submit", scanner.stop);
    const qrOptions = document.getElementById("picker-qr-options");
    qrOptions.addEventListener("toggle", () => { if (!qrOptions.open) scanner.stop(); });
    update();
    return {selection};
  }
  if (typeof module !== "undefined" && module.exports) module.exports = {createSelection, bindPicker};
  else {
    root.BitacoraDevicePicker = {createSelection, bindPicker};
    bindPicker(root.document);
  }
})(typeof window === "undefined" ? globalThis : window);
