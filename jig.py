"""
Chainstay bending jig for a Raleigh Record Sprint (lugged BB, Reynolds 501).
Measured: lug length, lug OD, stay sections at the lug and 50 mm on, dimple position.
Still estimated: stay sections beyond 50 mm from the lug, rub point, chainstay length.

Coordinates (jig local):
  X  along the chainstay, x=0 is the end of the chainstay lug (the jig butts against it)
  Y  lateral, +Y = outward (towards the chainring, drive side)
  Z  vertical

The two PPA-CF dies close on the stay along Y. Their mating face follows the
FINAL (overbent) centreline, so when the die faces touch the bend is done (hard stop).
  - inner die  (tire side, -Y)  pushes the stay outward
  - outer die  (crank side, +Y) holds the outside; the dimple is filled flush with putty
Comb fingers in top and bottom bands interlock the dies (alignment in X and Z).
Steel flat bar on both backs spreads the M8 bolt load.

Run:  python jig.py      -> writes STEP + STL files into ./out
"""
import math
from pathlib import Path
from build123d import *

# ---------------- stay cross-section (measured) ----------------
# (jig x from the lug end, width Y, height Z). Linear in between, held constant outside.
SECTIONS = [               # remeasured on the bike with the section gauges
    (0.0, 22.4, 22.0),    # where the stay leaves the lug
    (25.0, 19.2, 25.0),
    (50.0, 18.2, 25.8),   # calipers bridge the dimple
    (75.0, 17.8, 24.7),
    (100.0, 17.8, 23.6),
    (125.0, 17.5, 22.4),
    (150.0, 17.4, 21.2),  # dropout end of the die
]
CLR = 0.2            # total clearance on the tube cavity (gauges at +0.2 slid on loose-ish)


