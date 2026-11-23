"""Site templates, step 1e (site-kit#119, superintelligentfoo#175): build a whole static site from a layout record.

Every page of the record becomes <out>/<path>/index.html (render.document), the core-block stylesheet goes to
<out>/assets/blocks.css, and the brand record's icons and share image go to the site's root, where the pages name them.
The record is checked whole first, with its template's required routes, and with --publish every {{placeholder:...}}
left fails, so a starter can be previewed but never published unfilled. Nothing is written if the check fails.

    python3 build.py .sitekit/layout.json .sitekit/brand.json --origin https://example.com --out dist [--root .] [--publish]
        [--assets images-folder]

--assets copies the site's own images (a portfolio's work, a hero's picture) to the site's root as they sit in the
folder, so /images/a.jpg in the record is images/a.jpg in the folder. Every site-path image the pages show must be
there, and nothing the build itself writes may be overwritten.

A site with data/blog.json in --root gets its blog too (site-kit#321, blog.py): each published post at /blog/<slug>/,
the list on /blog/, and /blog/feed.xml. A post's featured image is one of --assets' images, like any other.

--functions DIR writes the site's edge code there too (site-kit#298, edge.py): its plugins' edge modules and data,
_plugins.js, the kit's chain and the kit's middleware recipe, from .sitekit/plugins.json. With --check it writes nothing and
fails if DIR differs from what it would write.

Standard library only.
"""
import argparse
import importlib.util
import json
import pathlib
import re
import shutil
import struct
import sys
import types

import agents
import blog
import discovery
import docs as doclib
import edge
import family
import layout
import render
import serialize

HERE = pathlib.Path(__file__).resolve().parent
CSS = "assets/blocks.css"
PLUGIN_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")   # a plugin folder's name, as plugins.json names it (site-kit#478)
# site-kit#476: the page a host shows for an unknown path (Pages, Netlify and most static hosts read 404.html at the root).
NOT_FOUND_FILE = "404.html"
NOT_FOUND = {
    "path": "/404/", "type": "page", "title": "No page here", "index": False, "menu": "none",
    "description": "There's no page at this address.",
    "sections": [
        {"id": "sitekit-404", "block": "text@1", "props": {"heading": "There's no page here",
         "body": [{"paragraph": "The address may have changed, or the page may be gone."}]}},
        {"id": "sitekit-404-home", "block": "cta@1", "props": {"heading": "Start from the home page", "button": {"text": "Go home", "href": "/"}}},
    ],
}


