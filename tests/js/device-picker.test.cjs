"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const {createSelection} = require("../../static/js/device-picker.js");
const source = fs.readFileSync(require.resolve("../../static/js/device-picker.js"), "utf8");

test("new selections prepend without moving the add tile or duplicating previous devices", () => {
  const selection = createSelection(["1", "2"]);
  selection.add(["3", "4"]);
  assert.deepEqual(selection.values(), ["4", "3", "1", "2"]);
  assert.deepEqual(selection.add(["1", "3", "1"]).added, []);
  assert.deepEqual(selection.values(), ["4", "3", "1", "2"]);
  selection.remove("3");
  selection.add(["3"]);
  assert.deepEqual(selection.values(), ["3", "4", "1", "2"]);
});

test("bulk addition counts unique new devices and rejects an overflowing group atomically", () => {
  const selection = createSelection(["1"], 3);
  assert.equal(selection.add(["1", "2", "3", "4"]).limitExceeded, true);
  assert.deepEqual(selection.values(), ["1"]);
  assert.equal(selection.add(["1", "2", "2", "3"]).limitExceeded, false);
  assert.deepEqual(selection.values(), ["3", "2", "1"]);
});

// Minimal DOM test double for event/state integration, not a visual browser test.
class Element {
  constructor(id = "", dataset = {}) {
    Object.assign(this, {id, dataset, children: [], parent: null, listeners: {}, value: "", textContent: ""});
  }
  append(...children) { children.forEach(child => { child.parent = this; this.children.push(child); }); }
  matches(selector) {
    return {
      "[data-device-card]": () => this.dataset.deviceCard !== undefined,
      "[data-picker-device]": () => this.dataset.pickerDevice !== undefined,
      "template[data-picker-card]": () => this.dataset.pickerCard !== undefined,
      "[data-remove-device]": () => this.dataset.removeDevice !== undefined,
      "[data-picker-selection]": () => this.dataset.pickerSelection !== undefined,
      "[hx-get]": () => this.dataset.request !== undefined,
      'input[type="hidden"]': () => this.type === "hidden"
    }[selector]();
  }
  closest(selector) { return this.matches(selector) ? this : this.parent?.closest(selector); }
  querySelectorAll(selector) {
    return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0]; }
  addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
  fire(type, event = {}) {
    const detail = {target: this, preventDefault() { this.prevented = true; }, ...event};
    (this.listeners[type] || []).forEach(listener => listener(detail));
    return detail;
  }
  after(child) {
    child.parent = this.parent;
    this.parent.children.splice(this.parent.children.indexOf(this) + 1, 0, child);
  }
  remove() { this.parent.children = this.parent.children.filter(child => child !== this); }
  focus() { this.focused = true; }
  requestSubmit() { this.submissions = (this.submissions || 0) + 1; }
  cloneNode() {
    const copy = Object.assign(new Element(this.id, {...this.dataset}), {type: this.type, name: this.name, value: this.value});
    copy.append(...this.children.map(child => child.cloneNode()));
    return copy;
  }
}
function deviceCard(id) {
  const card = new Element("", {deviceCard: "", deviceId: id});
  const input = Object.assign(new Element(), {type: "hidden", name: "devices", value: id});
  const button = Object.assign(new Element("", {removeDevice: ""}), {value: id});
  card.append(input, button);
  return card;
}
function cardTemplate(id) {
  const template = new Element("", {pickerCard: id});
  template.content = {firstElementChild: deviceCard(id)};
  return template;
}
function fixture(initial = [], limit = 200) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, new Element(id));
    return elements.get(id);
  };
  const modal = element("device-picker-modal"), grid = element("device-grid");
  grid.dataset = {fieldName: "devices", limit: String(limit)};
  grid.append(element("device-add"), ...initial.map(deviceCard));
  ["device-picker-search", "device-picker-code", "device-picker-results", "device-picker-scan-result", "device-picker-bulk-result"].forEach(id => {
    modal.append(element(id));
  });
  element("device-picker-code").elements = {query: {value: ""}};
  let scanner, stops = 0;
  const context = {module: {exports: {}}, window: {
    BitacoraScanner: {bind(config) { scanner = config; return {stop() { stops++; }}; }},
    htmx: {trigger() {}}
  }};
  vm.runInNewContext(source, context);
  const bound = context.module.exports.bindPicker({getElementById: element});
  function candidate(id) {
    const checkbox = Object.assign(new Element("", {pickerDevice: ""}), {value: id});
    element("device-picker-results").append(checkbox, cardTemplate(id));
    return checkbox;
  }
  function swap(ids, targetId = "device-picker-bulk-result") {
    const target = element(targetId), result = new Element("", {pickerSelection: ""});
    target.children = [];
    result.append(...ids.map(cardTemplate));
    target.append(result);
    modal.fire("htmx:afterSwap", {detail: {target}});
  }
  return {element, modal, grid, bound, candidate, swap, scanner: () => scanner, stops: () => stops,
    ids: () => grid.children.filter(child => child.dataset.deviceId).map(child => child.dataset.deviceId)};
}

