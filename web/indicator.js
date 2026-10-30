// Pure helpers for the indicator under each head. Implements SPECS/17 (Client). AC-REN-06.
const PALETTE = ["#4fc3f7", "#ffb74d", "#ba68c8", "#81c784", "#f06292", "#fff176"];
const NOBODY = "#6b6b78";

export function personColor(person) {
  if (person === null || person === undefined) return NOBODY;
  return PALETTE[(person - 1 + PALETTE.length * 1000) % PALETTE.length];
}

const MIN_TURN_DEG = 3;

// Live direction as the audience sees it: positive yaw turns toward the audience's right.
function direction(yaw) {
  if (typeof yaw !== "number") return "";
  const deg = Math.round((Math.abs(yaw) * 180) / Math.PI);
  if (deg <= MIN_TURN_DEG) return "";
  return ` · ${deg}° ${yaw > 0 ? "right" : "left"}`;
}

function describe(head) {
  const target = head.target_track ?? null;
  const person = head.person ?? null;
  if (head.mode === "mask" && target !== null) {
    return { text: `masked · #${target} looked away`, kind: "masked", person: target };
  }
  if ((head.mode === "orient" || head.mode === "hold") && target !== null) {
    return { text: `staring at #${target}`, kind: "staring", person: target };
  }
  if (head.mode === "return") return { text: "returning", kind: "returning", person };
  if (person !== null) return { text: `glancing · watched by #${person}`, kind: "watched", person };
  return { text: "idle · no one", kind: "idle", person: null };
}

export function indicator(head) {
  const d = describe(head);
  return { ...d, text: d.text + direction(head.yaw) };
}
