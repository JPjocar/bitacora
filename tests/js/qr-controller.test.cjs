"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {createController} = require("../../static/js/qr-controller.js");
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
function fixture(overrides = {}) {
  const log = [], results = [], errors = [], readers = [];
  const controller = createController({
    makeReader(mode) {
      const reader = {
        async start(camera, config, success) {
          this.success = success;
          log.push("start");
          if (overrides.start) await overrides.start();
        },
        async stop() { log.push("stop"); if (overrides.stop) await overrides.stop(); },
        clear() { log.push("clear"); },
        async scanFile(file, showImage) {
          assert.equal(showImage, false);
          log.push("file");
          return overrides.file ? overrides.file(file) : "decoded-file";
        }
      };
      readers.push(reader);
      log.push(mode);
      return reader;
    },
    releaseMedia: () => log.push("release"),
    onReady: () => log.push("ready"),
    onResult: text => { log.push("result"); results.push(text); },
    onError: error => errors.push(error)
  });
  return {controller, log, results, errors, readers};
}
test("successful scan closes the camera before submitting and ignores duplicate frames", async () => {
  const f = fixture();
  await f.controller.start();
  f.readers[0].success("first");
  f.readers[0].success("duplicate");
  await f.controller.idle();
  assert.deepEqual(f.results, ["first"]);
  assert.ok(f.log.indexOf("stop") < f.log.indexOf("result"));
  assert.ok(f.log.indexOf("clear") < f.log.indexOf("result"));
});
test("closing while permission is pending stops a camera that starts later", async () => {
  const pending = deferred();
  const f = fixture({start: () => pending.promise});
  const start = f.controller.start();
  await tick();
  const stop = f.controller.stop();
  pending.resolve();
  await Promise.all([start, stop]);
  f.readers[0].success("late");
  await f.controller.idle();
  assert.ok(f.log.includes("stop"));
  assert.ok(!f.log.includes("ready"));
  assert.deepEqual(f.results, []);
});
test("closing before queued start avoids asking for permission", async () => {
  const f = fixture();
  await Promise.all([f.controller.start(), f.controller.stop()]);
  assert.equal(f.readers.length, 0);
});
test("closing after a decoded frame cancels its pending navigation", async () => {
  const f = fixture();
  await f.controller.start();
  f.readers[0].success("late");
  await f.controller.stop();
  assert.deepEqual(f.results, []);
});
test("file reading waits until camera has stopped", async () => {
  const f = fixture();
  await f.controller.start();
  await f.controller.file({});
  assert.deepEqual(f.results, ["decoded-file"]);
  assert.ok(f.log.indexOf("stop") < f.log.indexOf("file"));
});
test("old file result cannot win over a newer selection", async () => {
  const pending = deferred();
  let count = 0;
  const f = fixture({file: () => ++count === 1 ? pending.promise : "new"});
  const old = f.controller.file({});
  await tick();
  const newer = f.controller.file({});
  pending.resolve("old");
  await Promise.all([old, newer]);
  assert.deepEqual(f.results, ["new"]);
});
test("page cancellation suppresses an in-flight file result", async () => {
  const pending = deferred();
  const f = fixture({file: () => pending.promise});
  const scan = f.controller.file({});
  await tick();
  const stop = f.controller.stop();
  pending.resolve("late");
  await Promise.all([scan, stop]);
  assert.deepEqual(f.results, []);
});
for (const name of ["NotAllowedError", "NotFoundError", "NotReadableError"]) {
  test(`${name} releases resources and allows a later file scan`, async () => {
    const f = fixture({start: () => Promise.reject(new Error(name))});
    await f.controller.start();
    assert.equal(f.errors.length, 1);
    assert.match(String(f.errors[0]), new RegExp(name));
    assert.equal(f.log.at(-1), "clear");
    await f.controller.file({});
    assert.deepEqual(f.results, ["decoded-file"]);
  });
}
test("stop failure still releases media tracks and clears the reader", async () => {
  const f = fixture({stop: () => Promise.reject(new Error("stop failed"))});
  await f.controller.start();
  await f.controller.stop();
  assert.equal(f.errors.length, 1);
  assert.deepEqual(f.log.slice(-3), ["stop", "release", "clear"]);
});
test("invalid image reports failure and a later image can be scanned", async () => {
  let first = true;
  const f = fixture({file: () => {
    if (first) { first = false; throw new Error("No QR"); }
    return "valid";
  }});
  await f.controller.file({});
  await f.controller.file({});
  assert.equal(f.errors.length, 1);
  assert.deepEqual(f.results, ["valid"]);
});
test("reopening camera cancels callbacks from the previous reader", async () => {
  const f = fixture();
  await f.controller.start();
  await f.controller.stop();
  await f.controller.start();
  f.readers[0].success("old");
  f.readers[1].success("new");
  await f.controller.idle();
  assert.deepEqual(f.results, ["new"]);
});
