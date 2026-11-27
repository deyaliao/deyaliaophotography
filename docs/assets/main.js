/* deya liao photography — shared behaviour */
(function () {
  "use strict";
  var DATA = window.SITE_DATA || { home: [], galleries: [], about: {} };
  var MOBILE = window.matchMedia("(max-width: 760px)");

  /* ---------- language (en / cn) ---------- */
  var LANG = "en";
  try { LANG = localStorage.getItem("lang") || ""; } catch (e) {}
  var qlang = new URLSearchParams(location.search).get("lang");      // ?lang=zh / ?lang=en links
  if (qlang === "zh" || qlang === "en") { LANG = qlang; try { localStorage.setItem("lang", LANG); } catch (e) {} }
  if (LANG !== "en" && LANG !== "zh") LANG = /^zh/i.test(navigator.language || "") ? "zh" : "en";
  function T(en, zh) { return LANG === "zh" ? zh : en; }
  var TYPE_ZH = { couples: "情侣写真", engagement: "订婚照", elopement: "私奔婚礼", proposal: "求婚", wedding: "婚礼" };
  var thanksName = "";

  /* ---------- helpers ---------- */
  function $(sel, root) { return (root || document).querySelector(sel); }
  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === "class") n.className = attrs[k];
      else if (k === "text") n.textContent = attrs[k];
      else n.setAttribute(k, attrs[k]);
    }
    (children || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }
  function rng(seed) { // mulberry32
    return function () {
      seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function shuffle(arr, rand) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(rand() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  function img(photo, sizes, alt) {
    return el("img", {
      src: photo.src + "-md.jpg",
      // phones never need the 2000px version: cap them at 1100px
      srcset: photo.src + "-sm.jpg 700w, " + photo.src + "-md.jpg 1100w" + (MOBILE.matches ? "" : ", " + photo.src + "-lg.jpg 2000w"),
      sizes: sizes || "100vw",
      width: photo.w, height: photo.h,
      alt: alt || "", loading: "lazy", decoding: "async"
    });
  }

  // Fixed order that spreads photos out: photos are in shooting order (by filename),
  // so step through them by a large stride. Shots taken back-to-back end up far apart,
  // and the order is the same on every visit.
  function spread(list) {
    var n = list.length; if (n < 4) return list.slice();
    var gcd = function (a, b) { return b ? gcd(b, a % b) : a; };
    var step = Math.round(n * 0.382);
    while (gcd(step, n) !== 1) step++;
    var out = [];
    for (var i = 0; i < n; i++) out.push(list[(i * step) % n]);
    return out;
  }

  /* ---------- nav ---------- */
  var nav = $(".nav");
  if (nav) {
    var onScroll = function () { nav.classList.toggle("scrolled", window.scrollY > 8); };
    window.addEventListener("scroll", onScroll, { passive: true }); onScroll();
  }
  var menu = $(".mobile-menu");
  document.addEventListener("click", function (e) {
    if (!menu) return;
    if (e.target.closest(".menu-btn")) { menu.classList.add("open"); document.body.style.overflow = "hidden"; }
    else if (e.target.closest(".mobile-menu .close") || e.target.closest(".mobile-menu a")) { menu.classList.remove("open"); document.body.style.overflow = ""; }
  });

  /* ---------- reveal on scroll ---------- */
  var io = "IntersectionObserver" in window ? new IntersectionObserver(function (entries) {
    entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
  }, { rootMargin: "0px 0px -8% 0px" }) : null;
  function reveal(node) { node.classList.add("reveal"); if (io) io.observe(node); else node.classList.add("in"); }
  document.querySelectorAll("[data-reveal]").forEach(reveal);

  /* ---------- scattered layout ----------
     Photos are placed in loose rows: 1–3 per row, each with its own width,
     horizontal gap and vertical drop. Everything is in %, so it stays put on resize. */
  function scatter(container, items, render, opts) {
    opts = opts || {};
    var seed = opts.seed != null ? opts.seed : Math.floor(Math.random() * 1e9);
    var scale = opts.scale || 1;

    function build() {
      var rand = rng(seed), mobile = MOBILE.matches;
      container.innerHTML = "";
      var i = 0, last = 0;
      while (i < items.length) {
        var choices = mobile ? [1, 2, 2] : (opts.counts || [1, 2, 2, 3, 2, 3]);
        var count = choices[Math.floor(rand() * choices.length)];
        if (count === last && count === 1) count = 2;
        count = Math.min(count, items.length - i);
        var rowItems = items.slice(i, i + count);
        // landscape photos need more room: keep them off crowded rows
        var landscapes = rowItems.filter(function (p) { return (p.w || p.cover.w) > (p.h || p.cover.h); }).length;
        if (count === 3 && landscapes > 0 && !opts.three) { count = 2; rowItems = rowItems.slice(0, 2); }
        if (mobile && count === 2 && landscapes > 0) { count = 1; rowItems = rowItems.slice(0, 1); }
        last = count;

        var widths = rowItems.map(function (p) {
          var ph = p.cover || p, land = ph.w > ph.h, w;
          if (mobile) w = count === 1 ? (land ? .92 : .58 + rand() * .2) : .42 + rand() * .05;
          else if (count === 1) w = land ? .48 + rand() * .1 : .3 + rand() * .1;
          else if (count === 2) w = land ? .36 + rand() * .06 : .23 + rand() * .09;
          else if (opts.three) w = land ? .3 + rand() * .04 : .2 + rand() * .05;
          else w = .19 + rand() * .06;
          if (opts.fixed) w = opts.fixed;
          return Math.min(w * scale, mobile ? .94 : .62);
        });
        if (opts.tight && !mobile) widths = rowItems.map(function (p) { return p.w > p.h ? .37 + rand() * .03 : .24 + rand() * .03; });
        var used = widths.reduce(function (a, b) { return a + b; }, 0);
        if (used > .97) { widths = widths.map(function (w) { return w * .97 / used; }); used = .97; }
        var free = Math.max(0, 1 - used - .005);
        var weights = []; for (var k = 0; k <= count; k++) weights.push(.25 + rand());
        if (count === 1) weights = [rand() < .5 ? .3 + rand() : 1.2 + rand(), 1];
        if (opts.three) { var edge = .4 + rand() * .3; weights[0] = edge; weights[count] = edge; }  // same space at both ends
        var wsum = weights.reduce(function (a, b) { return a + b; }, 0);

        var row = el("div", { class: "row" });
        rowItems.forEach(function (p, j) {
          var node = render(p, i + j, Math.round(widths[j] * 100) + "vw");
          node.classList.add("item");
          node.style.width = (widths[j] * 100).toFixed(2) + "%";
          var ml = free * weights[j] / wsum;
          if (opts.tight && !mobile) ml = j === 0 ? (1 - used - (count - 1) * .01) / 2 : .01;   // centered, small even gaps
          node.style.marginLeft = (ml * 100).toFixed(2) + "%";
          var drop = i === 0 && mobile ? 0 : opts.tight ? rand() * .01 : j === 0 && count > 1 ? rand() * .02 : rand() * (mobile ? .12 : opts.three ? .04 : .09);
          node.style.marginTop = (drop * 100).toFixed(2) + "%";
          row.appendChild(node);
        });
        container.appendChild(row);
        Array.prototype.forEach.call(row.children, reveal);
        i += count;
      }
    }
    build();
    MOBILE.addEventListener ? MOBILE.addEventListener("change", build) : MOBILE.addListener(build);
  }

  /* ---------- staggered layout (galleries) ----------
     Equal-size covers alternating right/left; each one starts partway down the
     previous one, so the next gallery peeks up beside it. */
  function stagger(container, items, render) {
    var W = .28, CAP = 34, GAP = 48;                    // width as share of container; caption + gap in px
    var lefts = [.56, .1, .62, .16];                      // repeats: right, left, right, left
    container.style.position = "relative";
    var nodes = items.map(function (g, i) {
      var n = render(g); n.classList.add("item");
      n.style.position = "absolute"; n.style.width = (W * 100) + "%";
      n.style.left = (lefts[i % lefts.length] * 100) + "%";
      container.appendChild(n); reveal(n);
      return n;
    });
    function place() {
      var cw = container.clientWidth, tops = [], bottoms = [];
      items.forEach(function (g, i) {
        var h = cw * W * g.cover.h / g.cover.w;
        var t = 0;
        if (i > 0) t = tops[i - 1] + (bottoms[i - 1] - tops[i - 1]) * .45;     // peek up beside previous
        if (i > 1) t = Math.max(t, bottoms[i - 2] + GAP);                      // never overlap same side
        tops.push(t); bottoms.push(t + h + CAP);
        nodes[i].style.top = t + "px";
      });
      container.style.height = (Math.max.apply(null, bottoms.concat([0]))) + "px";
    }
    place();
    window.addEventListener("resize", place);
  }

  /* ---------- lightbox ---------- */
  var lb, lbImg, lbCount, lbList = [], lbIndex = 0;
  function openLightbox(list, index) {
    if (!lb) {
      lb = el("div", { class: "lightbox", role: "dialog", "aria-modal": "true", "aria-label": "Photo viewer" }, [
        lbImg = el("img", { alt: "" }),
        el("button", { class: "lb-close", text: T("close", "关闭"), "aria-label": "Close" }),
        el("button", { class: "lb-prev", text: "‹", "aria-label": "Previous photo" }),
        el("button", { class: "lb-next", text: "›", "aria-label": "Next photo" }),
        lbCount = el("div", { class: "lb-count" })
      ]);
      document.body.appendChild(lb);
      lb.addEventListener("click", function (e) {
        if (e.target.closest(".lb-prev")) step(-1);
        else if (e.target.closest(".lb-next")) step(1);
        else if (e.target === lb || e.target.closest(".lb-close")) closeLightbox();
      });
      document.addEventListener("keydown", function (e) {
        if (!lb.classList.contains("open")) return;
        if (e.key === "Escape") closeLightbox();
        if (e.key === "ArrowLeft") step(-1);
        if (e.key === "ArrowRight") step(1);
      });
      var x0 = null;
      lb.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; }, { passive: true });
      lb.addEventListener("touchend", function (e) {
        if (x0 === null) return;
        var dx = e.changedTouches[0].clientX - x0; x0 = null;
        if (Math.abs(dx) > 50) step(dx < 0 ? 1 : -1);
      });
    }
    lbList = list; lbIndex = index; show();
    lb.classList.add("open"); document.body.style.overflow = "hidden";
  }
  function show() {
    var p = lbList[lbIndex];
    var big = MOBILE.matches ? "-md.jpg" : "-lg.jpg";
    lbImg.src = p.src + big;
    lbCount.textContent = (lbIndex + 1) + " / " + lbList.length;
    [lbIndex - 1, lbIndex + 1].forEach(function (n) { // preload neighbours
      var q = lbList[(n + lbList.length) % lbList.length]; if (q) new Image().src = q.src + big;
    });
  }
  function step(d) { lbIndex = (lbIndex + d + lbList.length) % lbList.length; show(); }
  function closeLightbox() { lb.classList.remove("open"); document.body.style.overflow = ""; }

  /* ---------- home ---------- */
  var home = $("#home-scatter");
  if (home) {
    var photos = shuffle(DATA.home, rng(Math.floor(Math.random() * 1e9)));
    // some photos shouldn't open the page: swap them out of the top row
    for (var a = 0, b = 3; a < 3 && a < photos.length; a++) {
      if (!photos[a].notfirst) continue;
      while (b < photos.length && photos[b].notfirst) b++;
      if (b >= photos.length) break;
      var t = photos[a]; photos[a] = photos[b]; photos[b] = t; b++;
    }
    // rows are groups of 3 on laptops: never let all three be horizontal
    var isLand = function (p) { return p.w > p.h; };
    for (var r = 0; r + 2 < photos.length; r += 3) {
      if (!(isLand(photos[r]) && isLand(photos[r + 1]) && isLand(photos[r + 2]))) continue;
      for (var c = r + 3; c < photos.length; c++) {
        if (isLand(photos[c]) || (r === 0 && photos[c].notfirst)) continue;
        var u = photos[r + 2]; photos[r + 2] = photos[c]; photos[c] = u; break;
      }
    }
    scatter(home, photos, function (p, idx, sizes) {
      var d = el("div", { class: "zoomable" }, [img(p, sizes, "Photo by Deya Liao")]);
      d.addEventListener("click", function () { openLightbox(photos, idx); });
      return d;
    }, { counts: [3], three: true });
  }

  /* ---------- about: travel film ---------- */
  var travel = $("#travel-scatter");
  if (travel && DATA.travels && DATA.travels.length) {
    // fixed order, rows of 3 that fill the full width at a shared height (no white space)
    // alternate horizontal/vertical so every row mixes both and rows end up similar heights
    var land = DATA.travels.filter(function (p) { return p.w > p.h; });
    var port = DATA.travels.filter(function (p) { return p.w <= p.h; });
    var tphotos = [];
    while (land.length || port.length) {
      var first = tphotos.length % 2 === 0 ? land : port, second = first === land ? port : land;
      tphotos.push((first.length ? first : second).shift());
    }
    var perRow = MOBILE.matches ? 2 : 3;
    for (var r = 0; r < tphotos.length; r += perRow) {
      var row = el("div", { class: "jrow" });
      tphotos.slice(r, r + perRow).forEach(function (p, j) {
        var idx = r + j;
        var d = el("div", { class: "zoomable" }, [img(p, "34vw", "Film photo from Deya's travels")]);
        d.style.flex = (p.w / p.h).toFixed(4) + " 1 0";
        d.addEventListener("click", function () { openLightbox(tphotos, idx); });
        row.appendChild(d);
      });
      travel.appendChild(row); reveal(row);
    }
  }

  /* ---------- galleries index ---------- */
  var gScatter = $("#galleries-scatter"), gList = $("#galleries-list");
  if (gScatter) {
    var card = function (g, sizes) {
      return el("a", { href: "gallery.html?g=" + g.slug }, [
        el("div", { class: "frame" }, [img(g.cover, sizes, g.name)]),
        el("div", { class: "cap" }, [el("span", { text: g.name }), el("span", { text: g.type || "", "data-zh": TYPE_ZH[g.type] || g.type || "" })])
      ]);
    };
    stagger(gScatter, DATA.galleries, function (g) { return card(g, "28vw"); });
    DATA.galleries.forEach(function (g) {
      var a = el("a", { href: "gallery.html?g=" + g.slug }, [
        img(g.cover, "100vw", g.name),
        el("div", { class: "cap" }, [el("span", { text: g.name }), el("span", { text: g.type || "", "data-zh": TYPE_ZH[g.type] || g.type || "" })])
      ]);
      gList.appendChild(a); reveal(a);
    });
  }

  /* ---------- single gallery ---------- */
  var masonry = $("#gallery");
  if (masonry) {
    var slug = new URLSearchParams(location.search).get("g");
    var gi = DATA.galleries.findIndex(function (g) { return g.slug === slug; });
    if (gi < 0) { location.replace("galleries.html"); return; }
    var g = DATA.galleries[gi];
    document.title = g.name + " · deya liao photography";
    $("#gallery-title").textContent = g.name;
    $("#gallery-location").textContent = g.location || "";
    var note = $("#gallery-note");
    if (g.note) { note.textContent = g.note; note.setAttribute("data-zh", g.note_zh || g.note); }
    else note.previousElementSibling.remove(), note.remove();
    var photos = g.photos;   // already arranged by build.py so look-alike shots sit apart
    // photos go left to right into the shortest column, so the first ones form the top row
    // (build.py models this exact layout when it keeps look-alike shots apart)
    var tiles = photos.map(function (p, idx) {
      var im = img(p, "(max-width: 760px) 100vw, 25vw", g.name);
      im.classList.add("zoomable");
      im.addEventListener("click", function () { openLightbox(photos, idx); });
      return im;
    });
    var colCount = 0;
    var layoutGallery = function () {
      var n = Math.max(1, Math.min(4, Math.floor((masonry.clientWidth + 12) / 192)));
      if (n === colCount) return;
      colCount = n; masonry.innerHTML = "";
      var cols = [], heights = [];
      for (var c = 0; c < n; c++) { cols.push(masonry.appendChild(el("div", { class: "mcol" }))); heights.push(0); }
      photos.forEach(function (p, idx) {
        var c = heights.indexOf(Math.min.apply(null, heights));
        cols[c].appendChild(tiles[idx]);
        heights[c] += p.h / p.w + 0.05;
      });
    };
    layoutGallery();
    window.addEventListener("resize", layoutGallery);
    var prev = DATA.galleries[(gi - 1 + DATA.galleries.length) % DATA.galleries.length];
    var next = DATA.galleries[(gi + 1) % DATA.galleries.length];
    var gnav = $("#gallery-nav");
    if (DATA.galleries.length > 1) {
      gnav.appendChild(el("a", { href: "gallery.html?g=" + prev.slug }, [document.createTextNode("← " + prev.name)]));
      gnav.appendChild(el("a", { class: "next", href: "gallery.html?g=" + next.slug }, [document.createTextNode(next.name + " →")]));
    }
  }

  /* ---------- contact form ---------- */
  var form = $("form.inquiry");
  if (form) {
    var status = $(".form-status", form), wrap = $(".form-area");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      status.classList.remove("error");
      var type = form.querySelector('input[name="inquiry_type"]:checked');
      if (!type) { status.textContent = T("Please choose what you're inquiring about.", "请选择咨询类型。"); status.classList.add("error"); return; }
      if (!form.checkValidity()) { form.reportValidity(); return; }
      var endpoint = form.getAttribute("action");
      var fd = new FormData(form);
      fd.set("_subject", "New " + type.value.toLowerCase() + " inquiry: " + fd.get("name") + " & " + fd.get("partner_name"));
      if (LANG === "zh") fd.set("language", "中文 (Chinese)");
      var btn = $("button[type=submit]", form);
      btn.disabled = true; status.textContent = T("Sending…", "发送中…");
      fetch(endpoint, { method: "POST", body: fd, headers: { Accept: "application/json" } })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function () {
          thanksName = (fd.get("name") || "").split(" ")[0];
          $("#thanks-name").textContent = thanksName || T("friend", "朋友");
          wrap.classList.add("sent");
          window.scrollTo({ top: wrap.getBoundingClientRect().top + window.scrollY - 120, behavior: "smooth" });
        })
        .catch(function () {
          status.textContent = T("Something went wrong sending that. Please try again, or email me directly at deya.liao@gmail.com.", "发送失败，请重试，或直接发邮件至 deya.liao@gmail.com。");
          status.classList.add("error");
        })
        .finally(function () { btn.disabled = false; });
    });
  }

  function applyLang() {
    // the Chinese font is large: only fetch it when the page is in Chinese
    if (LANG === "zh" && !$("#zh-font")) document.head.appendChild(el("link", { id: "zh-font", rel: "stylesheet",
      href: "https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;500&display=swap" }));
    document.documentElement.lang = LANG === "zh" ? "zh-CN" : "en";
    document.querySelectorAll("[data-zh]").forEach(function (n) {
      if (n.dataset.en == null) n.dataset.en = n.innerHTML;
      n.innerHTML = LANG === "zh" ? n.dataset.zh : n.dataset.en;
    });
    var y = $("#year"); if (y) y.textContent = new Date().getFullYear();
    var tn = $("#thanks-name"); if (tn && thanksName) tn.textContent = thanksName;
    document.querySelectorAll(".lang-toggle [data-l]").forEach(function (n) { n.classList.toggle("on", n.dataset.l === LANG); });
  }
  var toggle = $(".lang-toggle");
  if (toggle) toggle.addEventListener("click", function () {
    LANG = LANG === "zh" ? "en" : "zh";
    try { localStorage.setItem("lang", LANG); } catch (e) {}
    applyLang();
  });
  applyLang();
})();
