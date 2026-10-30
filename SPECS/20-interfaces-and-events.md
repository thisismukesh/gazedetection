# 20 Interfaces, Types and Events

All cross-module types live in `src/lookaway/types.py` and `src/lookaway/events.py`. Value types are `@dataclass(frozen=True, slots=True)`. Interfaces are `typing.Protocol`.

## Time

```python
class Clock(Protocol):
    def now(self) -> float: ...  # monotonic seconds


class FakeClock:  # tests
    def __init__(self, t0: float = 0.0) -> None: ...
    def now(self) -> float: ...
    def advance(self, dt: float) -> None: ...
```

## Capture

```python
@dataclass(frozen=True, slots=True)
class Intrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    dist: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceInfo:
    source_id: str
    width: int
    height: int
    fps_nominal: float
    intrinsics: Intrinsics


@dataclass(frozen=True, slots=True)
class Frame:
    source_id: str
    index: int
    t_capture: float
    image: "np.ndarray"  # HxWx3 uint8 BGR; empty array in replay


class CameraSource(Protocol):
    @property
    def info(self) -> SourceInfo: ...
    def open(self) -> None: ...
    def read(self) -> Frame | None: ...  # None = no new frame or end of stream
    def close(self) -> None: ...
```

## Perception

```python
Vec2 = tuple[float, float]
Box = tuple[float, float, float, float]  # x0, y0, x1, y1 in pixels
Mat3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


@dataclass(frozen=True, slots=True)
class FaceObservation:
    t: float
    bbox_px: Box
    centroid_px: Vec2
    confidence: float
    iod_px: float
    R_cam_head: Mat3  # OpenCV camera frame
    iris_px: tuple[Vec2, Vec2]  # (image-left eye, image-right eye)
    eye_corners_px: tuple[tuple[Vec2, Vec2], tuple[Vec2, Vec2]]
    eye_lids_px: tuple[tuple[Vec2, Vec2], tuple[Vec2, Vec2]]
    blink: tuple[float, float]  # (image-left eye, image-right eye)


class FacePerception(Protocol):
    def process(self, frame: Frame) -> list[FaceObservation]: ...
```

## Tracking and zones

```python
@dataclass(frozen=True, slots=True)
class Track:
    id: int
    bbox_px: Box
    centroid_px: Vec2
    created_t: float
    last_seen_t: float
    hits: int
    misses: int
    confirmed: bool
    last_obs: FaceObservation | None  # None when coasting


class Tracker(Protocol):
    def update(self, obs: list[FaceObservation], t: float) -> list[Track]: ...


class ZoneMap(Protocol):
    def assign(self, track_id: int, centroid_px: Vec2, t: float) -> int: ...
    def forget(self, track_id: int) -> None: ...
    def center_bearing(self, zone_id: int) -> float: ...  # bearing of zone k's centre column
    def bearing(
        self, zone_id: int, centroid_px: Vec2
    ) -> tuple[float, float]: ...  # (az_rel_rad, el_rad)
```

## Attention

```python
@dataclass(frozen=True, slots=True)
class AttentionSample:
    angle_to_cam_rad: float
    raw_score: float  # [0, 1]
    eyes_closed: bool
    quality: float  # [0, 1]


class AttentionScorer(Protocol):
    def score(self, obs: FaceObservation, intrinsics: Intrinsics) -> AttentionSample: ...


@dataclass(frozen=True, slots=True)
class ScoredSample:  # input to the state machine
    score: float  # filtered
    eyes_closed: bool
    zone_id: int
    az_rel_rad: float
    el_rad: float


class AttentionState(Enum):
    UNKNOWN = auto()
    LOOKING = auto()
    AWAY_PENDING = auto()
    AWAY = auto()
    LOOKING_PENDING = auto()
    LOST = auto()
```

## Control

```python
class HeadMode(Enum):
    IDLE = auto()
    ORIENT = auto()
    HOLD = auto()
    RETURN = auto()


@dataclass(frozen=True, slots=True)
class HeadCommand:
    head_id: int
    t: float
    yaw_rad: float  # + toward audience's right
    pitch_rad: float  # + up


class HeadAssigner:                        # pure; SPECS/16 Assignment, D6, D14
    def on_event(self, e: Event) -> list[Event]: ...  # person events in, head-addressed copies out
    def head_of(self, track_id: int) -> int | None: ...  # primary head
    def heads_of(self, track_id: int) -> list[int]: ...  # primary + followers (lone person)

class HeadDriver(Protocol):
    def send(self, cmd: HeadCommand) -> None: ...
    def state(self) -> HeadCommand | None: ...
    def close(self) -> None: ...
```

## Events

All events are frozen dataclasses with a leading `t: float`.

| Event | Fields |
|---|---|
| `GazeAcquired` | `track_id`, `zone_id` |
| `GazeLost` | `track_id`, `zone_id`, `az_rel_rad`, `el_rad`, `distance_m: float \| None` |
| `GazeRegained` | `track_id`, `zone_id` |
| `TrackUpdated` | `track_id`, `zone_id`, `az_rel_rad`, `el_rad`, `score`, `state: AttentionState` |
| `TrackLost` | `track_id`, `zone_id` |
| `TrackReleased` | `track_id`, `zone_id` (the head that stops following this track; D14) |
| `SourceStatus` | `source_id`, `ok: bool`, `detail: str` |
| `HeadModeChanged` | `head_id`, `mode: HeadMode`, `target_track: int \| None` |

## Bus semantics

- `subscribe(event_type, handler)`, `publish(event)`, `publish_all(events)`.
- Synchronous fan-out in publish order.
- Handlers must not block for more than 1 ms.
- An exception in one handler is logged and does not stop delivery to others.
