import { test } from "node:test";
import assert from "node:assert/strict";
import { indicator, personColor } from "./indicator.js";

test("AC-REN-06 staring head names its face", () => {
  const r = indicator({ mode: "hold", target_track: 7, person: 7 });
  assert.equal(r.text, "staring at #7");
  assert.equal(r.kind, "staring");
  assert.equal(r.person, 7);
});

test("orienting counts as staring", () => {
  assert.equal(indicator({ mode: "orient", target_track: 3, person: 3 }).text, "staring at #3");
});

test("assigned but not staring: glancing, watched by its person", () => {
  const r = indicator({ mode: "idle", target_track: null, person: 2 });
  assert.equal(r.text, "glancing · watched by #2");
  assert.equal(r.kind, "watched");
});

test("returning and idle", () => {
  assert.equal(indicator({ mode: "return", target_track: null, person: null }).text, "returning");
  const idle = indicator({ mode: "idle", target_track: null, person: null });
  assert.equal(idle.text, "idle · no one");
  assert.equal(idle.person, null);
});

test("missing person field (older server) still works", () => {
  assert.equal(indicator({ mode: "idle", target_track: null }).text, "idle · no one");
});

test("each face gets a stable colour; same face same colour", () => {
  assert.equal(personColor(4), personColor(4));
  assert.notEqual(personColor(1), personColor(2));
  assert.equal(personColor(null), "#6b6b78");
});

test("live direction is appended as the audience sees it", () => {
  const right = indicator({ mode: "hold", target_track: 2, person: 2, yaw: 0.6 });
  assert.equal(right.text, "staring at #2 · 34° right");
  const left = indicator({ mode: "idle", target_track: null, person: 2, yaw: -0.2 });
  assert.equal(left.text, "glancing · watched by #2 · 11° left");
  const centred = indicator({ mode: "hold", target_track: 2, person: 2, yaw: 0.03 });
  assert.equal(centred.text, "staring at #2");
});

test("AC-MASK masked head says who looked away", () => {
  const r = indicator({ mode: "mask", target_track: 3, person: 3, mask: "😜", yaw: 0 });
  assert.equal(r.text, "masked · #3 looked away");
  assert.equal(r.kind, "masked");
  assert.equal(r.person, 3);
});
