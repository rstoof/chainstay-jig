"""Refresh viewer/index.html from ./out: embeds the STL files (base64) and the gap numbers.
Run after:  python build.py --export"""
import base64, json, re
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "out"
PAGE = ROOT / "viewer" / "index.html"


def blob(folder, names):
    return json.dumps({n: base64.b64encode((folder / f"{n}.stl").read_bytes()).decode() for n in names})


def main():
    s = PAGE.read_text()
    for id_, folder in (("parts-data", OUT), ("bike-data", OUT / "bike"), ("spreader-data", OUT / "spreader"), ("dial-data", OUT / "dial_view")):
        m = re.search(r'(<script type="application/json" id="%s">)(.*?)(</script>)' % id_, s, re.S)
        names = list(json.loads(m.group(2)))
        s = s[:m.start(2)] + blob(folder, names) + s[m.end(2):]
    meta = json.loads((OUT / "bike" / "meta.json").read_text())
    T, R = meta["tires"], meta["rings"]
    s = re.sub(r"const JIG_META = \{die_off: [\d.]+\};", "const JIG_META = {die_off: %.2f};" % meta["die_off"], s)
    s = re.sub(r"const RING_GAP = .*?;", "const RING_GAP = " + json.dumps(R) + ";", s, count=1)
    s = re.sub(r"const TIRE_GAP = .*?;", "const TIRE_GAP = " + json.dumps({k: v[:2] for k, v in T.items()}) + ";", s, count=1)
    f = lambda v: ("−%.1f" % -v) if v < 0 else "%.1f" % v
    ba = lambda d, k: f"{f(d[k][0])} → {f(d[k][1])}"
    s = re.sub(r"(<td>Tire to stay, before → after: 28 / 32 / 35</td><td>).*?(</td>)",
               lambda m: m.group(1) + " / ".join(ba(T, k) for k in ("28", "32", "35")) + m.group(2), s)
    s = re.sub(r"(<td>Tire to stay, before → after: 40 / 45</td><td>).*?(</td>)",
               lambda m: m.group(1) + " / ".join(ba(T, k) for k in ("40", "45")) + m.group(2), s)
    s = re.sub(r"(<td>Ring to stay, before → after: 40T / 52T</td><td>).*?(</td>)",
               lambda m: m.group(1) + " / ".join(ba(R, k) for k in ("40", "52")) + m.group(2), s)
    PAGE.write_text(s)
    print("written", PAGE, f"{PAGE.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
