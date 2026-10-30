# 12 Tracking

## Algorithm

IoU and centroid matching with the Hungarian algorithm, plus a second pass for low-confidence observations (the ByteTrack idea).

1. **Predict.** Each track predicts its bbox with a constant-velocity alpha-beta filter on centre and size.
2. **Cost.** `C[i, j] = 1 - IoU(pred_i, obs_j)`. Where IoU is 0, use `1 + d_centroid / frame_diagonal` so nearby non-overlapping boxes still rank.
3. **First pass.** Observations with `confidence >= tracking.high_conf`. Solve with `scipy.optimize.linear_sum_assignment`. Accept a pair only if `IoU >= tracking.iou_gate`.
4. **Second pass.** Remaining observations against remaining tracks, same gate.
5. **New tracks.** Unmatched observations start tentative tracks. A track becomes confirmed after `tracking.confirm_hits` consecutive matched frames.
6. **Misses.** Unmatched tracks increment `misses` and coast on their prediction. Delete after `tracking.max_coast_s` without a match.
7. **IDs.** Positive integers, increasing per process run, never reused, never persisted.

The tracker runs on the full frame. Zone is an attribute assigned afterward (SPECS/15), so a person walking across zones keeps one ID.

Only confirmed, **live** tracks are passed to zones and attention (D12). A track is live once, since it began, either eye's blink score exceeded `tracking.liveness_blink` or its face centre spread reached `tracking.liveness_move_px` in x or y. Liveness is sticky. This rejects posters, masks and still pictures.

## Output

`Track(id, bbox_px, centroid_px, created_t, last_seen_t, hits, misses, confirmed, last_obs)`.

## Acceptance

AC-TRK-01 to AC-TRK-04.