def build(record, brand_rec, origin, out, root=".", publish=False, assets=None, plugins_root=None, now=None, functions=None):
    """Write the site to `out`; returns the paths written, relative to `out`. LayoutError, and nothing written, if invalid.
    A section with a "from" or an "until" is built only inside that window, decided at `now` (default: layout.build_time()).
    With `functions`, the site's edge code goes there too (edge.py), made before anything is written."""
    blocks = layout.load_blocks()
    types = json.loads(layout.PAGE_TYPES.read_text(encoding="utf-8"))
    posts = blog.load(root)   # site-kit#321: data/blog.json's published posts become pages of the record, checked with it
    record = blog.with_pages(record, posts)
    library = doclib.load(root)   # site-kit#485: a product's synced help docs become /docs/ and a page each, checked with it
    record = doclib.with_pages(record, library)
    found = layout.problems(record, blocks, types, publish, brand=brand_rec)   # the template's own routes apply inside
    if found:
        raise layout.LayoutError("the record is not valid, so nothing was built:\n  " + "\n  ".join(found))
    record = layout.at(record, layout.build_time(publish=publish) if now is None else now, blocks)   # site-kit#383: checked whole, built as of now
    # site-kit#476: a not-found page, so a host answers 404 for an unknown path instead of serving the homepage. A record
    # that has its own /404/ keeps it; otherwise the kit's is built like any page (the site's header and footer), kept out
    # of search and every index ("index": false), and written as 404.html with no canonical.
    not_found = "/404/" not in {p["path"] for p in record["pages"]}
    if not_found:
        record = {**record, "pages": [*record["pages"], NOT_FOUND]}
    files = brand_files(brand_rec, root)   # checked before anything is written
    fonts = font_files(brand_rec, root)
    size = image_size(next((src for src, name in files.items() if name.startswith("header.")), None))
    pictures = asset_files(assets) if assets else {}
    site = render.site_data(record, brand_rec)
    fam = None
    if (record.get("footer") or {}).get("family"):   # site-kit#428: the family list, checked before anything is written
        try:
            fam = family.marked(family.load(root), origin)
        except family.FamilyError as e:
            raise layout.LayoutError(str(e)) from None
    bodies = {p["path"]: serialize.to_html(serialize.page(record, p["path"], blocks, types, brand_rec), site, p["path"]) for p in record["pages"]}
    added = {**blog.main(posts), **doclib.main(library)}
    for path, extra_html in added.items():
        bodies[path] = blog.place(bodies[path], extra_html, len(bodies[path]))
    try:
        extra = agents.files(record, brand_rec, origin, bodies, root=root, family=fam)
    except ValueError as e:   # a skill's SKILL.md that is missing, a link, or outside the site's folder
        raise layout.LayoutError(f"the record's skills can't be published, so nothing was built: {e}") from None
    # Every page's head names the catalog at both its paths when the build writes it (herdos#3873).
    catalog = list(discovery.HEAD_LINKS) if set(discovery.CATALOGS) <= set(extra) else []
    docs = {}
    for p in record["pages"]:
        # The not-found page names no address of its own: no structured data (its breadcrumb would claim /404/).
        ld = catalog + ([] if p is NOT_FOUND else
                        [agents.script(b) for b in agents.jsonld(record, p, brand_rec, origin, site["logo"], bodies[p["path"]], family=fam)])
        ld += blog.head(posts, p["path"], brand_rec["name"], origin)
        ld += doclib.head(library, p["path"])
        doc = render.document(record, p["path"], brand_rec, origin, blocks, types, css="/" + CSS, head_extra=ld, header_size=size, family=fam,
                              image=blog.image(posts, p["path"]))
        docs[p["path"]] = hero_sizes(blog.place(doc, added[p["path"]], doc.index("\n</main>")) if p["path"] in added else doc, pictures, p["path"])
    docs, slot_files = fill_slots(record, blocks, docs, root if plugins_root is None else plugins_root)   # checked, and every plugin run, before anything is written
    docs, page_files = with_page_plugins(docs, root if plugins_root is None else plugins_root, posts["posts"])
    slot_files.update(page_files)
    # Looks after page plugins: a look swaps an image a page plugin places (hero-character's variant_slot, key-site#24).
    docs, look_files = with_looks(brand_rec, docs, root if plugins_root is None else plugins_root, pictures)
    slot_files.update(look_files)
    try:
        edge_files = edge.files(root, functions) if functions is not None else {}
        found = edge.refusals(edge_files, functions) if functions is not None else []
        if found:
            raise edge.EdgeError("; ".join(found))
    except edge.EdgeError as e:
        raise layout.LayoutError(f"the site's edge code can't be made, so nothing was built: {e}") from None
    listed = edge.listed_gated(record["pages"], edge_files)
    # The blog's pages come from data/blog.json and carry no "index" key, so the fix for them is the rule (Fable on #399).
    posts_listed = [p for p in listed if p == "/blog/" or p.startswith("/blog/")]
    if posts_listed:
        raise layout.LayoutError(f'a members rule gates the blog ({", ".join(posts_listed)}), whose pages are always listed: move '
                                 "the rule off /blog/ (a gated page belongs in the record, with \"index\": false); nothing was built")
    if listed:
        raise layout.LayoutError(f'a members rule gates {", ".join(listed)}, so each needs "index": false, or its words would be in '
                                 "llms-full.txt and its path in the sitemap; nothing was built")
    extra.update(blog.files(posts, brand_rec["name"], origin, extra))
    extra.update(doclib.files(library, extra))
    if not_found:
        # It is served at whatever address was asked for, so it claims none: no canonical and no og:url.
        page404 = re.sub(r'\s*<link rel="canonical" href="[^"]*">', "", docs.pop(NOT_FOUND["path"]), count=1)
        extra[NOT_FOUND_FILE] = re.sub(r'\s*<meta property="og:url" content="[^"]*">', "", page404, count=1)
    out, root, written = pathlib.Path(out), pathlib.Path(root), []
    # Every target is worked out and checked before the first file is written, so a refusal leaves nothing behind.
    made = [*(p.strip("/") + "/index.html" for p in docs), CSS, *files.values(), *(name for _, name in fonts), *extra, *slot_files.values()]
    for rel in [*made, *pictures.values()]:
        _inside(out, rel.lstrip("/"))
    # casefolded: on a case-insensitive disk (a Mac's) Icon-192.PNG would replace the brand's icon-192.png (game-dev-3 on #141)
    clash = sorted(r for r in pictures.values() if r.casefold() in {m.lstrip("/").casefold() for m in made})
    if clash:
        raise layout.LayoutError(f"--assets would overwrite what the build writes: {', '.join(clash)}")
    missing = sorted({src for src in re.findall(r'<img src="(/[^"]*)"', "".join(bodies.values()))} - {"/" + r for r in pictures.values()} - {"/" + n for n in files.values()})
    if missing:
        raise layout.LayoutError("the record shows images that --assets doesn't hold: " + ", ".join(missing))
    for path, doc in docs.items():
        f = out / path.strip("/") / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(doc, encoding="utf-8")
        written.append(f.relative_to(out).as_posix())
    for rel, text in extra.items():
        f = _inside(out, rel)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        written.append(rel)
    (out / CSS).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / "blocks.css", out / CSS)
    written.append(CSS)
    for rel, name in files.items():
        shutil.copyfile(rel, out / name)
        written.append(name)
    for src, name in fonts:
        f = out / name
        f.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, f)
        written.append(name)
    for src, rel in slot_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, f)
        written.append(rel)
    for src, rel in pictures.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, f)
        written.append(rel)
    if functions is not None:
        edge.write(edge_files, functions)
    return sorted(written)


