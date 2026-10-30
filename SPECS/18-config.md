# 18 Configuration

## Loading

1. `config/default.toml`
2. File passed with `--config` (overrides)
3. Environment variables `LOOKAWAY__<SECTION>__<KEY>`
4. CLI flags (`--source`)

Validated with pydantic v2. Unknown keys are errors. Degrees and seconds in files; converted to radians on load. The resolved config's SHA-256 is logged at startup.

Cross-field checks:
- `attention.t_off < attention.t_on`
- `zones.boundaries` strictly increasing, inside (0, 1), length `zones.count - 1`
- `attention.eye_weight_iod_min_px < attention.eye_weight_iod_full_px`
- all limits, rates and durations positive
- `render.camera_view = true` requires `render.allow_lan = false`
- `privacy.mode = "installation"` forbids `privacy.allow_restricted_models = true` without `privacy.restricted_license_ref`

## Canonical defaults

`config/default.toml` must equal this block. `tests/unit/test_config_matches_spec.py` extracts the block from this file and compares parsed values.

```toml
[capture]
source = "webcam:0"            # webcam:<index> | video:<path> | replay:<path>
width = 1280
height = 720
fps = 30
hfov_deg = 70.0                # used only without a calibration file
calibration_file = ""
mirror_display = true          # overlay window only

[zones]
count = 3
boundaries = [0.3333333, 0.6666667]
margin_px = 24
switch_s = 0.4

[perception]
backend = "mediapipe"
model_path = "models/face_landmarker.task"
max_faces = 6
min_detection_confidence = 0.5
min_presence_confidence = 0.5
min_tracking_confidence = 0.5

[tracking]
iou_gate = 0.2
high_conf = 0.6
confirm_hits = 3
max_coast_s = 1.0
liveness_blink = 0.35          # a blink this strong proves the face is alive
liveness_move_px = 8.0         # or the face centre moving this far in x or y

[attention]
scorer = "geometric"
ipd_m = 0.063
eye_radius_ratio = 0.40         # eyeball radius / eye width: iris offset = ratio * sin(eye angle)
eye_weight_iod_min_px = 15.0
eye_weight_iod_full_px = 45.0
look_target_pitch_deg = 8.0     # the display sits below the camera: people look this far below the lens
cone_deg = 18.0
softness_deg = 4.0
blink_thresh = 0.5
t_on = 0.65
t_off = 0.35
away_confirm_s = 0.2
look_confirm_s = 0.30
retrigger_cooldown_s = 1.0
missing_as_away_s = 0.35
track_timeout_s = 1.0
trigger_on_first_seen_away = false
max_triggers_per_min = 12

[attention.one_euro]
min_cutoff = 1.0
beta = 0.05
d_cutoff = 1.0

[control]
rate_hz = 100
yaw_scale = 4.0
pitch_scale = 2.0
pitch_offset_deg = 0.0
arrive_tol_deg = 2.0
hold_s = 2.0
min_hold_s = 0.8
next_target_ttl_s = 1.5
release_on_regain = true
regain_release_s = 0.4
idle_sway_deg = 2.0
idle_sway_period_s = 6.0
wander_yaw_deg = 40.0
wander_pitch_deg = 14.0
wander_min_dwell_s = 0.5
wander_max_dwell_s = 1.5
wander_looking_ttl_s = 1.0       # a person counts as looking this long after the last LOOKING update

[control.target_one_euro]
min_cutoff = 0.8
beta = 0.02
d_cutoff = 1.0

[control.limits]
yaw_deg = 60.0
pitch_deg = 30.0
vel_deg_s = 360.0
acc_deg_s2 = 2400.0

[render]
host = "127.0.0.1"
port = 8765
rate_hz = 60
debug_rate_hz = 10
allow_lan = false
camera_view = true             # stream the annotated camera frame to the browser (localhost only)
camera_view_fps = 15
camera_view_width = 480

[observability]
log_level = "INFO"
overlay = false
metrics_window_s = 10.0

[privacy]
mode = "installation"          # "development" enables consent-gated landmark recording
allow_restricted_models = false
restricted_license_ref = ""
```

## Shipped overrides

- `config/demo.toml`: `observability.overlay = true`.
- `config/dev.toml`: `privacy.mode = "development"`, `observability.log_level = "DEBUG"`.

Values marked for tuning in SPECS/13 are updated here after M0, with a decision entry in SPECS/03.
