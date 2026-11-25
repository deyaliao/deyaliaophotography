# deyaliaophoto.com

A plain static site: HTML, CSS and a little JavaScript, with no framework. Everything that gets published lives in `docs/`.

```
home/            original photos for the home page          (not published)
galleries/<x>/   one folder per couple, original photos     (not published)
deya.jpg, background.jpg   about-page photos                (not published)
build.py         makes web-sized copies -> docs/img + docs/assets/data.js
docs/            the website (this is what GitHub Pages serves)
  index.html  galleries.html  gallery.html  packages.html  contact.html  about.html
  assets/style.css  assets/main.js  assets/data.js
```

## Adding or changing photos

1. Drop photos into `home/`, or into a new or existing folder in `galleries/` (the folder name becomes the gallery title, e.g. `anna + ben`).
2. Run `python3 build.py`. It resizes each photo to 1100px and 2000px versions and strips location/camera data.
3. Optional: pick a gallery's cover photo or the gallery order in `COVERS` / `GALLERY_ORDER` at the top of `build.py`.
4. Commit and push. The site updates in about a minute.

Package photos and the contact-page photo are set directly in `packages.html` and `contact.html` (search for `img/home/`).

## Preview locally

```
cd docs && python3 -m http.server 8000
```
Then open http://localhost:8000.

## Contact form (Formspree)

1. In Formspree, create a new form that sends to your email and copy its ID (the part after `/f/`).
2. In `docs/contact.html`, replace `YOUR_FORM_ID` in `action="https://formspree.io/f/YOUR_FORM_ID"`.
3. In the Formspree form settings, add `deyaliaophoto.com` under allowed domains.

The form submits in the background: visitors never leave the site and see a "thank you, <name>!" message. Each email's subject reads like "New wedding inquiry: Anna Lee & Ben Park", and Reply goes straight to the couple.

## Deploying (GitHub Pages + your domain)

1. Create a **new** GitHub repo, e.g. `deyaliaophotography`. Your existing portfolio site can stay where it is.
2. From this folder:
   ```
   git init && git add . && git commit -m "Launch site"
   git branch -M main
   git remote add origin https://github.com/<you>/deyaliaophotography.git
   git push -u origin main
   ```
3. In the repo, open Settings → Pages → Source: *Deploy from a branch*, then pick `main` and `/docs`.
4. Custom domain: `deyaliaophoto.com` (`docs/CNAME` already contains it). Tick **Enforce HTTPS** once it becomes available.
5. At your domain registrar, add these DNS records:
   - `A` records for `@` → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `CNAME` for `www` → `<you>.github.io`

## English / Chinese

Every translatable element has its Chinese text in a `data-zh="..."` attribute right next to the English, so to edit wording, change both in the same tag. The en / cn toggle (bottom right) remembers each visitor's choice; first-time visitors whose browser is set to Chinese see Chinese automatically. Share `https://deyaliaophoto.com/?lang=zh` to open the site in Chinese. Gallery types (couples, engagement...) are translated in `TYPE_ZH` in `docs/assets/main.js`.
