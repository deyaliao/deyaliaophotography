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
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).parent
SITE = ROOT / "docs"
OUT = SITE / "img"

SIZES = {"md": 1100, "lg": 2000}  # long edge, in px
QUALITY = 80

# Optional: choose the cover photo for each gallery (filename inside the folder).
# If a gallery isn't listed, the first photo is used.
COVERS = {
    "caitlin + dane": "DSC01100.jpg",
    "christian + linh": "_DSC7334.jpg",
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

    data["home"] = [e for _, e in by_dir.get("home", [])]
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
            "photos": [e for _, e in items],
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