def fill_slots(record, blocks, docs, root):
    """Each page with a plugin slot (site-kit#223), its empty group replaced by the plugin's own render(config): the
    record's "slots" names the plugin and its committed config file. Only a plugin whose plugin.json says
    "fills_slots": true may fill one; a slot with no plugin, or a plugin's refusal, stops the build. layout.problems has
    already held the record to: every slot on a page is mapped, and every mapping's slot is on a page.
    site-kit#303: a plugin's "slot_assets" ({"css": [...], "js": [...]}, each one of its "assets") are linked on the pages
    that hold its slot, and only there; its "assets" are copied to /assets/plugins/<plugin>/. Returns (docs, {source: path})."""
    root, mapping, made, manifests, copies = pathlib.Path(root), record.get("slots", {}), {}, {}, {}
    for path, names in layout.slots(record, blocks).items():
        doc, used = docs[path], []
        for name in names:
            m = mapping[name]
            group = re.compile(r'<div id="[^"]*" class="wp-block-group slot ' + re.escape(serialize.SLOT_CLASS + name) + r'"></div>')
            if len(group.findall(doc)) != 1:
                raise layout.LayoutError(f"page {path}: slot {name!r} is not one empty group in the page")
            if name not in made:
                made[name], manifests[m["plugin"]] = _plugin_output(name, m["plugin"], root / m["config"], root)
            doc = group.sub(lambda g: g.group(0)[:-len("</div>")] + made[name] + "</div>", doc)
            if m["plugin"] not in used:
                used.append(m["plugin"])
        for plugin in used:
            css, js = _slot_assets(plugin, manifests[plugin], root, copies)
            base = f"/assets/plugins/{plugin}/"
            doc = doc.replace("</head>", "".join(f'<link rel="stylesheet" href="{base}{a}">' for a in css) + "</head>", 1)
            doc = doc.replace("</body>", "".join(f'<script src="{base}{a}" defer></script>' for a in js) + "</body>", 1)
        docs[path] = doc
    return docs, copies


SLOT_ASSET = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._/-]*")


