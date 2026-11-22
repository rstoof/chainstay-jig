"""
Straight test-fit dies: same jig, but with no bend (die offset 0), so the dies close
fully on the stay as it is now. Checks the measured stay sections, the fingers that
follow the stay height, the lug butt and the bolt holes before printing the real dies.

Run:  python testfit.py   -> writes out/testfit/*.stl / *.step
"""
from pathlib import Path
import jig

jig.DIE_OFF = 0.0
jig.Y_OUT_BACK = jig.W_MAX / 2 + jig.CLR / 2 + jig.WALL

import scene  # noqa: E402  (uses the patched jig values)
from build123d import export_stl, export_step, Location, Vector  # noqa: E402


def ov(a, b):
    r = a & b
    return 0.0 if r is None else r.volume


if __name__ == "__main__":
    out = Path(__file__).parent / "out" / "testfit"
    out.mkdir(parents=True, exist_ok=True)
    parts, meta = scene.build()
    jl = parts.pop("_jig_local")
    plain = jig.build()
    tube = plain["tube_straight"]
    print("test dies valid:", jl["die_inner"].is_valid, jl["die_outer"].is_valid,
          "solids:", len(jl["die_inner"].solids()), len(jl["die_outer"].solids()))
    print("stay vs test dies:", round(ov(tube, jl["die_inner"] + jl["die_outer"]), 2),
          " dies overlap:", round(ov(jl["die_inner"], jl["die_outer"]), 2))
    frame = parts["bb_frame"]; nds = parts["stay_nds_straight"]
    hits = [k for k in ("jig_die_inner", "jig_die_outer", "jig_plate_inner", "jig_plate_outer", "jig_bolts", "jig_nuts")
            if ov(parts[k], frame) > 0.05 or ov(parts[k], nds) > 0.05]
    print("collisions with frame / other stay:", hits or "none")
    for k in ("die_inner", "die_outer"):
        export_stl(jl[k], str(out / f"{k}_test.stl"), tolerance=0.05, angular_tolerance=0.2)
        export_step(jl[k], str(out / f"{k}_test.step"))
    print("written to", out)
