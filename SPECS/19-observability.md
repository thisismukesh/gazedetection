# 19 Observability

## Logs

structlog JSON lines to stdout. In development mode, also a rotating file under `logs/` (gitignored).

Fields: `t`, `level`, `module`, `event`, and where relevant `track_id`, `zone_id`, `head_id`, scalar values. Never images, crops, landmark arrays or embeddings (enforced by AC-SYS-02).

## Metrics

Kept in process over a sliding `observability.metrics_window_s` window. Exposed in the overlay, the `debug` WebSocket message, and `lookaway bench`.

- `fps_capture`, `fps_perception`, `frames_dropped`
- `latency_ms` per stage: capture->perception, perception->score, score->event, event->command (p50, p95)
- `faces`, `confirmed_tracks`
- `events_total{type}`, `suppressed_triggers`
- `head_mode{head_id}`

## Event journal (development mode only)

JSONL of bus events with scalar fields only. Used to create golden files and debug sessions.

## Debug overlay

The same drawing (`draw_overlay`) feeds two outputs: an OpenCV window (`--overlay`, toggled with `D`, quit with `Q`, main thread per D8) and the camera view in the page (D11). It draws:
- zone boundaries (in the displayed, mirrored view when `capture.mirror_display`)
- each live track's bbox, ID, state, score and assigned head (`-> head k`, or `-> all heads` for a lone person)
- score bar coloured by state: green LOOKING, amber pending, red AWAY, grey UNKNOWN
- head direction (cyan arrow from the face) and gaze direction (yellow arrows from each iris), projected onto the image and mirrored with it
- non-live tracks (D12) as a thin grey box labelled `static?`
- per head: mode and current target track
- FPS and p95 latency

Text sits on translucent dark boxes so it stays legible at the 480 px camera-view size. The overlay frame is never written to disk.

## Bench

`lookaway bench --config ... [--source video:...] [--seconds N]` runs the pipeline headless, prints p50/p95 per stage, and exits non-zero if NFR-PERF-01 or NFR-PERF-02 is violated.
