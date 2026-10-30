# Head models

The renderer draws procedural heads (sphere + nose) unless `heads.glb` exists in this folder.

To use mannequin heads, add a single GLB named `heads.glb`:

- One head model, facing +Z (toward the viewer), upright (+Y up).
- Any size and origin: the renderer centres it, scales it to a fixed height and rotates it about
  its centre. Yaw turns it about Y, pitch about X.
- The same model is cloned for all three heads. Static meshes work; skeletal animation is ignored.

No model is shipped with the repo. Do not commit scans of real people.