def _slot_assets(plugin, manifest, root, copies):
    """The css and js a slot plugin links, after its "assets" (every file it ships) are queued in `copies`: each a plain
    relative path inside the plugin's own folder, never a ".." or a symlink out of it."""
    folder, assets = root / "plugins" / plugin, manifest.get("assets", [])
    want = manifest.get("slot_assets", {})
    if not isinstance(assets, list) or not isinstance(want, dict) or set(want) - {"css", "js"}:
        raise layout.LayoutError(f'plugin {plugin!r}: "assets" is a list and "slot_assets" is {{"css": [...], "js": [...]}}')
    for a in assets:
        # one spelling per file (mkt-dev and mi-dev-2 on #304): no empty, "." or ".." segment, so "vendor//x.js" is refused
        if not (isinstance(a, str) and SLOT_ASSET.fullmatch(a) and not {"", ".", ".."} & set(a.split("/"))
                and (folder / a).resolve().is_relative_to(folder.resolve()) and (folder / a).is_file()):
            raise layout.LayoutError(f"plugin {plugin!r}: asset {a!r} is not a file inside its folder")
        copies[folder / a] = f"assets/plugins/{plugin}/{a}"
    css, js = want.get("css", []), want.get("js", [])
    for a in [*css, *js]:
        if a not in assets:
            raise layout.LayoutError(f'plugin {plugin!r}: slot asset {a!r} is not one of its "assets"')
    return css, js


PICKER_JS = "assets/theme-picker.js"
# site-kit#416: the menu reads as a control, the way Foo's era picker does: a bordered button in the site's own tokens
# (ink, ground, accent, the display font), a caret, 44px targets, a focus ring, and the current look ticked.
PICKER_STYLE = (".wp-block-column:has(>[data-variant-picker]){display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-end;gap:.5rem 1rem}"
                ".variant-picker{position:relative;display:inline-block}"
                ".variant-picker summary{cursor:pointer;list-style:none;display:inline-flex;align-items:center;min-height:44px;"
                "padding:.3em .8em;font-family:var(--sk-font-display,inherit);letter-spacing:.03em;color:var(--st-ink);"
                "background:var(--st-ground);border:2px solid var(--st-ink);border-radius:.4rem}"
                ".variant-picker summary::-webkit-details-marker{display:none}"
                '.variant-picker summary::after{content:"\\25BE";margin-left:.4em}'
                ".variant-picker summary:focus-visible{outline:3px solid var(--st-accent);outline-offset:2px}"
                ".variant-picker ul{position:absolute;right:0;top:calc(100% + 6px);z-index:10;margin:0;padding:.25rem;list-style:none;min-width:11em;"
                "background:var(--st-ground);color:var(--st-ink);border:2px solid var(--st-ink);border-radius:.4rem}"
                ".variant-picker button{width:100%;text-align:left;min-height:44px;font:inherit;font-family:var(--sk-font-display,inherit);"
                "color:inherit;background:none;border:0;border-radius:.3rem;padding:.3em .6em;cursor:pointer;white-space:nowrap}"
                ".variant-picker button:hover,.variant-picker button:focus-visible{background:color-mix(in srgb,var(--st-accent) 35%,var(--st-ground))}"
                '.variant-picker button[aria-pressed="true"]::after{content:" \\2713"}')


