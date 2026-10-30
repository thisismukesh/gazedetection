# 13 Attention Scoring

## Goal

Answer one question per track per frame: is this person looking at the camera (the piece)? Output a smoothed score in [0, 1]. Continuous gaze accuracy is not the goal; the state machine (SPECS/14) needs reliable transitions.

## Interface

`AttentionScorer.score(obs: FaceObservation, intrinsics: Intrinsics) -> AttentionSample` with `angle_to_cam_rad`, `raw_score`, `eyes_closed`, `quality`.

Smoothing is applied per track by the pipeline, not inside the scorer, so scorers stay stateless.

## Default: `GeometricScorer`

All steps are in the OpenCV camera frame.

1. **Face position.** Ray through `centroid_px` using the intrinsics. Depth `z = fx · attention.ipd_m / iod_px`. Gives `p_cam`.
2. **Head direction.** `f_head` = the head's forward axis from `R_cam_head`, with the sign pinned by AC-PER-05 so a frontal face gives `f_head` pointing toward the camera.
3. **Eye offset.** Per eye:
   - `u = (iris_x - mid_corners_x) / eye_width`
   - `v = (iris_y - mid_lids_y) / eye_height`
   - `eye_yaw = attention.k_yaw_deg · u`, `eye_pitch = attention.k_pitch_deg · v`
   - Average the two eyes weighted by eye width.
4. **Eye weight (distance and openness).**
   `w_eye = clamp((iod_px - attention.eye_weight_iod_min_px) / (attention.eye_weight_iod_full_px - attention.eye_weight_iod_min_px), 0, 1) · (1 - mean(blink))`.
   With defaults (15 px, 45 px) the eye term is fully weighted up to about 1.3 m and about half weighted at 2.0 m (D2).
5. **Gaze ray.** Rotate `f_head` by `w_eye · eye_yaw` about the head's vertical axis and `w_eye · eye_pitch` about its horizontal axis. Result `g`.
6. **Angle to camera and to the look target.** `theta_cam = angle(g, -p_cam / |p_cam|)`, reported as `angle_to_cam_rad`. This compensates for people at the frame edge, who must turn to face the camera. In the laptop demo the heads are drawn on a display below the camera, so the point people look at is `attention.look_target_pitch_deg` below the lens: `d_target = Rx(look_target_pitch) · (-p_cam / |p_cam|)` (rotation toward +y, down, in the OpenCV frame) and `theta = angle(g, d_target)`. The physical rig sets the offset to 0.
7. **Score.** `raw_score = sigmoid((attention.cone_deg - theta_deg) / attention.softness_deg)`, using the look-target angle `theta`.
8. **Eyes closed.** `eyes_closed = blink_left > attention.blink_thresh and blink_right > attention.blink_thresh`.
9. **Quality.** `min(1, iod_px / attention.eye_weight_iod_full_px) · obs.confidence`. Reported for the overlay and logs; not used in decisions in M1 to M3.

## Smoothing

The pipeline keeps one `OneEuroFilter` per track on `raw_score` (`attention.one_euro.*`), reset when a track is created, and passes the filtered value to the state machine as `score`.

1-euro filter (Casiez, Roussel, Vogel, CHI 2012): cutoff `fc = min_cutoff + beta · |dx_hat|`, with derivative filtered at `d_cutoff`. Implemented in `attention/one_euro.py` (pure).

## Tuning

`k_yaw_deg`, `k_pitch_deg`, `cone_deg`, `softness_deg` are initial guesses. M0 tunes them (SPECS/40) and updates SPECS/18.

## Plug-ins (not in M1 to M3)

`OnnxGazeScorer` for appearance-based models and `FusionScorer` for weighted averages. Restricted-license weights follow SPECS/21 P7.

## Acceptance

AC-ATT-01 to AC-ATT-07.
