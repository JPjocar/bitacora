"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const source = fs.readFileSync(require.resolve("../../static/js/scanner.js"), "utf8");
function fixture({secure = true, library = true} = {}) {
  const events = new Map(), calls = [], elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      textContent: "", value: "", elements: {query: {value: ""}},
      addEventListener: (event, action) => events.set(`${id}:${event}`, action),
      requestSubmit: () => calls.push("submit"), querySelectorAll: () => []
    });
    return elements.get(id);
  };
  let options;
  const context = {
    window: {
      isSecureContext: secure, Html5Qrcode: library ? function () {} : null,
      BitacoraQR: {createController(config) {
        options = config;
        return {
          start: () => calls.push("start"), stop: () => calls.push("stop"),
          file: file => calls.push(file)
        };
      }},
      addEventListener: (event, action) => events.set(`window:${event}`, action)
    },
    navigator: {mediaDevices: {getUserMedia() {}}},
    document: {
      hidden: false, getElementById: element,
      addEventListener: (event, action) => events.set(`document:${event}`, action)
    },
    bootstrap: {Modal: {getInstance: () => ({hide: () => calls.push("hide")})}}
  };
  vm.runInNewContext(source, context);
  return {context, options, calls, element, fire: (event, arg) => events.get(event)(arg)};
}
test("insecure connection keeps manual entry and blocks camera start", () => {
  const f = fixture({secure: false});
  f.fire("camera-modal:shown.bs.modal");
  assert.deepEqual(f.calls, []);
  assert.match(f.element("scan-status").textContent, /HTTPS/);
});
test("missing library leaves a manual fallback message", () => {
  const f = fixture({library: false});
  assert.match(f.element("scan-status").textContent, /manualmente/);
  assert.deepEqual(f.calls, []);
});
test("modal closing, backgrounding and page exit stop the camera", () => {
  const f = fixture();
  f.fire("camera-modal:shown.bs.modal");
  f.fire("camera-modal:hide.bs.modal");
  f.fire("window:pagehide");
  f.context.document.hidden = true;
  f.fire("document:visibilitychange");
  assert.deepEqual(f.calls, ["start", "stop", "stop", "stop", "hide"]);
});
test("decoded external text is sent to server validation without client navigation", () => {
  const f = fixture();
  const untrusted = "https://evil.example/<script>";
  f.options.onResult(untrusted);
  assert.equal(f.element("scan-form").elements.query.value, untrusted);
  assert.deepEqual(f.calls, ["submit"]);
  assert.equal(f.context.window.location, undefined);
});
test("wrong file type and oversized file never reach decoder", () => {
  const f = fixture();
  for (const file of [{type: "text/html", size: 100}, {type: "image/png", size: 10485761}]) {
    f.fire("qr-file:change", {target: {files: [file], value: "image"}});
    assert.match(f.element("scan-status").textContent, /hasta 10 MB/);
  }
  assert.deepEqual(f.calls, ["stop", "stop"]);
});
test("image file is decoded locally and input is reset for retry", () => {
  const f = fixture();
  const file = {type: "image/png", size: 100};
  const target = {files: [file], value: "image"};
  f.fire("qr-file:change", {target});
  assert.deepEqual(f.calls, [file]);
  assert.equal(target.value, "");
});
test("permission, absent camera and occupied camera have distinct Spanish messages", () => {
  const f = fixture();
  for (const [name, message] of [["NotAllowedError", /denegado/], ["NotFoundError", /No se encontró/], ["NotReadableError", /ocupada/]]) {
    f.options.onError({name});
    assert.match(f.element("scan-status").textContent, message);
    assert.equal(f.element("scan-status").textContent, f.element("camera-status").textContent);
  }
});
test("fallback cleanup stops every video media track", () => {
  const f = fixture();
  let stopped = 0;
  f.element("camera-modal").querySelectorAll = () => [{srcObject: {getTracks: () => [
    {stop: () => stopped++}, {stop: () => stopped++}
  ]}}];
  f.options.releaseMedia();
  assert.equal(stopped, 2);
});
