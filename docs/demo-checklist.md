# Demo checklist

Before the demo:

- [ ] Soft, frontal lighting; no strong backlight behind viewers
- [ ] Heads display directly below (or around) the webcam
- [ ] Three floor marks about 1.2 m from the laptop, one per third of the camera view
- [ ] Privacy signage is up (`docs/signage.md`)
- [ ] First run done once on this machine (camera permission granted, model downloaded)
- [ ] Fallback tested: `uv run lookaway run --source replay:tests/fixtures/landmarks/two_in_one_zone.jsonl`

Start: `uv run lookaway run` (add `--overlay` for the debug window; `D` toggles it, `Q` quits).

Look for:

- [ ] While someone looks at the piece, their head glances around randomly
- [ ] The moment they look away, their head faces forward wearing an emoji mask; it comes off when they look back
- [ ] A blink or a very quick glance does not trigger
- [ ] One person alone: all three heads glance around, then all three put on masks when they look away
- [ ] Several people at once: each gets their own head; a head never reacts to someone else's person
- [ ] Posters or pictures of faces in view are shown as `static?` and ignored
- [ ] A fourth person waits; a head that has been masked for 2 s moves on to them if they are looking
