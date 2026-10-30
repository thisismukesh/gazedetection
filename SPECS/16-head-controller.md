# 16 Head Controller

One `HeadController` per head. It listens to the events the `HeadAssigner` addresses to it (`zone_id` = this head's id, D6/D14), runs a pure policy, converts targets to yaw/pitch (D1), applies a motion profile, and sends a `HeadCommand` to its `HeadDriver` every control tick.

Data flow: attention events (keyed by the person's zone) -> `HeadAssigner` -> head-addressed events -> each head's policy.

## Targeting (pure, `control/targeting.py`)

```
yaw_target   = clamp(control.yaw_scale   * az_rel,                         ±control.limits.yaw_deg)
pitch_target = clamp(control.pitch_scale * (el - control.pitch_offset_deg), ±control.limits.pitch_deg)
```

Positive yaw turns the face toward the audience's right. Positive pitch tilts the face up. While following a target, its bearing is smoothed with a 1-euro filter (`control.target_one_euro.*`) reset whenever the target changes.

## Policy (pure, `control/policy.py`)

States: `IDLE`, `ORIENT`, `HOLD`, `RETURN`.

Inputs: events addressed to this head (`GazeAcquired`, `GazeLost`, `GazeRegained`, `TrackUpdated`, `TrackLost`, `TrackReleased`) and `tick(t)`. Output each tick: the pose target, the current mode and the `wander` flag.

| State | Behaviour | Exit |
|---|---|---|
| IDLE | If the assigned person is looking (see rule 9): **wander**. Otherwise neutral (0, 0) plus idle sway: `yaw = idle_sway_deg · sin(2π t / idle_sway_period_s)` | `GazeLost` for this head -> ORIENT |
| ORIENT | Target follows the target track's bearing | Pose within `arrive_tol_deg` on both axes -> HOLD |
| HOLD | Stares: keeps following the target's bearing | `hold_s` after the last away sample (or after entering HOLD) -> RETURN |
| RETURN | Target is neutral | Pose within `arrive_tol_deg` -> IDLE |

Rules:

1. **Trigger.** `GazeLost` received in IDLE or RETURN starts ORIENT toward that track immediately.
2. **Same target again.** `GazeLost` for the current target restarts the hold timer and stays on that target.
3. **Preemption.** `GazeLost` for a different track during ORIENT or HOLD: if in HOLD for at least `min_hold_s`, switch to the new track (ORIENT). Otherwise store it as `next_target` (latest wins). (With the assigner a head serves one person at a time, so this only happens across a release.)
4. **Queued target.** On entering RETURN, if `next_target` exists, is not lost and is younger than `next_target_ttl_s`, go to ORIENT toward it. Otherwise discard it.
5. **Regain.** If `release_on_regain` and the target emits `GazeRegained`, go to RETURN after `regain_release_s`.
6. **Following.** While in ORIENT or HOLD, `TrackUpdated` for the target updates its bearing, so the head follows the person wherever they walk, across zones (D6). A head stops following only through rules 5, 7, 8 or HOLD expiry.
7. **Target lost.** On `TrackLost` for the target, freeze the target pose at the last bearing. Continue to HOLD expiry, then RETURN.
8. **Release (D14).** `TrackReleased` for the head's current target sends it to RETURN, clears its queued target and stops it wandering on that person's behalf.
9. **Isolation.** The policy ignores every event whose `zone_id` is not this head's id. The assigner delivers one person's events to several heads (D14), each copy addressed to its head; copies addressed to other heads must never change this head's state.
10. **Wander (D7).** In IDLE, if a `TrackUpdated` (state LOOKING or AWAY_PENDING), `GazeAcquired` or `GazeRegained` arrived within `control.wander_looking_ttl_s`, the output carries `wander = True`. The controller then picks random targets: yaw uniform in ±`wander_yaw_deg`, pitch in ±`wander_pitch_deg`, a new one every uniform(`wander_min_dwell_s`, `wander_max_dwell_s`) seconds, all through the normal motion limits.
11. **Stare (D7).** While in HOLD, a `TrackUpdated` for the target with state AWAY restarts the linger timer, so the head keeps staring for as long as the person looks away.

## Assignment (pure, `control/assigner.py`, D6, D14)

`HeadAssigner.on_event(event) -> list[Event]` sits between the attention events and the heads.

1. A track without a head gets one on its first event: the head whose id equals the track's zone if free, else the nearest free head (ties to the lower id). With no free head the track is ignored and retried on its next event.
2. The pairing is sticky until `TrackLost`, even if the person moves to another zone.
3. Output events are copies with `zone_id = head id` and `az_rel_rad` re-referenced to that head's zone centre: `az_rel + centre[zone] - centre[head]`.
4. `TrackLost` is forwarded, then the head is freed.
5. **Solo ownership (D14).** When exactly one track has a head, that track also owns every other head (its followers). All its events are delivered to each of its heads, retargeted per head. When a second track gets a head, the followers are released: `TrackReleased(track, head)` is emitted for each, then the new track's events flow. When tracks leave and exactly one remains, the free heads rejoin it; a head that rejoins while the person is looking away receives a synthetic `GazeLost` so it stares at once.
6. Each `GazeLost` reaches only the heads its track owns, and no head is owned by two tracks at once.

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

AC-HEAD-01 to AC-HEAD-11, AC-ASSIGN-01 to AC-ASSIGN-07.
