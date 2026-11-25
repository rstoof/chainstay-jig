# Chainstay cold-set jig

A parametric, 3D-printable jig for cold-setting the chainstays of a lugged steel frame (a Raleigh Record Sprint, Reynolds 501). It moves the stays about 4 mm outward per side to make room for a wider tire in a 1x gravel conversion.

**3D viewer:** https://rstoof.github.io/chainstay-jig/viewer/ (source: [`viewer/index.html`](viewer/index.html)). Open it in a browser to see the jig on the bike, before and after bending, with selectable tire (28–45 mm) and chainring (40–52T) sizes.

## How it works

- **Dies:** two printed dies (PPA-CF) clamp the stay and are split along the *final* (overbent) centreline. When the die faces touch, the bend is done, so the dies are their own hard stop.
- **Bends:** an outward kink near the BB (centred 22 mm from the lug) and an inward kink after the dimple. The dimple on the drive side is filled flush with epoxy putty and held straight.
- **Fingers:** interlocking fingers above and below the stay keep the dies aligned and support the stay top and bottom against buckling.
- **Clamping:** eight M8×100 fully threaded bolts with big washers (DIN 9021 Ø24) straight on 18 mm thick PPA die backs. There are no steel bars. Two of the bolts sit in the BB-end corners, next to the outward bend.
- **Fit:** the dies butt against the end of the chainstay lug and are trimmed to clear the BB, lugs, seat tube and the other stay, open or closed.

## Files

| Script | Does |
|---|---|
| `jig.py` | All parameters: measured stay sections, bend positions, overbend, fingers, bolts and washers. Builds the dies. |
| `scene.py` | Generic bike around it (BB, lugs, stays, wheel, tires, chainrings). Fits the dies to the frame. |
| `build.py` | Builds everything and runs the checks: validity, overlaps, collisions, tire and chainring gaps. `--export` writes `out/`. |
| `testfit.py` | Straight test-fit dies (no bend) to check the fit before printing the real ones. |
| `gauges.py` | Split-ring section gauges that clip on the stay to check the measured sections. |
| `make_3mf.py` | Orca Slicer project for the Qidi Q2: both dies on their backs, Siraya PPA-CF settings labelled as PAHT-CF, heated chamber and QIDI Box. Pass the Siraya Tech PPA-CF Q2 `.3mf`. |
| `make_viewer.py` | Embeds the exported STLs and numbers into `viewer/index.html`. |

The print-ready output is in `out/`:

- `die_inner_fitted.stl` and `die_outer_fitted.stl`: the real dies.
- `testfit/`: the straight test-fit dies.
- `gauges/`: the section gauges.
- Raw dies, washers, bolts and the bike scene.

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python build.py --export     # dies + bike scene + checks
python testfit.py            # straight test-fit dies
python gauges.py             # section gauges
python make_viewer.py        # refresh the viewer
```

## Workflow

1. Measure the stay, put the measurements in `SECTIONS` in `jig.py`, then print the gauges and check them on the bike.
2. Print the straight test-fit dies in PLA. They should close fully, butt against the lug, and the fingers should just touch the stay.
3. Print the real dies in PPA-CF, on their flat backs with no supports.
4. Bend: fill the dimple with putty, fit the bolts and washers, and tighten in a cross pattern until the dies bottom out. Start with the two corner bolts at the BB end.
5. Measure the springback and adjust `OVERBEND`. Try it on a scrap tube first.

## Status

- **Measured:** lug, stay sections (gauge-checked), dimple, rub point.
- **Still generic:** chainstay length, BB drop, rear spacing.
- **Guess:** the springback (`OVERBEND = 1.25`).

Cold-setting is at your own risk: steel frames only, and check dropout alignment and rear spacing afterwards.
