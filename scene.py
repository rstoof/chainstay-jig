"""
Bike context for the chainstay jig: BB shell, both chainstays (straight and bent),
dropouts, rear wheel + tire, chainring, and the jig placed on the drive-side stay.

Raleigh Record Sprint. Measured: lugged BB, lug length / OD / gap, stay sections near
the BB, dimple. Still generic: chainstay length, BB drop, rear spacing, tire position.

Bike coordinates: origin = BB centre, +X rearward, +Y = drive side (right), +Z up.
Run:  python scene.py   -> writes STLs into ./out/bike
"""
import math
from pathlib import Path
from build123d import *
import jig

# ---------------- generic frame (measure!) ----------------
CS_LEN = jig.DROPOUT_FROM_BB   # chainstay length, BB centre to axle along the stay
BB_DROP = 70.0                 # axle height above BB centre
OLD = 126.0                    # rear spacing (dropout inner faces)
STAY_END_Y = OLD / 2 - 7       # stay centreline at the dropout
BB_SHELL_W, BB_SHELL_OD, BB_SHELL_ID = 68.0, jig.BB_SHELL_OD, 34.8
LUG_OD = 26.2                  # chainstay lug outer diameter (measured)
LUG_GAP = 10.8                 # gap between the two chainstay lugs (measured)
STAY_Y_AT_LUG = (LUG_GAP + LUG_OD) / 2   # stay centre at the lug end
SEAT_ANGLE, DOWN_ANGLE = 73.0, 58.0
TUBE_OD = 28.6
RIM_R = 311.0                  # 700c bead seat radius
TIRE_W = 40.0                  # reference tire
TIRE_SIZES = (28, 32, 35, 40, 45)
CHAINRING_R, CHAINRING_Y = 85.0, 45.0   # 40T 1x ring, ~45 mm chainline
FIT_CLR = 1.5                  # clearance around the seat tube / down tube / other stay

TIRE_R_MID = RIM_R + TIRE_W / 2 - 3   # torus centre radius (tire overlaps the rim a bit)
OUT = Path(__file__).parent / "out" / "bike"


def section(s):
    """Stay height, width at distance s from BB centre: measured near the BB, then taper (guess)."""
    w, h = jig.sec(s - jig.JIG_START_FROM_BB)
    t = min(1.0, max(0.0, (s - 200) / (CS_LEN - 20 - 200)))
    return (h + (13 - h) * t, w + (13 - w) * t)


def frame_vectors(y0):
    xa = math.sqrt(CS_LEN ** 2 - BB_DROP ** 2 - (STAY_END_Y - y0) ** 2)
    p0 = Vector(0, y0, 0)
    u = (Vector(xa, STAY_END_Y, BB_DROP) - p0).normalized()
    n = Vector(-u.Y, u.X, 0).normalized()          # horizontal, outward
    up = u.cross(n)
    return p0, u, n, up, Vector(xa, 0, BB_DROP)


def bike_offset(s, bent):
    """Lateral offset of the stay after springback (die offset / OVERBEND)."""
    if not bent:
        return 0.0
    x = s - jig.JIG_START_FROM_BB
    x_end = jig.L + 50
    die = jig.yc(x) if x <= x_end else jig.yc(x_end) + jig.SLOPE * (x - x_end)
    return max(0.0, die) / jig.OVERBEND


def centre(s, y0, bent, side=1):
    p0, u, n, up, _ = frame_vectors(y0)
    c = p0 + u * s + n * bike_offset(s, bent)
    return Vector(c.X, c.Y * side, c.Z)


def tire_halfwidth(rho, tw=None):
    tw = TIRE_W if tw is None else tw
    r = tw / 2
    d = rho - (RIM_R + tw / 2 - 3)
    return math.sqrt(r * r - d * d) if abs(d) < r else 0.0


def gaps(y0, bent, tw=None):
    """Tire-to-stay inner face gap along the drive stay: list of (s, gap)."""
    _, _, n, _, axle = frame_vectors(y0)
    out = []
    for i in range(0, 4001):
        s = 20 + i * (CS_LEN - 40) / 4000
        c = centre(s, y0, bent)
        rho = math.hypot(c.X - axle.X, c.Z - axle.Z)
        w = section(s)[1]
        out.append((s, c.Y - w / 2 * abs(n.Y) - tire_halfwidth(rho, tw)))
    return out


def solve_y0():
    """Stay spacing from the measured lugs: centre at the lug end = STAY_Y_AT_LUG."""
    lo, hi = 0.0, 40.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if centre(jig.JIG_START_FROM_BB, mid, False).Y < STAY_Y_AT_LUG:
            lo = mid
        else:
            hi = mid
    return hi