def with_page_plugins(docs, root, posts=()):
    """site-kit#478: the page plugins a site names in .sitekit/plugins.json, the ones that fill head.styles or filter
    page.html and have no edge code (time-of-day's backdrop, hero-character's figure and bubble), run as Foo's builder runs
    them: each page's head gets their styles, each page goes through their filters, and their assets are copied. They are
    loaded through the site's own synced theme.py, so a plugin is checked as it is everywhere else. A site that names none
    builds byte for byte as before. Returns (docs, {source: path in the site})."""
    root = pathlib.Path(root)
    conf = root / ".sitekit" / "plugins.json"
    try:
        settings = json.loads(conf.read_text(encoding="utf-8")) if conf.is_file() else {}
    except (OSError, ValueError) as e:
        raise layout.LayoutError(f".sitekit/plugins.json can't be read ({type(e).__name__}); nothing was built") from None
    if not isinstance(settings, dict):   # game-review on #479: a list or a string named nothing, silently
        raise layout.LayoutError('.sitekit/plugins.json must be {"<plugin>": {"<setting>": value}}; nothing was built')
    named = set(settings)
    for name in sorted(named):
        # a plain folder name before any path is made of it, so "../x" or an absolute path is refused by name (game-review on #479)
        if not PLUGIN_NAME.fullmatch(name):
            raise layout.LayoutError(f'plugins.json names {name!r}, which is not a plugin folder name; nothing was built')
        manifest = root / "plugins" / name / "plugin.json"
        if not manifest.is_file():
            raise layout.LayoutError(f'settings for plugin "{name}", which is not in plugins/ (remove them, or restore the '
                                     "folder); nothing was built")
        try:   # an unreadable manifest is named, never skipped: it would ship every page without the plugin (game-review on #479)
            if not isinstance(json.loads(manifest.read_text(encoding="utf-8")), dict):
                raise ValueError("not an object")
        except (OSError, ValueError):
            raise layout.LayoutError(f"plugins/{name}/plugin.json can't be read; nothing was built") from None
    names = named & edge.page_plugins(root / "plugins")
    if not names:
        return docs, {}
    kit = root / ".sitekit" / "theme.py"
    spec = importlib.util.spec_from_file_location("sitekit_theme_pages", kit)
    if spec is None or not kit.is_file():
        raise layout.LayoutError(".sitekit/theme.py is missing: run site_sync.py sync; nothing was built")
    theme = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(theme)
    # The site's data a page plugin reads as ctx, as Foo's builder passes it (site-kit#478): data/editions.json for
    # monthly-edition. Absent, the plugin gets no editions and writes nothing; unreadable, the build stops.
    data = {}
    ed = root / "data" / "editions.json"
    if ed.is_file():
        try:
            data["editions"] = json.loads(ed.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise layout.LayoutError(f"data/editions.json can't be read ({type(e).__name__}); nothing was built") from None
    # site-kit#510: data/series.json for the series plugin, as ctx.series. Absent, a page with a series marker stops the build.
    sj = root / "data" / "series.json"
    if sj.is_file():
        try:
            data["series"] = doclib.strict("data/series.json", sj.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise layout.LayoutError(f"data/series.json can't be read ({type(e).__name__}); nothing was built") from None
    # site-kit#488: the family's monthly themes (the kit's catalog/editions.json, vendored on a family site) and the blog's
    # published posts, for monthly-edition's issue menu. Absent, the menu has none of them.
    themes = root / ".sitekit" / "editions.json"
    if themes.is_file():
        try:
            data["themes"] = doclib.strict(".sitekit/editions.json", themes.read_text(encoding="utf-8"))["themes"]   # a repeated month refused (site-kit#503)
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise layout.LayoutError(f".sitekit/editions.json can't be read ({type(e).__name__}): run site_sync.py sync; nothing was built") from None
    data["posts"] = [{"slug": p["slug"], "title": p["title"], "date": p["date"]} for p in posts]
    try:
        t = theme.load(root / "plugins", {n: settings[n] for n in names}, only=names)
        out = {}
        for path, doc in docs.items():
            ctx = types.SimpleNamespace(path=path, **data)
            head = t.render("head.styles", ctx)
            if head:
                doc = doc.replace("\n</head>", f"\n{head}\n</head>", 1)
            out[path] = t.filter("page.html", doc, ctx)
    except theme.ThemeError as e:
        raise layout.LayoutError(f"a page plugin refused: {e}; nothing was built") from None
    files = {}
    for p in t.plugins:
        for rel in p.assets:
            files[p.folder / rel] = f"assets/plugins/{p.name}/{rel}"
    return out, files


def with_looks(brand_rec, docs, root, pictures):
    """site-kit#413: the brand's looks, switched by site-kit's theme-picker, the plugin Foo's era picker uses (no second one).
    It runs the vendored plugin's own head.styles hook and page.html filter on every page, puts its menu at the end of the
    header, and copies its script. A look's vars that name a brand colour role, or display-font, also set the variable the
    blocks read (--wp--preset--color--<role>, --sk-font-display) under html[data-variant], so one look recolours every
    block with no site stylesheet. The default look is the brand as built. An image is swapped by the default look's path:
    each <img> showing the default look's `images` path for a slot is marked with that slot. A brand with no looks builds
    byte for byte as before. Returns (docs, {source: path in the site})."""
    looks = brand_rec.get("looks")
    if not looks:
        return docs, {}
    root = pathlib.Path(root)
    folder, base = root / "plugins" / "theme-picker", root.resolve()
    for target in (folder / "plugin.py", folder / PICKER_JS):
        if not target.is_file() or not target.resolve().is_relative_to(base):
            raise layout.LayoutError("the brand's looks need site-kit's theme-picker in plugins/theme-picker "
                                     "(plugin-sync.sh theme-picker <tag>); nothing was built")
    spec = importlib.util.spec_from_file_location("sitekit_hook_theme_picker", folder / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    ctx = types.SimpleNamespace(config={"menu_label": looks["label"]}, variants=looks["variants"])
    try:
        spec.loader.exec_module(module)
        head = module.hooks["head.styles"](ctx)
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        raise layout.LayoutError(f"the brand's looks: theme-picker refused: {e}; nothing was built") from None
    default, others = looks["variants"][0], looks["variants"][1:]
    roles, rules = set(brand_rec["colours"]), [PICKER_STYLE]
    if (brand_rec.get("panels") or {}).get("style") == "comic":   # square like the comic panels (the designer on key-site#7)
        rules.append(".variant-picker summary,.variant-picker ul,.variant-picker button{border-radius:0}")
    for v in others:
        mapped = [(f"--wp--preset--color--{n}" if n in roles else "--sk-font-display", n)
                  for n in (v.get("vars") or {}) if n in roles or n == "display-font"]
        if mapped:
            rules.append(f'html[data-variant="{v["key"]}"]{{' + "".join(f"{t}:var(--variant-{n});" for t, n in mapped) + "}")
    slots = default.get("images") or {}
    for v in looks["variants"]:   # a slot name is written into an attribute: held to theme-picker's own slot pattern
        for slot in v.get("images") or {}:
            if not (isinstance(slot, str) and module.KEY.fullmatch(slot)):
                raise layout.LayoutError(f'look {v["key"]}: image slot {slot!r} must be lowercase letters, digits and hyphens; '
                                         "nothing was built")
    for v in others:
        for slot, src in (v.get("images") or {}).items():
            if slot not in slots:
                raise layout.LayoutError(f'look {v["key"]}: image slot {slot!r} needs the default look\'s image for it, the path '
                                         "the page shows; nothing was built")
            if src.lstrip("/") not in pictures.values():
                raise layout.LayoutError(f'look {v["key"]}: image {src} is not in --assets; nothing was built')
    out = {}
    for path, doc in docs.items():
        for slot, src in slots.items():
            doc = doc.replace(f'<img src="{src}"', f'<img data-variant-img="{slot}" src="{src}"')
        doc = doc.replace("\n</head>", f"\n<style>{''.join(rules)}</style>\n{head}\n</head>", 1)
        if "</header>" in doc:   # beside the header's menu when it has one, else at the header's end
            end = doc.index("</header>")
            nav = doc.find("</nav>", doc.index("<header"), end)
            at = nav + len("</nav>") if nav != -1 else end
            doc = doc[:at] + "<div data-variant-picker></div>" + doc[at:]
        try:
            out[path] = module.filters["page.html"](doc, ctx)
        except ValueError as e:
            raise layout.LayoutError(f"{path}: theme-picker refused: {e}; nothing was built") from None
    shown = "".join(out.values())
    unseen = sorted(slot for slot in slots if f'data-variant-img="{slot}"' not in shown)
    if unseen:
        raise layout.LayoutError(f"the default look's image for {', '.join(unseen)} is on no page, so no look can swap it; "
                                 "nothing was built")
    return out, {folder / PICKER_JS: "assets/plugins/theme-picker/" + PICKER_JS}


def _plugin_output(slot, plugin, config_path, root):
    """What one slot-filling plugin renders for its config."""
    folder, base = root / "plugins" / plugin, root.resolve()
    # A committed symlink must not reach outside the site (site-dev on #227): both are resolved and kept inside root.
    for what, target in (("plugin folder", folder), ("plugin.json", folder / "plugin.json"), ("plugin.py", folder / "plugin.py"),
                         ("config", config_path)):
        if not target.resolve().is_relative_to(base):
            raise layout.LayoutError(f"slot {slot!r}: its {what} resolves outside the site, so it is not read")
    try:
        manifest = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise layout.LayoutError(f"slot {slot!r}: no plugin {plugin!r} in plugins/ ({type(e).__name__})") from None
    if manifest.get("fills_slots") is not True:
        raise layout.LayoutError(f'slot {slot!r}: plugin {plugin!r} does not say "fills_slots": true, so it may not fill a slot')
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise layout.LayoutError(f"slot {slot!r}: cannot read its config {config_path.relative_to(root)} ({type(e).__name__})") from None
    spec = importlib.util.spec_from_file_location(f"sitekit_slot_{plugin.replace('-', '_')}", folder / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        html = module.render(config)
    except Exception as e:   # the plugin's own refusal, shown as it wrote it (paypal-button never echoes a URL, #224)
        raise layout.LayoutError(f"slot {slot!r}: {plugin} refused: {e}") from None
    if not isinstance(html, str) or not html.strip():
        raise layout.LayoutError(f"slot {slot!r}: {plugin}'s render gave no markup")
    return html, manifest


def _inside(out, rel):
    """`out/rel`, refused unless it stays inside `out` (game-dev-3 on #125)."""
    target = (out / rel).resolve()
    if not target.is_relative_to(out.resolve()):
        raise layout.LayoutError(f"{rel!r} would be written outside the output folder")
    return target


MAGIC = {"png": (b"\x89PNG\r\n\x1a\n",), "jpg": (b"\xff\xd8\xff",), "ico": (b"\x00\x00\x01\x00",)}


def brand_files(brand_rec, root):
    """{source file: fixed name}, every source inside `root` and of the type its name says (the security review on
    step 1e: a brand path of ../../anything would have been copied into the published site)."""
    root = pathlib.Path(root).resolve()
    out = {}
    for rel, name in render.web_names(brand_rec).items():
        src = (root / rel).resolve()
        if not src.is_relative_to(root) or not src.is_file():
            raise layout.LayoutError(f"brand file {rel!r} must be a file inside {root}")
        head = src.read_bytes()[:12]
        kind = name.rsplit(".", 1)[1]
        ok = head[:4] == b"RIFF" and head[8:12] == b"WEBP" if kind == "webp" else head.startswith(MAGIC[kind])
        if not ok:
            raise layout.LayoutError(f"brand file {rel!r} is not a {kind} image")
        if src in out:   # game-dev-2 on #125: "brand/./icon-32.png" and "brand/icon-32.png" are one file in two slots
            raise layout.LayoutError(f"brand file {rel!r} is named for two slots")
        out[src] = name
    return out


FONT_MAGIC = {".woff2": (b"wOF2",), ".woff": (b"wOFF",), ".ttf": (b"\x00\x01\x00\x00", b"true"), ".otf": (b"OTTO",)}


def font_files(brand_rec, root):
    """[(source file, fixed name)] for the brand's font faces (site-kit#243), every source inside `root` and of the type its
    name says, as brand_files does for icons."""
    root = pathlib.Path(root).resolve()
    out = []
    for rel, name in render.font_names(brand_rec):
        src = (root / rel).resolve()
        if not src.is_relative_to(root) or not src.is_file():
            raise layout.LayoutError(f"font file {rel!r} must be a file inside {root}")
        if not src.read_bytes()[:4].startswith(FONT_MAGIC[pathlib.PurePosixPath(name).suffix]):
            raise layout.LayoutError(f"font file {rel!r} is not a {pathlib.PurePosixPath(name).suffix[1:]} font")
        out.append((src, name))
    return out


HERO_IMG = re.compile(r'<img src="((?:/img/hero/|/docs-img/)[^"<>]+)" alt="')   # hero art (site-kit#519) and docs figures (#516)


def hero_sizes(html, pictures, path):
    """Hero art (site-kit#519, under /img/hero/) carries its own width and height, read from the file, so the hero never
    shifts the page as it loads. Only that path, so every other image is written as before."""
    by_path = {"/" + name: src for src, name in pictures.items()}

    def sized(m):
        size = image_size(by_path.get(m.group(1)))
        if size is None:
            raise layout.LayoutError(f"page {path}: hero art {m.group(1)} must be a PNG, JPEG or WebP in --assets, so its size can go on the page")
        return f'<img src="{m.group(1)}" width="{size[0]}" height="{size[1]}" alt="'
    return HERO_IMG.sub(sized, html)


def image_size(src):
    """(width, height) of a PNG, JPEG or WebP, read from its header, or None (anything unreadable: the page then simply carries
    no size)."""
    if src is None:
        return None
    data = src.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        i = 2
        while i + 9 < len(data) and data[i] == 0xFF:
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return (w, h) if w and h else None
            i += 2 + length
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) >= 30:   # superintelligentfoo#1028: a .webp banner
        chunk = data[12:16]
        if chunk == b"VP8X":                                   # extended: the canvas, 24-bit little-endian, each minus one
            return (1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little"))
        if chunk == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":  # lossy: after the key frame's start code
            w, h = struct.unpack("<HH", data[26:30])
            return (w & 0x3FFF, h & 0x3FFF) if w & 0x3FFF and h & 0x3FFF else None
        if chunk == b"VP8L" and data[20] == 0x2F:              # lossless: 14 bits each, minus one
            bits = int.from_bytes(data[21:25], "little")
            return (1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF))
    return None


IMAGE_KIND = {".png": "png", ".jpg": "jpg", ".jpeg": "jpg", ".webp": "webp"}


def asset_files(folder):
    """{source file: its path in the site} for the site's own images (a portfolio's work, a hero's picture): every file in
    `folder`, each a real image of the type its name says, no link out of the folder, and names a site path can hold."""
    folder = pathlib.Path(folder).resolve()
    if not folder.is_dir():
        raise layout.LayoutError(f"--assets {folder} is not a folder")
    out, seen = {}, {}
    for src in sorted(folder.rglob("*")):
        rel = src.relative_to(folder).as_posix()
        if any(part.startswith(".") for part in rel.split("/")):
            continue   # .DS_Store, .git and the like are the folder's, not the site's (game-dev-3 on #141)
        if src.is_symlink():   # a linked file, or a linked folder rglob would skip without a word (game-dev-2 on #141)
            raise layout.LayoutError(f"asset {rel!r} is a link; copy the file into the folder instead")
        if src.is_dir():
            continue
        kind = IMAGE_KIND.get(src.suffix.lower())
        if src.is_symlink() or not src.resolve().is_relative_to(folder) or not src.is_file():
            raise layout.LayoutError(f"asset {rel!r} must be a file inside {folder}")
        if not kind or not layout.SAFE_SRC.fullmatch("/" + rel):
            raise layout.LayoutError(f"asset {rel!r} must be a .png, .jpg or .webp with a plain name (letters, digits, . _ ~ -)")
        head = src.read_bytes()[:12]
        if not (head[:4] == b"RIFF" and head[8:12] == b"WEBP" if kind == "webp" else head.startswith(MAGIC[kind])):
            raise layout.LayoutError(f"asset {rel!r} is not a {kind} image")
        if rel.casefold() in seen:   # two names one disk would hold as one file
            raise layout.LayoutError(f"assets {seen[rel.casefold()]!r} and {rel!r} differ only in case")
        seen[rel.casefold()] = rel
        out[src] = rel
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("record")
    ap.add_argument("brand")
    ap.add_argument("--origin", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--root", default=".", help="the site's folder: the brand record's files, and data/blog.json if it has a blog")
    ap.add_argument("--publish", action="store_true", help="fail on any {{placeholder:...}} left")
    ap.add_argument("--assets", help="a folder of the site's own images, copied to the site's root as they sit")
    ap.add_argument("--functions", help="also write the site's edge code to this folder (edge.py), from .sitekit/plugins.json")
    ap.add_argument("--check", action="store_true", help="with --functions: write nothing, fail if that folder differs")
    args = ap.parse_args(argv)
    if args.check:
        if not args.functions:
            ap.error("--check needs --functions")
        try:
            stale = edge.differences(edge.files(args.root, args.functions), args.functions)
        except edge.EdgeError as e:
            print(f"build: {e}", file=sys.stderr)
            return 1
        for rel in stale:
            print(f"build: {args.functions}/{rel} differs from what the build writes: run build.py with --functions", file=sys.stderr)
        return 1 if stale else 0
    try:
        record = json.loads(pathlib.Path(args.record).read_text(encoding="utf-8"))
        brand_rec = render.brand.check(args.brand, args.root)
        now = layout.build_time(publish=args.publish)
        if layout.gated(record):
            print(f"build: dated sections decided at {now.isoformat(timespec='seconds')}")
        written = build(record, brand_rec, args.origin, args.out, args.root, args.publish, args.assets, now=now, functions=args.functions)
    except (OSError, ValueError) as e:
        print(f"build: cannot read ({e})", file=sys.stderr)
        return 1
    except (layout.LayoutError, render.brand.BrandError) as e:
        print(f"build: {e}", file=sys.stderr)
        return 1
    print(f"build: {len(written)} files written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
