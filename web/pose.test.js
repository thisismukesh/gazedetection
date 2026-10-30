import { test } from "node:test";
import assert from "node:assert/strict";
import { applyPose } from "./pose.js";

test("AC-REN-03 maps yaw and pitch to Euler YXZ", () => {
  const r = applyPose({}, 0.5, 0.3);
  assert.equal(r.order, "YXZ");
  assert.equal(r.y, 0.5);
  assert.equal(r.x, -0.3);
});