def stay(y0, bent, side, dimple):
    p0, u, n, up, _ = frame_vectors(y0)
    ss = [0.0] + [10.0 + i * (CS_LEN - 10) / 30 for i in range(31)]
    pts = [centre(s, y0, bent, side) for s in ss]
    path = Spline(*pts)
    secs = []
    for s, pt in zip(ss, pts):
        t = path.tangent_at(path.param_at_point(pt))
        nn = Vector(n.X, n.Y * side, 0)
        x_dir = (nn - t * nn.dot(t)).normalized()
        h, w = section(s)
        secs.append(Plane(origin=pt, x_dir=x_dir, z_dir=t) * Ellipse(w / 2, h / 2).wire())
    body = loft([make_face(w) for w in secs])
    if dimple:
        s_d = jig.DIMPLE[0] + jig.DIMPLE_DEEPEST + jig.JIG_START_FROM_BB
        c = centre(s_d, y0, bent, side)
        nn = Vector(n.X, n.Y * side, 0)
        loc = Location(Plane(origin=c + nn * (section(s_d)[1] / 2), x_dir=u, z_dir=up))
        body -= jig.dimple_shape().moved(loc)
    return body


def fit_jig(jp, jloc, n, st_dir, dt_dir, stub, other_stay=None, other_lug=None):
    """Fit the jig to the frame (all in jig coordinates). The dies butt against the
    end of the chainstay lug (repeatable position). Clear the seat tube, down tube,
    other stay and other lug, also over the opening travel of the inner side.
    """
    inv = jloc.inverse()
    tubes = []
    for d in (st_dir, dt_dir):
        pl = Plane(origin=d * (90), z_dir=d)
        tubes.append(pl * Cylinder(TUBE_OD / 2 + FIT_CLR, 180))
    if other_stay is not None:
        tubes.append(offset(other_stay, FIT_CLR))
    if other_lug is not None:
        tubes.append(offset(other_lug, FIT_CLR))
    tubes = [t.moved(inv) for t in tubes]
    # the same jig flipped 180 deg around its length axis does the other stay: top and
    # bottom swap, so clear the frame mirrored top <-> bottom as well (bike is symmetric)
    tubes += [t.mirror(Plane.XY) for t in tubes]
    # the inner side slides up to DIE_OFF towards the bike centre while the stay is still straight
    steps = [k for k in (0, 2, 4, 6, 8) if k < jig.DIE_OFF] + [jig.DIE_OFF + 0.5]
    travel = [t.moved(Location((0, k, 0))) for t in tubes for k in steps]

    # cut one cutter at a time: a single cut with the whole compound can silently skip parts
    die = jp["die_inner"]
    for cutter in travel:
        die = die - cutter
    jp["die_inner"] = max(die.solids(), key=lambda q: q.volume)   # drop slivers left by the cut
    die = jp["die_outer"]
    for cutter in tubes:
        die = die - cutter
    jp["die_outer"] = max(die.solids(), key=lambda q: q.volume)
    return jp