def sec(x):
    """Stay (width, height) at jig x."""
    if x <= SECTIONS[0][0]:
        return SECTIONS[0][1], SECTIONS[0][2]
    for (x0, w0, h0), (x1, w1, h1) in zip(SECTIONS, SECTIONS[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return w0 + (w1 - w0) * t, h0 + (h1 - h0) * t
    return SECTIONS[-1][1], SECTIONS[-1][2]


W_MAX = max(w for _, w, _ in SECTIONS)
H_MAX = max(h for _, _, h in SECTIONS)

L = 150.0            # jig length along the stay
H = 74.0             # die height (Z): room for the Ø24 washers at the +-24 bolt rows
BAND = 6.0           # thickness (Z) of the finger band right above / below the stay
BAND_GAP = 0.0       # flat finger faces level with the stay top; the cavity (CLR/2) cuts a 0.1 groove into them - keep CLR/2 - BAND_GAP > 0 (coincident faces break the booleans)
FINGER = 12.0        # finger reach past the split face: covers the stay top even with the jig open
FINGER_W = 10.0      # finger width along X (pitch = 2x)
FCLR = 0.3           # finger side clearance
FCHAMF = 1.0         # lead-in chamfer on both side corners of each finger tip (X)
ZCHAMF = 0.9         # lead-in chamfer on the tip edge away from the stay (Z)
WALL = 18.0          # PPA behind the tube. No steel bars: the die itself spans from the bolt rows to the stay

CLEAR_NEEDED = 4.0   # extra tire clearance wanted on the bike, per side (mm)
RUB_FROM_LUG = 57.0  # measured: tire rubs 57 mm after the end of the lug
OVERBEND = 1.25      # springback guess: die bends this much further than wanted

BB_SHELL_OD = 38.1   # lugged English shell
LUG_LEN = 10.8       # chainstay lug sticks out this far from the shell (measured)
JIG_START_FROM_BB = BB_SHELL_OD / 2 + LUG_LEN   # x=0 of jig = lug end, from BB centre
DIMPLE = (18.0, 78.0)   # measured: starts 18 mm after the lug, 60 mm long - NOT bent
DIMPLE_DEPTH = 10.0     # measured
DIMPLE_DEEPEST = 33.0   # deepest point, from the dimple start (past the middle, towards the dropout)
CLEAR_AT_BB = JIG_START_FROM_BB + RUB_FROM_LUG
BEND1 = (12.0, 32.0)    # outward kink centred 22 mm from the lug: runs into the putty-filled
                        # start of the dimple, so it is not right at the brazed lug
BEND2 = (82.0, 100.0)   # single inward kink, just after the dimple
DROPOUT_FROM_BB = 420.0   # chainstay length

WASHER_T = 2.0       # DIN 9021 M8 washer (Ø24) under every head and nut, straight on the PPA
WASHER_D = 24.0
BOLT_X = (49.0, 92.0, 135.0)   # pairs at +-BOLT_Z
BOLT_Z = 24.0        # bolt rows at +-BOLT_Z, outside the finger bands
# extra bolts in the BB-end corners, next to bend 1 (x, z, washer Ø). The top one sits
# close to the seat tube: a plain DIN 125 Ø16 washer clears it, a Ø24 one just touches.
CORNER_BOLTS = ((12.0, -BOLT_Z, 24.0), (12.0, BOLT_Z, 16.0))
BOLTS = tuple((x, z, WASHER_D) for x in BOLT_X for z in (-BOLT_Z, BOLT_Z)) + CORNER_BOLTS
BOLT_D = 8.5         # M8 clearance
BOLT_LEN = 100.0
NUT_H = 6.5
HEAD_H = 5.3
HEX_AF = 13.0

OUT = Path(__file__).parent / "out"

# ---------------- centreline ----------------
# Two single kinks: the stay angles outward at bend 1, runs straight (and slightly
# angled) past the dimple, then angles back inward at bend 2 so it meets the fixed
# dropout. Built by integrating a slope that ramps linearly through each bend zone
# (= constant curvature arcs), then scaled so the max offset equals `off`.
_X1C = 0.5 * (BEND1[0] + BEND1[1])
_X2C = 0.5 * (BEND2[0] + BEND2[1])
_DROP = DROPOUT_FROM_BB - JIG_START_FROM_BB   # dropout in jig coordinates
_S1 = 1.0 / (_X2C - _X1C)                      # slope past the dimple (unit offset)
_S2 = -1.0 / (_DROP - _X2C)                    # slope towards the dropout


def _ramp(x, a, b):
    return min(1.0, max(0.0, (x - a) / (b - a)))


def _slope(x):
    return _S1 * _ramp(x, *BEND1) + (_S2 - _S1) * _ramp(x, *BEND2)


_DX = 0.05
_X0 = -60.0
_GRID = [0.0]
for _i in range(int((L + 120) / _DX)):
    _x = _X0 + _i * _DX
    _GRID.append(_GRID[-1] + 0.5 * (_slope(_x) + _slope(_x + _DX)) * _DX)
_PEAK = max(_GRID)


def _unit(x):
    f = (x - _X0) / _DX
    i = max(0, min(len(_GRID) - 2, int(f)))
    t = f - i
    return (_GRID[i] * (1 - t) + _GRID[i + 1] * t) / _PEAK


# die offset at its peak (bend 2) so the clearance point gets CLEAR_NEEDED after springback
DIE_OFF = CLEAR_NEEDED * OVERBEND / _unit(CLEAR_AT_BB - JIG_START_FROM_BB)


def yc(x, off=None):
    """Die centreline y at x, max outward offset = off (default DIE_OFF)."""
    off = DIE_OFF if off is None else off
    f = (x - _X0) / _DX
    i = max(0, min(len(_GRID) - 2, int(f)))
    t = f - i
    return off * (_GRID[i] * (1 - t) + _GRID[i + 1] * t) / _PEAK


SLOPE = DIE_OFF * _S2 / _PEAK


def xs(a, b, step=1.0):
    n = max(1, int(math.ceil((b - a) / step)))
    return [a + (b - a) * i / n for i in range(n + 1)]


Y_IN_BACK = -(W_MAX / 2 + CLR / 2 + WALL)
Y_OUT_BACK = DIE_OFF + W_MAX / 2 + CLR / 2 + WALL


def roof(x):
    """Flat finger faces sit here: just above the local stay top."""
    return sec(x)[1] / 2 + BAND_GAP


Z_BAND_TOP = H_MAX / 2 + BAND_GAP + BAND


def _clean(pts):
    out = []
    for q in pts:
        if not out or abs(q[0] - out[-1][0]) + abs(q[1] - out[-1][1]) > 1e-6:
            out.append(q)
    return out


def band(back_y, which, z0, z1):
    """Finger band between z0 (stay side) and z1, tips chamfered by ZCHAMF at z1."""
    def face(pull, z):
        o, i = band_fronts(pull)
        pts = _clean((o if which == "outer" else i) + [(L, back_y), (0, back_y)])
        return Pos(0, 0, z) * make_face(Polyline(*pts, close=True))
    zm = z1 - ZCHAMF
    lower = prism(_clean((band_fronts()[0] if which == "outer" else band_fronts()[1]) + [(L, back_y), (0, back_y)]), z0, zm)
    return lower + loft([face(0.0, zm), face(ZCHAMF, z1)], ruled=True)


def prism(pts, z0, z1):
    """Extrude a closed XY polygon between z0 and z1."""
    clean = []
    for q in pts:
        if not clean or abs(q[0] - clean[-1][0]) + abs(q[1] - clean[-1][1]) > 1e-6:
            clean.append(q)
    pts = clean
    face = make_face(Polyline(*pts, close=True))
    return Pos(0, 0, z0) * extrude(face, amount=z1 - z0, dir=(0, 0, 1))


def front(x0, x1, dy):
    return [(x, yc(x) + dy) for x in xs(x0, x1)]


def tipfront(x0, x1, dy, n=8):
    """Finger tip line with a fixed point count (so chamfer layers can be lofted)."""
    return [(x0 + (x1 - x0) * k / n, yc(x0 + (x1 - x0) * k / n) + dy) for k in range(n + 1)]


def band_fronts(pull=0.0):
    """Stepped split lines for the comb band: (outer_front_pts, inner_front_pts).
    pull shortens the finger tips (used for the Z chamfer layer)."""
    o, i = [], []
    n = int(round(L / FINGER_W))
    for k in range(n):
        a, b = k * FINGER_W, (k + 1) * FINGER_W
        outer_tooth = (k % 2 == 0)
        # outer die front
        a1, b1, c = a + FCLR, b - FCLR, FCHAMF
        if outer_tooth:
            o += (front(a, a1, FINGER + 1) + [(a1, yc(a1) - FINGER + c)]
                  + tipfront(a1 + c - pull, b1 - c + pull, -FINGER + pull) + [(b1, yc(b1) - FINGER + c)] + front(b1, b, FINGER + 1))
            i += front(a, b, -FINGER - 1)
        else:
            o += front(a, b, FINGER + 1)
            i += (front(a, a1, -FINGER - 1) + [(a1, yc(a1) + FINGER - c)]
                  + tipfront(a1 + c - pull, b1 - c + pull, FINGER - pull) + [(b1, yc(b1) + FINGER - c)] + front(b1, b, -FINGER - 1))
    return o, i


def tube_sweep(grow, off, x0=-10.0, x1=L + 10.0, step=5.0):
    """Stay (or cavity, grow = clearance) along the die centreline, following SECTIONS."""
    xs_ = xs(x0, x1, step)
    path = Spline(*[(x, yc(x, off), 0) for x in xs_])
    wires = []
    for x in xs_:
        pt = Vector(x, yc(x, off), 0)
        t = path.tangent_at(path.param_at_point(pt))
        plane = Plane(origin=pt, x_dir=(-t.Y, t.X, 0), z_dir=t)
        w, h = sec(x)
        w, h = w + grow, h + grow
        # periodic spline profile with the seam at 37 deg, so no edge of the surface
        # lies on the die split face (OCC boolean trouble)
        pts = [(w / 2 * math.cos(a), h / 2 * math.sin(a)) for a in (math.radians(37 + 15 * i) for i in range(24))]
        wires.append(plane * Spline(*pts, periodic=True))
    return loft([make_face(Wire([w])) for w in wires])


def dimple_shape():
    """Dimple dent, origin at its deepest point on the outer face, X along the stay.
    Measured length and depth; height (Z) is a guess."""
    a1 = DIMPLE_DEEPEST
    a2 = (DIMPLE[1] - DIMPLE[0]) - DIMPLE_DEEPEST
    ball = Rot(0, 90, 0) * Sphere(1)   # poles along X, so the x=0 cut runs along the equator
    front = scale(ball, (a1, DIMPLE_DEPTH, 9)) & Pos(-a1, 0, 0) * Box(2 * a1, 40, 40)
    back = scale(ball, (a2, DIMPLE_DEPTH, 9)) & Pos(a2, 0, 0) * Box(2 * a2, 40, 40)
    return front + back


def _xz_region(pts):
    """Solid spanning all Y from a closed polygon in the XZ plane."""
    face = make_face(Polyline(*[(x, -100, z) for x, z in pts], close=True))
    return extrude(face, amount=200, dir=(0, 1, 0))


def build():
    # z layout: [cavity zone | finger band (supports top/bottom of the stay) | plain body with bolts]
    # the finger faces follow the measured stay height (roof), the band top is flat
    zf = Z_BAND_TOP
    rx = xs(-1, L + 1, 2.0)
    below_roof = _xz_region([(x, roof(x)) for x in rx] + [(L + 1, -50), (-1, -50)])
    between = below_roof & below_roof.mirror(Plane.XY)
    main_outer = [(x, yc(x)) for x in xs(0, L)] + [(L, Y_OUT_BACK), (0, Y_OUT_BACK)]
    main_inner = [(x, yc(x)) for x in xs(0, L)] + [(L, Y_IN_BACK), (0, Y_IN_BACK)]
    bo, bi = band_fronts()
    band_outer = bo + [(L, Y_OUT_BACK), (0, Y_OUT_BACK)]
    band_inner = bi + [(L, Y_IN_BACK), (0, Y_IN_BACK)]

    z_lo = min(roof(x) for x in rx) - 1
    bands_o = band(Y_OUT_BACK, "outer", z_lo, zf) - below_roof
    bands_i = band(Y_IN_BACK, "inner", z_lo, zf) - below_roof
    outer = ((prism(main_outer, -zf, zf) & between) + bands_o + bands_o.mirror(Plane.XY)
             + prism(main_outer, zf, H / 2) + prism(main_outer, -H / 2, -zf))
    inner = ((prism(main_inner, -zf, zf) & between) + bands_i + bands_i.mirror(Plane.XY)
             + prism(main_inner, zf, H / 2) + prism(main_inner, -H / 2, -zf))

    cavity = tube_sweep(CLR, DIE_OFF)
    outer -= cavity
    inner -= cavity

    # no pocket: the dimple is filled flush with epoxy putty on the real stay
    # (cling film between), so the smooth cavity wall supports it 1:1
    # the dimple section is straight but angled outward, so tilt the shapes with it
    xm = DIMPLE[0] + DIMPLE_DEEPEST
    ang = math.degrees(math.atan((yc(xm + 1) - yc(xm - 1)) / 2))
    yd = yc(xm) + sec(xm)[0] / 2
    tilt = Pos(xm, yd, 0) * Rot(0, 0, ang)
    dimple = tilt * dimple_shape()
    env_final = tube_sweep(0.0, DIE_OFF, -40, L + 40)
    tube_final = env_final - dimple
    tube_straight = tube_sweep(0.0, 0.0, -40, L + 40) - Pos(xm, sec(xm)[0] / 2, 0) * dimple_shape()
    putty = dimple & env_final   # flush fill of the dimple

    # bolt holes
    for bx, bz, _ in BOLTS:
        hole = Pos(bx, 0, bz) * Rot(90, 0, 0) * Cylinder(BOLT_D / 2, 200)
        outer -= hole
        inner -= hole

    def washers(y0):
        ring = lambda d: Cylinder(d / 2, WASHER_T) - Cylinder(BOLT_D / 2, WASHER_T + 1)
        return Compound([Pos(bx, y0 + WASHER_T / 2, bz) * Rot(90, 0, 0) * ring(wd) for bx, bz, wd in BOLTS])

    washers_in = washers(Y_IN_BACK - WASHER_T)
    washers_out = washers(Y_OUT_BACK)

    # hardware (closed state): head on the tire side, nut on the crank side
    y_head = Y_IN_BACK - WASHER_T
    y_nut = Y_OUT_BACK + WASHER_T
    bolts, nuts = [], []
    for bx, bz, _ in BOLTS:
        head = Pos(bx, y_head - HEAD_H / 2, bz) * Rot(90, 0, 0) * extrude(
            RegularPolygon(HEX_AF / math.sqrt(3), 6), HEAD_H / 2, both=True)
        shank = Pos(bx, y_head + BOLT_LEN / 2, bz) * Rot(90, 0, 0) * Cylinder(4, BOLT_LEN)
        bolts.append(head + shank)
        nut = Pos(bx, y_nut + NUT_H / 2, bz) * Rot(90, 0, 0) * (
            extrude(RegularPolygon(HEX_AF / math.sqrt(3), 6), NUT_H / 2, both=True) - Cylinder(4, 20))
        nuts.append(nut)

    return dict(
        die_outer=outer, die_inner=inner, washers_inner=washers_in, washers_outer=washers_out,
        putty=putty, tube_final=tube_final, tube_straight=tube_straight,
        bolts=Compound(bolts), nuts=Compound(nuts),
    )


def report():
    closed = (Y_OUT_BACK - Y_IN_BACK) + 2 * WASHER_T + NUT_H
    xc = CLEAR_AT_BB - JIG_START_FROM_BB
    print(f"at BB+{CLEAR_AT_BB:.0f}: die {yc(xc):.2f} mm -> bike ~{yc(xc) / OVERBEND:.2f} mm")
    print(f"die offset peak (incl. overbend): {DIE_OFF:.2f} mm, bike ~{DIE_OFF / OVERBEND:.2f} mm, return slope {math.degrees(math.atan(SLOPE)):.2f} deg")
    a1 = math.degrees(math.atan(DIE_OFF * _S1 / _PEAK))
    a2 = a1 + math.degrees(math.atan(-SLOPE))
    print(f"bend 1: {a1:.1f} deg out, bend 2: {a2:.1f} deg in")
    for x in (0, BEND1[1], DIMPLE[0], DIMPLE[1], _X2C, L):
        print(f"  offset at x={x:5.1f} (BB+{x + JIG_START_FROM_BB:5.1f}): {yc(x):.2f}")
    print(f"bolt grip closed {closed:.1f} mm, open {closed + DIE_OFF:.1f} mm  (bolt {BOLT_LEN})")
    print(f"inner stack (tire side) from tube centre: {-Y_IN_BACK + WASHER_T + HEAD_H:.1f} mm")
    print(f"bolts: {len(BOLTS)}  die thickness, inner / outer: {-Y_IN_BACK:.1f} / {Y_OUT_BACK:.1f}")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    report()
    parts = build()
    for name, shp in parts.items():
        export_stl(shp, str(OUT / f"{name}.stl"), tolerance=0.05, angular_tolerance=0.2)
    export_step(Compound([parts[k] for k in ("die_outer", "die_inner", "washers_inner", "washers_outer", "putty")]),
                str(OUT / "jig_assembly.step"))
    export_step(parts["die_outer"], str(OUT / "die_outer.step"))
    export_step(parts["die_inner"], str(OUT / "die_inner.step"))
    print("written to", OUT)