test("checkbox selections keep add first, newest cards next, and hidden form inputs in sync", () => {
  const f = fixture();
  f.modal.fire("show.bs.modal");
  for (const id of ["1", "2"]) {
    const checkbox = f.candidate(id);
    checkbox.checked = true;
    f.modal.fire("change", {target: checkbox});
  }
  assert.equal(f.grid.children[0].id, "device-add");
  assert.deepEqual(f.ids(), ["2", "1"]);
  assert.deepEqual(f.grid.querySelectorAll('input[type="hidden"]').map(input => input.value), ["2", "1"]);
  assert.match(f.element("device-picker-count").textContent, /2 \/ 200/);
});

test("search page changes reflect existing selections instead of clearing them", () => {
  const f = fixture(["1"]);
  f.modal.fire("show.bs.modal");
  const checkbox = f.candidate("1");
  f.modal.fire("htmx:afterSwap", {detail: {target: f.element("device-picker-results")}});
  assert.equal(checkbox.checked, true);
  assert.deepEqual(f.ids(), ["1"]);
  checkbox.checked = false;
  f.modal.fire("change", {target: checkbox});
  assert.deepEqual(f.ids(), []);
});

test("removing a grid card prevents form submission, updates modal and restores focus", () => {
  const f = fixture(["1"]), checkbox = f.candidate("1");
  const button = f.grid.children[1].children[1];
  const event = f.grid.fire("click", {target: button});
  assert.equal(event.prevented, true);
  assert.equal(checkbox.checked, false);
  assert.deepEqual(f.ids(), []);
  assert.equal(f.element("device-add").focused, true);
});

test("camera/manual scan responses add directly to draft and duplicate scans do not reorder", () => {
  const f = fixture();
  f.modal.fire("show.bs.modal");
  f.scanner().onResult("https://bitacora.example.edu/dispositivos/opaque/");
  assert.equal(f.element("device-picker-code").elements.query.value, "https://bitacora.example.edu/dispositivos/opaque/");
  assert.equal(f.element("device-picker-code").submissions, 1);
  f.swap(["1"], "device-picker-scan-result");
  f.swap(["2"], "device-picker-scan-result");
  f.swap(["1"], "device-picker-scan-result");
  assert.deepEqual(f.ids(), ["2", "1"]);
  assert.match(f.element("device-picker-status").textContent, /ya estaban/);
});

test("an overflowing bulk response changes neither cards nor hidden submitted devices", () => {
  const f = fixture(["1"], 2);
  f.modal.fire("show.bs.modal");
  f.swap(["2", "3"]);
  assert.deepEqual(f.ids(), ["1"]);
  assert.match(f.element("device-picker-status").textContent, /No se agregó ninguno/);
  f.swap(["1", "2"]);
  assert.deepEqual(f.ids(), ["2", "1"]);
});

test("closed or reopened modal discards delayed responses from the previous opening", () => {
  const f = fixture(), xhr = {};
  f.modal.fire("show.bs.modal");
  f.modal.fire("htmx:beforeRequest", {detail: {xhr}});
  f.modal.fire("hide.bs.modal");
  const detail = {xhr, shouldSwap: true};
  f.modal.fire("htmx:beforeSwap", {detail});
  assert.equal(detail.shouldSwap, false);
  f.swap(["1"]);
  assert.deepEqual(f.ids(), []);
  f.scanner().onResult("late-qr");
  assert.equal(f.element("device-picker-code").submissions, undefined);
  f.modal.fire("show.bs.modal");
  detail.shouldSwap = true;
  f.modal.fire("htmx:beforeSwap", {detail});
  assert.equal(detail.shouldSwap, false);
});

test("closing QR details and submitting the main form stop the scanner", () => {
  const f = fixture();
  f.element("picker-qr-options").open = false;
  f.element("picker-qr-options").fire("toggle");
  f.element("maintenance-form").fire("submit");
  assert.equal(f.stops(), 2);
});