def build():
    y0 = solve_y0()
    p0, u, n, up, axle = frame_vectors(y0)
    parts = {}

    shell = Rot(90, 0, 0) * (Cylinder(BB_SHELL_OD / 2, BB_SHELL_W) - Cylinder(BB_SHELL_ID / 2, BB_SHELL_W + 2))
    st_dir = Vector(-math.cos(math.radians(SEAT_ANGLE)), 0, math.sin(math.radians(SEAT_ANGLE)))
    # seat tube leans back: top is rearward (+X)
    st_dir = Vector(-st_dir.X, 0, st_dir.Z)
    dt_dir = Vector(-math.cos(math.radians(DOWN_ANGLE)), 0, math.sin(math.radians(DOWN_ANGLE)))

    def stub(d, length):
        pl = Plane(origin=d * (length / 2 + 8), z_dir=d)
        return pl * Cylinder(TUBE_OD / 2, length)
    lugs = {}
    for side in (1, -1):
        c0 = centre(0.0, y0, False, side)
        d = (centre(jig.JIG_START_FROM_BB, y0, False, side) - c0).normalized()
        lugs[side] = Plane(origin=c0 + d * (jig.JIG_START_FROM_BB / 2), z_dir=d) * Cylinder(LUG_OD / 2, jig.JIG_START_FROM_BB)
    parts["bb_frame"] = shell + stub(st_dir, 160) + stub(dt_dir, 160) + lugs[1] + lugs[-1]

    for side, tag in ((1, "drive"), (-1, "nds")):
        parts[f"stay_{tag}_straight"] = stay(y0, False, side, side == 1)
        parts[f"stay_{tag}_bent"] = stay(y0, True, side, side == 1)

    drops = []
    for side in (1, -1):
        drops.append(Pos(axle.X - 5, side * (OLD / 2 + 2.5), axle.Z - 2) * Rot(0, 15, 0) * Box(50, 5, 28))
    parts["dropouts"] = Compound(drops)
    parts["axle"] = Pos(axle.X, 0, axle.Z) * Rot(90, 0, 0) * Cylinder(5, OLD + 20)
    wheel = Pos(axle.X, 0, axle.Z) * Rot(90, 0, 0)
    parts["rim"] = wheel * (Cylinder(RIM_R, 19) - Cylinder(RIM_R - 14, 20))
    for tw in TIRE_SIZES:
        parts[f"tire_{tw}"] = wheel * Torus(RIM_R + tw / 2 - 3, tw / 2)
    for teeth in (40, 44, 48, 52):
        r = 12.7 / (2 * math.sin(math.pi / teeth)) + 4.0   # pitch radius + tooth tip
        parts[f"chainring_{teeth}"] = Pos(0, CHAINRING_Y, 0) * Rot(90, 0, 0) * (Cylinder(r, 2) - Cylinder(r - 15, 3))

    # jig on the drive stay, jig frame: X along stay, Y outward, Z up-ish
    jloc = Location(Plane(origin=p0 + u * jig.JIG_START_FROM_BB, x_dir=u, z_dir=u.cross(n)))
    jp = fit_jig(jig.build(), jloc, n, st_dir, dt_dir, stub, parts["stay_nds_straight"], lugs[-1])
    for k in ("die_outer", "die_inner", "washers_inner", "washers_outer", "bolts", "nuts", "putty"):
        parts["jig_" + k] = jp[k].moved(jloc)
    parts["_jig_local"] = jp

    meta = dict(y0=y0, n=(n.X, n.Y, n.Z), die_off=jig.DIE_OFF, axle=(axle.X, axle.Y, axle.Z),
                jig_start=jig.JIG_START_FROM_BB, u=(u.X, u.Y, u.Z), p0=(p0.X, p0.Y, p0.Z), up=(up.X, up.Y, up.Z))
    return parts, meta


def report(y0):
    g0, g1 = gaps(y0, False), gaps(y0, True)
    s0, m0 = min(g0, key=lambda t: t[1])
    print(f"stay centre at BB: +-{y0:.1f} mm")
    print(f"tightest tire gap original: {m0:.2f} mm at BB+{s0:.0f}")
    d = dict(g1)
    s1, m1 = min(g1, key=lambda t: t[1])
    print(f"same spot after bending: {d[s0]:.2f} mm; tightest after bending: {m1:.2f} mm at BB+{s1:.0f}")
    for s in (60, 80, 100, 120, 140, 160, 200, 260):
        k = min(range(len(g0)), key=lambda i: abs(g0[i][0] - s))
        print(f"  BB+{s:3d}: gap {g0[k][1]:6.2f} -> {g1[k][1]:6.2f}   stay moved {bike_offset(s, True):.2f}")
    return dict(orig_gap=m0, orig_at=s0, bent_gap_same=d[s0], bent_min=m1, bent_min_at=s1)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    parts, meta = build()
    meta.update(report(meta["y0"]))
    meta["tires"] = {}
    for tw in TIRE_SIZES:
        g0, g1 = gaps(meta["y0"], False, tw), gaps(meta["y0"], True, tw)
        s0, m0 = min(g0, key=lambda t: t[1])
        s1, m1 = min(g1, key=lambda t: t[1])
        meta["tires"][tw] = dict(before=round(m0, 1), at=round(s0), after=round(m1, 1))
        print(f"tire {tw}: tightest {m0:5.1f} at BB+{s0:.0f} -> after bending {m1:5.1f}")
    jl = parts.pop("_jig_local")
    for k in ("die_inner", "die_outer"):
        export_stl(jl[k], str(OUT.parent / f"{k}_fitted.stl"), tolerance=0.05, angular_tolerance=0.2)
        export_step(jl[k], str(OUT.parent / f"{k}_fitted.step"))
    for name, shp in parts.items():
        export_stl(shp, str(OUT / f"{name}.stl"), tolerance=0.1, angular_tolerance=0.3)
    import json
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    print("written to", OUT)
