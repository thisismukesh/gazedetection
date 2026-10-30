# 16 Head Controller

One `HeadController` per head. It listens to bus events for its own zone, runs a pure policy, converts targets to yaw/pitch (D1), applies a motion profile, and sends a `HeadCommand` to its `HeadDriver` every control tick.

## Targeting (pure, `control/targeting.py`)

```
yaw_target   = clamp(control.yaw_scale   * az_rel,                         ±control.limits.yaw_deg)
pitch_target = clamp(control.pitch_scale * (el - control.pitch_offset_deg), ±control.limits.pitch_deg)
```

Positive yaw turns the face toward the audience's right. Positive pitch tilts the face up. While following a target, its bearing is smoothed with a 1-euro filter (`control.target_one_euro.*`) reset whenever the target changes.

## Policy (pure, `control/policy.py`)

States: `IDLE`, `ORIENT`, `HOLD`, `RETURN`.

Inputs: events for this head's zone (`GazeLost`, `GazeRegained`, `TrackUpdated`, `TrackLost`) and `tick(t)`. Output each tick: the pose target and the current mode.

| State | Behaviour | Exit |
|---|---|---|
| IDLE | Target is neutral (0, 0) plus idle sway: `yaw = idle_sway_deg · sin(2π t / idle_sway_period_s)` | `GazeLost` in zone -> ORIENT |
| ORIENT | Target follows the target track's bearing | Pose within `arrive_tol_deg` on both axes -> HOLD |
| HOLD | Keeps following the target's bearing | `hold_s` elapsed -> RETURN |
| RETURN | Target is neutral | Pose within `arrive_tol_deg` -> IDLE |

Rules:

1. **Trigger.** `GazeLost` whose `zone_id` equals this head's zone, received in IDLE or RETURN, starts ORIENT toward that track immediately.
2. **Same target again.** `GazeLost` for the current target restarts the hold timer and stays on that target.
3. **Preemption.** `GazeLost` for a different track during ORIENT or HOLD: if in HOLD for at least `min_hold_s`, switch to the new track (ORIENT). Otherwise store it as `next_target` (latest wins).
4. **Queued target.** On entering RETURN, if `next_target` exists, is not lost, is still owned by this zone, and is younger than `next_target_ttl_s`, go to ORIENT toward it. Otherwise discard it.
5. **Regain.** If `release_on_regain` and the target emits `GazeRegained`, go to RETURN after `regain_release_s`.
6. **Zone change (D3).** If a `TrackUpdated` shows the target's zone is no longer this head's zone, go to RETURN. Other heads do not react unless a new `GazeLost` arrives for them.
7. **Target lost.** On `TrackLost` for the target, freeze the target pose at the last bearing. Continue to HOLD expiry, then RETURN.
8. **Isolation.** Events for other zones never change this head's state.

## Motion (pure, `control/motion.py`)

Per axis, every tick of length `dt = 1 / control.rate_hz`:

```
e      = target - pos
v_des  = sign(e) · min(v_max, sqrt(2 · a_max · |e|))
v      = v + clamp(v_des - v, -a_max · dt, +a_max · dt)
pos    = clamp(pos + v · dt, -limit, +limit)
```

`v_max = control.limits.vel_deg_s`, `a_max = control.limits.acc_deg_s2`. If clamping position stops motion at a limit, set `v = 0`.

**Invariant:** every emitted pose satisfies the position limit, and successive poses satisfy the velocity and acceleration limits within floating-point tolerance. These limits also protect real servos later.

## Output

Each tick: `HeadCommand(head_id, t, yaw_rad, pitch_rad)` to the driver. On mode change, publish `HeadModeChanged(head_id, mode, target_track)`.

## Drivers (`control/drivers/`)

- **`SimulatedHeadDriver`**: forwards commands to the render bridge. `state()` returns the last command.
- **`RecordingHeadDriver`**: stores all commands (tests).
- **`SerialHeadDriver`** (stub, contract-tested against a fake port): maps radians to servo pulse width per joint with `(center_us, us_per_rad, sign, min_us, max_us)`, writes ASCII lines `H<id> <yaw_us> <pitch_us>\n`, at most `control.rate_hz` writes per second. Not used by the demo.

## Acceptance

AC-HEAD-01 to AC-HEAD-08.
