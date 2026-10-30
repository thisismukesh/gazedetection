# 14 Attention State Machine

One instance per confirmed track. Pure module.

## Step function

`step(t: float, sample: ScoredSample | None) -> list[Event]`

`ScoredSample` = filtered `score`, `eyes_closed`, owning `zone_id`, `az_rel_rad`, `el_rad` (SPECS/20). `None` means the track was not observed this frame.

## States

`UNKNOWN`, `LOOKING`, `AWAY_PENDING`, `AWAY`, `LOOKING_PENDING`, `LOST` (terminal).

## Parameters (`attention.*`)

`t_on`, `t_off` (validated `t_off < t_on`), `away_confirm_s`, `look_confirm_s`, `retrigger_cooldown_s`, `missing_as_away_s`, `track_timeout_s`, `trigger_on_first_seen_away`, `max_triggers_per_min`.

## Transitions

| From | Condition | To | Event |
|---|---|---|---|
| UNKNOWN | `score >= t_on` sustained `look_confirm_s` | LOOKING | `GazeAcquired` |
| UNKNOWN | `score <= t_off` sustained `away_confirm_s` | AWAY | `GazeLost` only if `trigger_on_first_seen_away` |
| LOOKING | `score <= t_off` | AWAY_PENDING (start = t) | none |
| AWAY_PENDING | `score >= t_on` | LOOKING | none |
| AWAY_PENDING | `t - start >= away_confirm_s` | AWAY | `GazeLost` if cooldown and rate limit allow, else none and `suppressed_triggers += 1` |
| AWAY | `score >= t_on` | LOOKING_PENDING (start = t) | none |
| LOOKING_PENDING | `score <= t_off` | AWAY | none |
| LOOKING_PENDING | `t - start >= look_confirm_s` | LOOKING | `GazeRegained` |

Additional rules:

- **Hysteresis band.** A score strictly between `t_off` and `t_on` never starts a transition. Running pending timers continue.
- **Blinks.** When `eyes_closed` is true, no transition occurs and pending timers pause (that frame's elapsed time is not counted).
- **Missing observations.** If the state is LOOKING or AWAY_PENDING and the track has been unobserved for `missing_as_away_s`, go to AWAY and emit `GazeLost` with the last known bearing and zone (people who turn to profile often drop out of detection). Cooldown and rate limit apply.
- **Timeout.** In any state, unobserved for `track_timeout_s` -> LOST, emit `TrackLost`. No further events.
- **Cooldown.** Consecutive `GazeLost` events for a track are at least `retrigger_cooldown_s` apart.
- **Rate limit.** At most `max_triggers_per_min` `GazeLost` per track in any sliding 60 s window.
- **TrackUpdated.** Every observed step emits `TrackUpdated` with current zone, bearing, score and state, so heads can follow targets.

`GazeLost` carries the track's owning `zone_id` at the moment of the transition (D3).

## Invariants (property-tested)

- **I1** Between two `GazeLost` events for one track there is a `GazeRegained`.
- **I2** After the state settles, a sequence whose scores all lie strictly inside (`t_off`, `t_on`) produces no `GazeLost`, `GazeAcquired` or `GazeRegained`.
- **I3** A step with `eyes_closed = true` never emits `GazeLost`, `GazeAcquired` or `GazeRegained`.
- **I4** Consecutive `GazeLost` events for a track are at least `retrigger_cooldown_s` apart.
- **I5** Output is a deterministic function of the input sequence.
- **I6** Nothing is emitted after `TrackLost`.

## Acceptance

AC-SM-01 to AC-SM-09.
