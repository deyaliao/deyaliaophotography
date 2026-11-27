#!/usr/bin/env python3
"""
Build script for deyaliaophoto.com

Resizes the original photos into web-sized copies (and strips EXIF/GPS data),
then writes docs/assets/data.js, which the pages use to lay out photos.

Usage:
    python3 build.py            # only processes new/changed photos
    python3 build.py --force    # re-processes everything

Folders it reads:
    home/                 photos scattered on the home page
    galleries/<name>/     one folder per couple, e.g. "kyu + missa"
    deya.jpg, background.jpg   used on the about page

To pick a cover photo for a gallery, add it to COVERS below.
To change the order galleries appear in, edit GALLERY_ORDER.
"""
import json

import numpy as np
import os
import math
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps, ImageStat

ROOT = Path(__file__).parent
SITE = ROOT / "docs"
OUT = SITE / "img"

SIZES = {"sm": 700, "md": 1100, "lg": 2000}  # long edge, in px
QUALITY = 80

# Optional: choose the cover photo for each gallery (filename inside the folder).
# If a gallery isn't listed, the first photo is used.
COVERS = {
    "caitlin + dane": "DSC01100.jpg",
    "christian + linh": "_DSC7543.jpg",
    "kyu + missa": "_DSC1083.jpg",
    "meghan + marco": "000005860029.jpg",
    "vic + dan": "DSC00096.jpg",
}

# Label shown on the right under each gallery cover.
GALLERY_TYPES = {
    "caitlin + dane": "couples",
    "christian + linh": "engagement",
    "kyu + missa": "engagement",
    "meghan + marco": "elopement",
    "vic + dan": "couples",
}

# Location shown under the gallery name on each gallery page.
GALLERY_LOCATIONS = {
    "caitlin + dane": "green lake park",
    "christian + linh": "brackett's landing north",
    "kyu + missa": "gas works park",
    "meghan + marco": "nyc city hall",
    "vic + dan": "seattle chinatown",
}

# Optional extra line under the location: (english, chinese).
GALLERY_NOTES = {
    "meghan + marco": ("digital + 35 mm film", "数码 + 35mm 胶片"),
}

# Optional: photos shown first (the top row) on a gallery page, in this order.
GALLERY_FIRST = {
    "christian + linh": ["_DSC7543.jpg", "_DSC7292.jpg", "_DSC7588.jpg", "_DSC7466.jpg"],
    "caitlin + dane": ["DSC00721.jpg", "DSC01216.jpg", "DSC01041.jpg", "DSC01301.jpg", "DSC01015.jpg"],
    "meghan + marco": ["_DSC9017.jpg", "000005860018.jpg", "_DSC8838.jpg", "000005860024.jpg"],
}

# Optional: photos that should appear near the top (within the next two rows after the
# GALLERY_FIRST photos). The build picks their exact spots so look-alikes stay apart.
GALLERY_EARLY = {
    "christian + linh": ["_DSC7384.jpg", "_DSC7279.jpg"],
}

# Optional: order of galleries. Unlisted galleries are appended alphabetically.
GALLERY_ORDER = ["caitlin + dane", "vic + dan", "kyu + missa", "meghan + marco", "christian + linh"]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def is_photo(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}


def process(job):
    src, dest_dir, stem, force = job
    dest_dir = Path(dest_dir)
    outputs = {k: dest_dir / f"{stem}-{k}.jpg" for k in SIZES}
    src_mtime = os.path.getmtime(src)
    if not force and all(o.exists() and os.path.getmtime(o) >= src_mtime for o in outputs.values()):
        with Image.open(outputs["md"]) as im:
            return src, im.size
    with Image.open(src) as im:
        im.draft("RGB", (SIZES["lg"], SIZES["lg"]))  # fast JPEG downscale on decode
        im = ImageOps.exif_transpose(im).convert("RGB")
        size_md = None
        for key, edge in sorted(SIZES.items(), key=lambda kv: -kv[1]):
            copy = im.copy()
            copy.thumbnail((edge, edge), Image.LANCZOS)
            # No exif passed -> location/camera metadata is stripped
            copy.save(outputs[key], "JPEG", quality=QUALITY, optimize=True, progressive=True)
            if key == "md":
                size_md = copy.size
    return src, size_md


