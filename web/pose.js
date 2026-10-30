// Pure pose mapping for a rendered head. Implements SPECS/17 (Client). AC-REN-03.
// Positive yaw turns the face toward the audience's right; positive pitch tilts it up.
export function applyPose(rotation, yaw, pitch) {
  rotation.order = "YXZ";
  rotation.y = yaw;
  rotation.x = -pitch;
  return rotation;
}
