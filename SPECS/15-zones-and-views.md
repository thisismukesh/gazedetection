# 15 Zones and Views

## Audience frame

Raw webcam images are unmirrored: a person standing to the audience's right appears on the image left. To keep "left" and "right" meaning the same thing everywhere (zones, heads, logs), all zone and bearing math uses the **audience frame**:

- `x_aud = (W - 1) - x`, `y_aud = y` (horizontal mirror of pixel coordinates; the image itself is never flipped).
- Horizontal bearing `az_rad = -atan((x - cx) / fx)`. Positive means toward the audience's right.
- Elevation `el_rad = -atan((y - cy) / fy)`. Positive means above the camera's optical axis.

## Zones (demo)

- `zones.count = 3`. Boundaries are fractions of width in the audience frame (`zones.boundaries`, default 1/3 and 2/3).
- Zone 0 is the audience's left, zone 2 the audience's right. Head k is bound to zone k and is drawn at position k from the audience's left.
- **Zone-relative bearing:** `az_rel = az_rad - az_center[k]`, where `az_center[k]` is the bearing of zone k's centre column. This plays the role of a per-camera bearing in the physical rig.

## Ownership (D3)

Every confirmed track has exactly one owning zone.

1. A newly confirmed track is owned by the zone that contains its `centroid_px` (in the audience frame).
2. Ownership moves to an adjacent zone only after the centroid has been past the shared boundary by more than `zones.margin_px` continuously for at least `zones.switch_s`.
3. If the centroid comes back within the margin before `zones.switch_s`, the switch timer resets.
4. Ownership never splits and is never empty for a confirmed track.

`ZoneMap.assign(track_id, centroid_px, t) -> zone_id` is pure and keeps per-track switch state. `ZoneMap.forget(track_id)` drops state on `TrackLost`.

## Physical rig (later, informational)

`CameraZoneMap`: zone = camera id. Each camera has calibrated intrinsics and fisheye undistortion, mounted at yaw 0°, 120°, 240° about the piece centre. A person detected by two cameras is owned by the camera whose optical axis is closest to the person's bearing in the piece frame, with the same margin and dwell hysteresis. Exact rule is open (SPECS/60 Q5).

## Acceptance

AC-ZONE-01 to AC-ZONE-05.