def photo_entry(rel_dir: str, stem: str, size):
    w, h = size
    return {"src": f"img/{rel_dir}/{stem}", "w": w, "h": h}


# ---------- gallery arrangement ----------
# Photos of the same moment (e.g. a film shot and its digital twin) share almost the
# same colours. We arrange each gallery so look-alike photos never sit next to or
# directly under each other in the masonry columns, at any screen width.
def colour_sig(path):
    with Image.open(path) as im:
        im = im.convert("RGB").resize((48, 72)).convert("HSV")
        hist = [0.0] * 24
        for h, s, v in im.getdata():
            hist[h * 24 // 256] += (s / 255) * (v / 255)
    tot = sum(hist) or 1.0
    return np.sqrt(np.array(hist) / tot)


def shape_sig(path):
    """Small contrast-normalised greyscale thumbnails of the photo and of zoomed-in crops,
    so a film frame and a digital frame of the same moment match despite different framing."""
    with Image.open(path) as im:
        im = ImageOps.equalize(im.convert("L"))
        w, h = im.size
        size = (16, 24) if h >= w else (24, 16)
        out = []
        for s in (1.0, 0.88, 0.76):
            for fx in ((0.5,) if s == 1 else (0, 0.5, 1)):
                for fy in ((0.5,) if s == 1 else (0, 0.5, 1)):
                    x, y = (w - w * s) * fx, (h - h * s) * fy
                    c = im.crop((int(x), int(y), int(x + w * s), int(y + h * s))).resize(size, Image.BILINEAR)
                    v = np.asarray(c, dtype=np.float32).ravel()
                    v = (v - v.mean()) / (v.std() + 1e-6)
                    out.append(v / np.sqrt(v.size))
    return h >= w, np.stack(out)


def is_black_and_white(path):
    with Image.open(path) as im:
        return ImageStat.Stat(im.convert("RGB").resize((60, 90)).convert("HSV")).mean[1] < 3


def lookalike_matrix(paths):
    """Higher = more alike. Mixes colour palette and composition, each scored relative to the gallery."""
    n = len(paths)
    col = np.stack([colour_sig(p) for p in paths])
    colour = col @ col.T
    shapes = [shape_sig(p) for p in paths]
    shape = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(i + 1, n):
            if shapes[i][0] == shapes[j][0]:      # only compare photos of the same orientation
                a, b = shapes[i][1], shapes[j][1]
                shape[i, j] = shape[j, i] = max((a[:1] @ b.T).max(), (b[:1] @ a.T).max())
    iu = np.triu_indices(n, 1)
    ok = ~np.isnan(shape[iu])
    if ok.sum() < 2:
        return np.zeros((n, n))
    def z(m):
        v = m[iu][ok]
        return (m - v.mean()) / (v.std() + 1e-9)
    zs = z(shape)
    # a very close composition counts on its own (catches black & white versions of colour shots)
    return np.nan_to_num(np.maximum(zs + z(colour), zs), nan=-9.0)


def spread_order(n):
    """Fixed big-stride order so shots taken back to back end up far apart."""
    if n < 4:
        return list(range(n))
    step = round(n * 0.382)
    while math.gcd(step, n) != 1:
        step += 1
    return [(i * step) % n for i in range(n)]


GAP, SLACK = 0.05, 0.1
LOOKALIKE = 2.3        # how alike two photos must be before they are kept apart (higher = stricter)


def neighbours(order, ratios):
    """Pairs of positions that touch in the gallery layout at 1-4 columns.
    Mirrors main.js: each photo goes into the currently shortest column (leftmost on ties)."""
    pairs = set()
    for cols in (1, 2, 3, 4):
        heights = [0.0] * cols
        last = [None] * cols
        placed = []
        for pos, i in enumerate(order):
            c = heights.index(min(heights))
            top = heights[c]
            heights[c] += ratios[i] + GAP
            placed.append((c, top, heights[c]))
            if last[c] is not None:
                pairs.add((last[c], pos))
            last[c] = pos
        for x in range(len(order)):
            cx, tx, bx = placed[x]
            for y in range(x + 1, len(order)):
                cy, ty, by = placed[y]
                if abs(cx - cy) == 1 and ty < bx + SLACK and tx < by + SLACK:
                    pairs.add((x, y))
    return pairs


def arrange(paths, ratios, pinned=(), early=()):
    """pinned: indexes of photos that must come first, in that order (the top row).
    early: indexes of photos that must land somewhere in the next two rows."""
    n = len(paths)
    sim = lookalike_matrix(paths).tolist()
    thr = LOOKALIKE
    def cost(order):
        return sum(max(0.0, sim[order[a]][order[b]] - thr) for a, b in neighbours(order, ratios))
    k = len(pinned)
    # black & white photos are spread evenly through the gallery (starting near the top)
    # instead of wherever they happen to land; colour photos fill the other spots
    bw = [is_black_and_white(p) for p in paths]
    early = [i for i in early if i not in pinned]
    window = len(pinned) + max(8, len(early))          # early photos must stay before this position
    rest = list(early) + [i for i in spread_order(n) if i not in pinned and i not in early]
    mono, colour = [i for i in rest if bw[i]], [i for i in rest if not bw[i]]
    slots = {k + 2 + round(j * (len(rest) - 2) / len(mono)) for j in range(len(mono))} if mono else set()
    def start(shift):
        m = mono[shift % len(mono):] + mono[:shift % len(mono)] if mono else []
        e = [i for i in colour if i in early]
        cr = [i for i in colour if i not in early]
        c = e + (cr[shift % len(cr):] + cr[:shift % len(cr)] if cr else [])
        order = list(pinned)
        for pos in range(k, n):
            order.append(m.pop(0) if (pos in slots and m) or not c else c.pop(0))
        return order

    def improve(order):
        best = cost(order)
        for _ in range(40):
            improved = False
            bad = sorted({x for a, b in neighbours(order, ratios) if sim[order[a]][order[b]] > thr for x in (a, b)})
            for a in bad:
                if a < k:
                    continue
                for b in range(k, n):
                    if a == b or bw[order[a]] != bw[order[b]]:   # only swap like with like
                        continue
                    if (order[a] in early and b >= window) or (order[b] in early and a >= window):
                        continue                                   # keep "early" photos near the top
                    order[a], order[b] = order[b], order[a]
                    c = cost(order)
                    if c < best - 1e-9:
                        best, improved = c, True
                        break                      # keep this swap, move on to the next bad photo
                    order[a], order[b] = order[b], order[a]
            if not improved:
                break
        return best, order

    # if look-alikes still touch, retry from a few different starting orders and keep the best
    best, order = improve(start(0))
    for shift in (3, 7, 11, 17, 23):
        if best <= 0:
            break
        c, o = improve(start(shift))
        if c < best:
            best, order = c, o
    return order


# home photos that should never open the page (kept out of the top row)
HOME_NOT_FIRST = {"j.jpg", "_DSC1200.jpg", "_DSC7639.jpg", "c.jpg", "_DSC8886.jpg", "_DSC7312.jpg", "_DSC8730.jpg"}


def main():
    force = "--force" in sys.argv
    jobs, plan = [], []

    def queue(src: Path, rel_dir: str, stem: str):
        d = OUT / rel_dir
        d.mkdir(parents=True, exist_ok=True)
        jobs.append((str(src), str(d), stem, force))
        plan.append((str(src), rel_dir, stem))

    for p in sorted((ROOT / "home").iterdir()):
        if is_photo(p):
            queue(p, "home", slugify(p.stem))

    if (ROOT / "travels").is_dir():
        for p in sorted((ROOT / "travels").iterdir()):
            if is_photo(p):
                queue(p, "travels", slugify(p.stem))

    galleries = [d for d in (ROOT / "galleries").iterdir() if d.is_dir()]
    order = {n: i for i, n in enumerate(GALLERY_ORDER)}
    galleries.sort(key=lambda d: (order.get(d.name, 999), d.name))
    for g in galleries:
        for p in sorted(g.iterdir()):
            if is_photo(p):
                queue(p, f"galleries/{slugify(g.name)}", slugify(p.stem))

    for name in ("deya.jpg", "background.jpg"):
        if (ROOT / name).exists():
            queue(ROOT / name, "about", slugify(Path(name).stem))

    print(f"Processing {len(jobs)} photos...")
    sizes = {}
    with ProcessPoolExecutor() as pool:
        for i, (src, size) in enumerate(pool.map(process, jobs, chunksize=4), 1):
            sizes[src] = size
            if i % 25 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)}")

    data = {"home": [], "travels": [], "galleries": [], "about": {}}
    by_dir = {}
    for src, rel_dir, stem in plan:
        by_dir.setdefault(rel_dir, []).append((Path(src).name, photo_entry(rel_dir, stem, sizes[src])))

    data["home"] = [dict(e, notfirst=True) if n in HOME_NOT_FIRST else e for n, e in by_dir.get("home", [])]
    data["travels"] = [e for _, e in by_dir.get("travels", [])]
    data["about"] = {Path(n).stem: e for n, e in by_dir.get("about", [])}
    for g in galleries:
        items = by_dir.get(f"galleries/{slugify(g.name)}", [])
        if not items:
            continue
        cover_name = COVERS.get(g.name)
        cover = next((e for n, e in items if n == cover_name), items[0][1])
        data["galleries"].append({
            "slug": slugify(g.name),
            "name": g.name,
            "type": GALLERY_TYPES.get(g.name, ""),
            "location": GALLERY_LOCATIONS.get(g.name, ""),
            "cover": cover,
            "note": GALLERY_NOTES.get(g.name, ("", ""))[0],
            "note_zh": GALLERY_NOTES.get(g.name, ("", ""))[1],
            "photos": [items[i][1] for i in arrange(
                [OUT / f"galleries/{slugify(g.name)}" / f"{slugify(Path(n).stem)}-md.jpg" for n, _ in items],
                [e["h"] / e["w"] for _, e in items],
                [next(i for i, (n, _) in enumerate(items) if n == f) for f in GALLERY_FIRST.get(g.name, [])
                 if any(n == f for n, _ in items)],
                [next(i for i, (n, _) in enumerate(items) if n == f) for f in GALLERY_EARLY.get(g.name, [])
                 if any(n == f for n, _ in items)])],
        })

    # remove web copies of photos that were deleted from the source folders
    keep = {OUT / rel_dir / f"{stem}-{k}.jpg" for _, rel_dir, stem in plan for k in SIZES}
    removed = [f for f in OUT.rglob("*.jpg") if f not in keep]
    for f in removed:
        f.unlink()
    if removed:
        print(f"Removed {len(removed) // len(SIZES)} deleted photo(s)")

    js = "// Generated by build.py. Do not edit by hand.\nwindow.SITE_DATA = " + json.dumps(data, indent=1) + ";\n"
    (SITE / "assets" / "data.js").write_text(js)
    print("Wrote docs/assets/data.js")
    stamp_assets()


def stamp_assets():
    """Add ?v=<hash> to css/js links so browsers fetch fresh copies after changes."""
    import hashlib
    for html in SITE.glob("*.html"):
        text = html.read_text()
        for asset in ("assets/style.css", "assets/data.js", "assets/main.js"):
            digest = hashlib.md5((SITE / asset).read_bytes()).hexdigest()[:8]
            text = re.sub(re.escape(asset) + r'(\?v=[0-9a-f]+)?"', f'{asset}?v={digest}"', text)
        html.write_text(text)
    print("Updated asset versions in pages")


if __name__ == "__main__":
    main()
