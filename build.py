"""Build jig + bike scene once, run all checks (validity, overlaps, collisions, gaps). --export writes everything to ./out"""
import json, math, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import jig, scene
from build123d import *


def ov(a, b):
    """Overlap volume; 0 when the shapes do not meet."""
    r = a & b
    return 0.0 if r is None else r.volume

out = scene.OUT; out.mkdir(parents=True, exist_ok=True)
jig.report()
parts, meta = scene.build()
jl = parts.pop("_jig_local")
y0 = meta["y0"]; n = Vector(*meta["n"])
frame = parts["bb_frame"]; nds = parts["stay_nds_straight"]

print("--- checks")
for k in ("die_inner", "die_outer"):
    print(k, "valid", jl[k].is_valid, "solids", len(jl[k].solids()))
plain = jig.build()
t = plain["tube_final"]
print("tube vs fitted dies:", round(ov(t, jl["die_inner"] + jl["die_outer"]), 2),
      " dies overlap:", round(ov(jl["die_inner"], jl["die_outer"]), 2))
bad = 0
for k in ("jig_die_inner", "jig_die_outer", "jig_washers_inner", "jig_washers_outer", "jig_bolts", "jig_nuts"):
    inner = k in ("jig_die_inner", "jig_washers_inner", "jig_bolts")
    for st, sh in (("closed", 0), ("open", -jig.DIE_OFF)):
        m = parts[k].moved(Location(n * (sh if inner else 0)))
        a, b = ov(m, frame), ov(m, nds)
        if a > 0.05 or b > 0.05:
            bad += 1
            o = (m & (frame + nds))
            bb = o.bounding_box()
            print(f"HIT {k} {st}: frame {a:.1f} other stay {b:.1f}  bike x {bb.min.X:.0f}..{bb.max.X:.0f}")
print("collisions:", bad)
# flipped 180 deg around the length axis on the other stay: in jig coordinates the frame
# is mirrored top <-> bottom (the bike is symmetric; the other stay is then the dimpled one)
inv = Location(Plane(origin=Vector(*meta["p0"]) + Vector(*meta["u"]) * jig.JIG_START_FROM_BB,
                     x_dir=Vector(*meta["u"]), z_dir=Vector(*meta["u"]).cross(n))).inverse()
bad_f = 0
for stay_k in ("stay_nds_straight", "stay_nds_bent"):
    obst = (frame + parts[stay_k]).moved(inv).mirror(Plane.XY)
    for k in ("die_inner", "die_outer", "washers_inner", "washers_outer", "bolts", "nuts"):
        inner = k in ("die_inner", "washers_inner", "bolts")
        sh = -jig.DIE_OFF if (inner and stay_k.endswith("straight")) else 0
        v = ov(jl[k].moved(Location((0, sh, 0))), obst)
        if v > 0.05:
            bad_f += 1
            print(f"HIT flipped {k} ({stay_k}): {v:.1f}")
print("collisions, flipped for the other stay:", bad_f)
print("inner washers to frame / other stay, open:", round(parts["jig_washers_inner"].moved(Location(n * -jig.DIE_OFF)).distance_to(nds + frame), 2))

meta.update(scene.report(y0))
meta["tires"] = {}
for tw in scene.TIRE_SIZES:
    g0, g1 = scene.gaps(y0, False, tw), scene.gaps(y0, True, tw)
    s0, m0 = min(g0, key=lambda q: q[1]); s1, m1 = min(g1, key=lambda q: q[1])
    meta["tires"][tw] = [round(m0, 1), round(m1, 1), round(s0)]
    print(f"tire {tw}: {m0:5.1f} at BB+{s0:.0f} -> {m1:5.1f}")
meta["rings"] = {}
for N in (40, 44, 48, 52):
    R = 12.7 / (2 * math.sin(math.pi / N)) + 4.0
    res = []
    for bent in (False, True):
        best = None
        for i in range(400):
            s = 20 + i; c = scene.centre(s, y0, bent)
            if math.hypot(c.X, c.Z) < R:
                g = (scene.CHAINRING_Y - 1) - (c.Y + scene.section(s)[1] / 2)
                best = g if best is None else min(best, g)
        res.append(round(best, 1))
    meta["rings"][N] = res
    print("ring", N, res)

if "--export" in sys.argv:
    for name, shp in plain.items():
        export_stl(shp, str(jig.OUT / f"{name}.stl"), tolerance=0.05, angular_tolerance=0.2)
    export_step(plain["die_outer"], str(jig.OUT / "die_outer.step"))
    export_step(plain["die_inner"], str(jig.OUT / "die_inner.step"))
    for k in ("die_inner", "die_outer"):
        export_stl(jl[k], str(jig.OUT / f"{k}_fitted.stl"), tolerance=0.05, angular_tolerance=0.2)
        export_step(jl[k], str(jig.OUT / f"{k}_fitted.step"))
    for f in out.glob("*.stl"): f.unlink()
    for name, shp in parts.items():
        export_stl(shp, str(out / f"{name}.stl"), tolerance=0.1, angular_tolerance=0.3)
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print("exported")
