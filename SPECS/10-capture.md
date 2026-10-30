# 10 Capture

## Interface

`CameraSource` (SPECS/20): `info`, `open()`, `read() -> Frame | None`, `close()`.

## Implementations

- **`WebcamSource(index, width, height, fps)`**: OpenCV `VideoCapture`. Requests the configured resolution and reports the actual resolution in `info`.
- **`VideoFileSource(path, realtime)`**: `realtime=True` paces frames by their timestamps. `realtime=False` yields frames as fast as they are consumed (tests, bench).
- **`ReplaySource(jsonl_path)`**: emits blank frames whose index and timestamp match a recorded landmark stream. Used with `ReplayPerception` so the pipeline runs with no camera and no model.

Source selection string: `webcam:<index>`, `video:<path>`, `replay:<path>`.

## Behaviour

1. Each frame is stamped with `Clock.now()` at grab time (`t_capture`) and a monotonically increasing `index`.
2. A capture thread writes into a `LatestFrameSlot`. `take_latest()` returns the newest unread frame, or `None` if nothing new arrived. Overwritten frames increment `frames_dropped`.
3. On read failure, publish `SourceStatus(ok=False)` once, then retry with backoff 0.5, 1, 2, 5, 5, ... seconds. On recovery publish `SourceStatus(ok=True)`.
4. Intrinsics: from `capture.calibration_file` if set; otherwise from `capture.hfov_deg` with a centred principal point and square pixels: `fx = fy = (w / 2) / tan(hfov / 2)`, `cx = w / 2`, `cy = h / 2`.
5. Frames are never mirrored in the pipeline. Mirroring for the audience frame is a coordinate transform in SPECS/15. `capture.mirror_display` only affects the overlay window.

## Acceptance

AC-CAP-01 to AC-CAP-04.
