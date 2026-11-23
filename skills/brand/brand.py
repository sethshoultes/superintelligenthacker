"""A site's brand as one record, and the two checks that keep it honest (site-kit#108).

A brand is a JSON record: name, wordmark, icon set, share image, colours and support links. Each site reads it at
build, in its own stack; this file only checks it. A white-label tenant is a second record, never a fork.

  --check RECORD                    every field is there and well formed, every file exists, is not empty, and an
                                    icon is the size its key says
  --leak RECORD_A RECORD_B BUILD_B  B's build shows nothing of A: not A's name, wordmark, support links or domains
                                    in any text file (read as a person sees it: tags dropped, entities decoded, spaces
                                    folded; .gz files opened), and no file named like or identical to one of A's icon
                                    or share files. Brotli (.br) files are not opened.

Paths in a record are relative to --root (default: the current folder). Standard library only.

    python3 brand.py --check .sitekit/brand.json
    python3 brand.py --leak .sitekit/brand.json brands/smartwebutah.json dist-smartwebutah
"""
import argparse
import gzip
import hashlib
import html
import json
import pathlib
import re
import struct
import sys
import unicodedata
import urllib.parse

KEYS = {"name", "wordmark", "icons", "share_image", "colours", "support"}
OPTIONAL = {"short_name"}   # what people call the brand for short ("Foo"), searched as a whole word
# A tenant app's own surfaces, read from the same record (Foo's #342, superintelligentfoo#373): checked for shape
# here, never searched by --leak (two tenants may share a plugin's names on purpose).
URLS = ("app_url", "api_url", "help_url", "terms_url", "privacy_url", "plugin_download_url")   # https, or null
SLUGS = ("plugin_admin_page", "plugin_rest_namespace")
# The tenant's WordPress plugins (superintelligentfoo#342): the folder, zip and update channel each is published under.
PLUGIN_SLUGS = ("plugin_free_slug", "plugin_pro_slug")
# The tenant's own Unsplash app (superintelligentfoo#342): the utm_source its photo credits carry, which Unsplash's
# attribution wants to be that app's name, and the environment variable holding its access key (never the key).
UNSPLASH = {"utm_source", "access_key_env"}
# The brand's own sender (site-kit#274, superintelligentfoo#342): the From its mail carries and its Reply-To. One address
# each, so a record can never add a header or a recipient: no list, no line break, a display name in quotes only.
EMAIL_BLOCK = {"from", "reply_to"}
FROM_NAME = re.compile(r'"[^"\\<>\x00-\x1f\x7f-\x9f\u2028\u2029]{1,80}"')   # no quote, backslash, bracket or control
UTM_SOURCE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
# The site's own analytics (site-kit#240): each key optional, a site picks Cloudflare, GA4, both or neither. The values are
# public site identifiers that sit in page source, never secrets. site-templates writes them into every page's head.
ANALYTICS = {"cloudflare", "ga4"}
CF_TOKEN = re.compile(r"[0-9a-f]{32}")        # a Cloudflare Web Analytics site token (host-based entry; see SKILL.md)
GA4_ID = re.compile(r"G-[A-Z0-9]{6,12}")      # a GA4 measurement id, not the numeric property id
# The site's look (site-kit#243), config only: a closed set of header knobs, and a font's text held to plain names so it can sit
# inside a <style>. Every key optional; a site that sets none builds exactly as it did.
HEADER = {"image", "image_alt", "align", "nav_case", "logo_size", "in_card", "nav_align", "nav_current", "nav_home", "nav_style", "image_size", "title", "nav_phone"}
HEADINGS = {"case", "size", "from_h3"}
BANDS = {"light", "dark", "card"}                     # section bands (site-kit#243 follow-up): {"ground": hex, "ink": hex} each
HEADER_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
FONT_EXT = (".woff2", ".woff", ".ttf", ".otf")
FONT_FAMILY = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,59}")        # written as "Family" in a stylesheet
FONT_FALLBACK = re.compile(r"[A-Za-z0-9 ,._-]{0,120}")                # e.g. Georgia, serif: no quote, bracket or semicolon
FONT_WEIGHT = re.compile(r"(?:normal|bold|[1-9]00(?: [1-9]00)?)")
FONT_STYLE = re.compile(r"(?:normal|italic|oblique)")
OPTIONAL |= set(URLS) | set(SLUGS) | set(PLUGIN_SLUGS) | {"fonts", "unsplash", "email", "analytics", "header", "text_align", "bands", "main", "headings", "footer", "looks", "panels", "body"}
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*$")   # a WordPress page slug or REST namespace
PLUGIN_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")   # one path segment: it names a folder, a zip and a URL
ICONS = ("16", "32", "180", "192", "512", "ico")
HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
EMAIL = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")   # no ":" or "/", so never "javascript:x//@a.co"
TEXT = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".xml", ".txt", ".svg", ".webmanifest", ".md", ".map"}
PNG = b"\x89PNG\r\n\x1a\n"
ICO = b"\x00\x00\x01\x00"


TAG = re.compile(r"<[^>]*>")
SPACE = re.compile(r"\s+")


def seen(text):
    """`text` as a reader compares it: entities decoded, NFKC, every run of (Unicode) space one space, lower case."""
    return SPACE.sub(" ", unicodedata.normalize("NFKC", html.unescape(text))).strip().lower()


def _views(text):
    """The ways a page's words can show A: with its markup (attributes, scripts), with tags dropped (a word split by
    <em>), and with tags as spaces (words split by <br> or a block)."""
    return seen(text), seen(TAG.sub("", text)), seen(TAG.sub(" ", text))


def _words(rec):
    """Everything that names a brand: name, wordmark, support links, and the domains of those links."""
    s = rec["support"]
    hosts = {urllib.parse.urlsplit(s["url"]).hostname or "", s["email"].rsplit("@", 1)[-1]}
    hosts = {h.lower().removeprefix("www.") for h in hosts if h}
    return {seen(w) for w in (rec["name"], rec["wordmark"]["lead"] + rec["wordmark"]["emphasis"], s["email"],
                              s["url"], *hosts) if seen(w)}


def _short(rec):
    """The brand's short_name, matched only as a whole word, so "Foo" is a leak and "food" is not. Only the record's
    own short_name: a wordmark part is often a common word ("Solutions"), so guessing from it would flag clean builds
    (game-dev-2 on #128). Under 3 letters is too common to tell apart, so it is left out."""
    x = seen(rec.get("short_name", ""))
    return {x} if len(re.sub(r"\W", "", x)) >= 3 else set()


class BrandError(Exception):
    """The record or the build is not right; the message names each problem."""


def _text(v):
    return isinstance(v, str) and v.strip() != ""


def load(path):
    """The record at `path`, or BrandError if it is not a JSON object."""
    try:
        rec = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BrandError(f"{path}: cannot read the record ({e})") from None
    if not isinstance(rec, dict):
        raise BrandError(f"{path}: the record must be a JSON object")
    return rec


def contrast(a, b):
    """WCAG 2 contrast ratio of two #rgb or #rrggbb colours."""
    def lum(h):
        h = h.lstrip("#")
        h = "".join(ch * 2 for ch in h) if len(h) == 3 else h
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        r, g, b = (ch / 12.92 if ch <= 0.03928 else ((ch + 0.055) / 1.055) ** 2.4 for ch in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


MIN_CONTRAST = 4.5   # WCAG AA for body text: a filled button's words on its fill (site-kit#599)


def pair_problems(colours, looks=None):
    """site-kit#599: on-accent is the text on every accent-filled button (site-templates' buttons, the adventure's choices),
    so the pair must read at 4.5:1, in the base colours and in each look that changes either."""
    out, hexed = [], lambda v: isinstance(v, str) and HEX.fullmatch(v)
    pairs = [("colours", colours.get("accent"), colours.get("on-accent"))]
    for i, v in enumerate((looks or {}).get("variants", []) if isinstance(looks, dict) else []):
        vs = v.get("vars") if isinstance(v, dict) else None
        if isinstance(vs, dict) and ({"accent", "on-accent"} & set(vs)):
            pairs.append((f"looks.variants[{i}]", vs.get("accent", colours.get("accent")), vs.get("on-accent", colours.get("on-accent"))))
    for where, acc, on in pairs:
        if hexed(acc) and hexed(on) and contrast(acc, on) < MIN_CONTRAST:
            out.append(f"{where}: on-accent {on} on accent {acc} is {contrast(acc, on):.2f}:1; a filled button's text needs "
                       f"{MIN_CONTRAST}:1 (pick a darker accent or another on-accent)")
    return out


def problems(rec, root):
    """Every problem with `rec`, files resolved against `root`; empty when the record is good."""
    root = pathlib.Path(root)
    out = [f"unknown key {k!r}" for k in sorted(set(rec) - KEYS - OPTIONAL)]
    out += [f"missing {k!r}" for k in sorted(KEYS - set(rec))]
    if "name" in rec and not _text(rec["name"]):
        out.append("name must be a non-empty string")
    if "short_name" in rec and not _text(rec["short_name"]):
        out.append("short_name must be a non-empty string")
    one_line = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]")   # game-review on site-kit#126: a line break wrote structure into llms.txt
    for label, v in (("name", rec.get("name")), ("short_name", rec.get("short_name")), ("wordmark", rec.get("wordmark")),
                     ("support", rec.get("support"))):
        vals = v.values() if isinstance(v, dict) else [v]
        if any(isinstance(x, str) and one_line.search(x) for x in vals):
            out.append(f"{label} must be one line: no line break or control character")
    w = rec.get("wordmark")
    if "wordmark" in rec:
        if not isinstance(w, dict) or set(w) != {"lead", "emphasis"} or not _text(w.get("lead")) \
                or not isinstance(w.get("emphasis"), str):
            out.append('wordmark must be {"lead": text, "emphasis": text or ""}')

    def file(label, rel):
        if not _text(rel):
            out.append(f"{label} must name a file")
            return None
        p = root / rel
        if not p.is_file():
            out.append(f"{label}: {rel} does not exist")
            return None
        if p.stat().st_size == 0:
            out.append(f"{label}: {rel} is empty")
            return None
        return p.read_bytes()

    icons = rec.get("icons")
    if "icons" in rec:
        if not isinstance(icons, dict) or set(icons) != set(ICONS):
            out.append(f"icons must have exactly the keys {', '.join(ICONS)}")
        else:
            for k in ICONS:
                data = file(f"icons.{k}", icons[k])
                if data is None:
                    continue
                if k == "ico":
                    if not data.startswith(ICO):
                        out.append(f"icons.ico: {icons[k]} is not an .ico file")
                elif not data.startswith(PNG) or len(data) < 24:
                    out.append(f"icons.{k}: {icons[k]} is not a PNG")
                else:
                    wd, ht = struct.unpack(">II", data[16:24])
                    if (wd, ht) != (int(k), int(k)):
                        out.append(f"icons.{k}: {icons[k]} is {wd}x{ht}, not {k}x{k}")
    if "share_image" in rec:
        file("share_image", rec["share_image"])
    c = rec.get("colours")
    if "colours" in rec:
        if not isinstance(c, dict) or not c:
            out.append("colours must be a non-empty {role: hex} object")
        else:
            out += [f"colours.{r}: {v!r} is not a #rgb or #rrggbb hex" for r, v in c.items()
                    if not (isinstance(v, str) and HEX.fullmatch(v))]
            out += pair_problems(c, rec.get("looks"))
    for k in URLS:
        v = rec.get(k)
        if k in rec and v is not None and not (_text(v) and v.startswith("https://") and not one_line.search(v)):
            out.append(f"{k}: {v!r} must be an https:// URL or null")
    for k in SLUGS:
        if k in rec and not (isinstance(rec[k], str) and SLUG.fullmatch(rec[k])):
            out.append(f"{k}: {rec[k]!r} must be a slug like superintelligentfoo or superintelligentfoo/v1")
    for k in PLUGIN_SLUGS:
        if k in rec and not (isinstance(rec[k], str) and PLUGIN_SLUG.fullmatch(rec[k])):
            out.append(f"{k}: {rec[k]!r} must be a plugin slug like superintelligentfoo-pro")
    if "unsplash" in rec:
        u = rec["unsplash"]
        if not (isinstance(u, dict) and set(u) == UNSPLASH and isinstance(u["utm_source"], str)
                and UTM_SOURCE.fullmatch(u["utm_source"]) and isinstance(u["access_key_env"], str)
                and ENV_NAME.fullmatch(u["access_key_env"])):
            out.append('unsplash must be {"utm_source": a lowercase app name, "access_key_env": an env var NAME}')
    if "email" in rec:
        e = rec["email"]
        if not (isinstance(e, dict) and set(e) == EMAIL_BLOCK and _sender(e["from"])
                and (e["reply_to"] is None or (isinstance(e["reply_to"], str) and EMAIL.fullmatch(e["reply_to"])))):
            out.append('email must be {"from": an address or "Name" <address>, "reply_to": an address or null}')
    if "analytics" in rec:
        an = rec["analytics"]
        if not isinstance(an, dict) or not an or set(an) - ANALYTICS:
            out.append('analytics must be {"cloudflare": <32 lowercase hex token>, "ga4": "G-XXXXXXXXXX"}, each optional, and nothing else')
        else:
            for key, shape, what in (("cloudflare", CF_TOKEN, "a 32-character lowercase hex token"),
                                     ("ga4", GA4_ID, "a measurement id like G-ABC123XYZ")):
                if key in an and not (isinstance(an[key], str) and shape.fullmatch(an[key])):
                    out.append(f"analytics.{key}: {an[key]!r} is not {what}")
    if "fonts" in rec:
        fonts = rec["fonts"]
        if not isinstance(fonts, dict) or not fonts:
            out.append('fonts must be {"<role>": {"family", "fallback", "faces": [...]}, ...}')
        else:
            for role, f in fonts.items():
                if not isinstance(f, dict) or set(f) != {"family", "fallback", "faces"} or not _text(f.get("family")) \
                        or not isinstance(f.get("fallback"), str) or not isinstance(f.get("faces"), list):
                    out.append(f'fonts.{role} must be {{"family": text, "fallback": text, "faces": [files, or [] for a system stack]}}')
                    continue
                if not FONT_FAMILY.fullmatch(f["family"]) or not FONT_FALLBACK.fullmatch(f["fallback"]):
                    out.append(f"fonts.{role}: family is letters, digits, spaces and . _ -; fallback adds commas (no quote, ; {{ }} < >)")
                for face in f["faces"]:
                    if not isinstance(face, dict) or set(face) != {"file", "weight", "style"} \
                            or not all(isinstance(face.get(x), str) for x in ("weight", "style")):
                        out.append(f'fonts.{role}.faces: each must be {{"file", "weight", "style"}}')
                        continue
                    if not (FONT_WEIGHT.fullmatch(face["weight"]) and FONT_STYLE.fullmatch(face["style"])):
                        out.append(f"fonts.{role}.faces: weight is normal, bold or 100-900 (or a range), style normal, italic or oblique")
                    if not (isinstance(face["file"], str) and face["file"].lower().endswith(FONT_EXT)):
                        out.append(f"fonts.{role}.faces: {face['file']!r} must be a {', '.join(FONT_EXT)} file")
                    file(f"fonts.{role}", face["file"])
    if "header" in rec:
        h = rec["header"]
        if not isinstance(h, dict) or not h or set(h) - HEADER:
            out.append('header must be {"image", "image_alt", "align": "center", "nav_case": "upper"}, each optional, and nothing else')
        else:
            if "image" in h:
                if not (isinstance(h["image"], str) and h["image"].lower().endswith(HEADER_IMAGE_EXT)):
                    out.append(f"header.image: {h['image']!r} must be a {', '.join(HEADER_IMAGE_EXT)} file")
                file("header.image", h["image"])
                if not _text(h.get("image_alt")) or one_line.search(h["image_alt"]):
                    out.append("header.image_alt is required with header.image: one line of text saying what the image shows")
            elif "image_alt" in h:
                out.append("header.image_alt without header.image")
            if "image_size" in h and h["image_size"] != "compact":
                out.append('header.image_size must be "compact"')
            elif "image_size" in h and "image" not in h:
                out.append("header.image_size without header.image")
            if "align" in h and h["align"] != "center":
                out.append('header.align must be "center"')
            if "nav_case" in h and h["nav_case"] != "upper":
                out.append('header.nav_case must be "upper"')
            if "logo_size" in h and h["logo_size"] != "large":
                out.append('header.logo_size must be "large"')
            if "title" in h:   # key-site#18: the wordmark stacked, lead small over emphasis big, in the display font
                t = h["title"]
                if not (isinstance(t, dict) and t.get("style") == "stacked" and set(t) <= {"style", "shadow"}
                        and ("shadow" not in t or (isinstance(t["shadow"], str) and t["shadow"] in (rec.get("colours") or {})))):
                    out.append('header.title must be {"style": "stacked"}, with an optional "shadow": a role of the brand\'s colours')
                elif not (isinstance(rec.get("wordmark"), dict) and rec["wordmark"].get("lead") and rec["wordmark"].get("emphasis")):
                    out.append("header.title stacked needs a wordmark with both lead and emphasis")
            if "in_card" in h and h["in_card"] is not True:
                out.append("header.in_card must be true")
            elif "in_card" in h and rec.get("main") != "card":
                out.append('header.in_card needs main: "card"')
            if "nav_current" in h and h["nav_current"] != "bar":
                out.append('header.nav_current must be "bar"')
            if "nav_style" in h and h["nav_style"] != "muted":
                out.append('header.nav_style must be "muted"')
            if "nav_home" in h and h["nav_home"] is not True:
                out.append("header.nav_home must be true")
            if "nav_phone" in h and h["nav_phone"] != "spread":   # site-kit#533
                out.append('header.nav_phone must be "spread"')
            if "nav_align" in h and h["nav_align"] != "left":
                out.append('header.nav_align must be "left"')
            elif "nav_align" in h and h.get("align") == "center":
                out.append('header.nav_align "left" cannot go with header.align "center"')
    if "text_align" in rec and rec["text_align"] != "center":
        out.append('text_align must be "center"')
    if "footer" in rec:
        f = rec["footer"]
        if not isinstance(f, dict) or set(f) != {"band"}:
            out.append('footer must be {"band": "light" or "dark"} and nothing else')
        elif f["band"] not in ("light", "dark"):
            out.append('footer.band must be "light" or "dark"')
        elif not (isinstance(rec.get("bands"), dict) and f["band"] in rec["bands"]):
            out.append(f"footer.band {f['band']} is not defined in the brand's bands")
    if "headings" in rec:
        hd = rec["headings"]
        if not isinstance(hd, dict) or not hd or set(hd) - HEADINGS:
            out.append('headings must be {"case": "upper", "size": "small"}, each optional, and nothing else')
        else:
            if "case" in hd and hd["case"] != "upper":
                out.append('headings.case must be "upper"')
            if "size" in hd and hd["size"] != "small":
                out.append('headings.size must be "small"')
            if "from_h3" in hd and hd["from_h3"] != "text":   # site-kit#533
                out.append('headings.from_h3 must be "text"')
            elif "from_h3" in hd and "text" not in (rec.get("fonts") or {}):
                out.append('headings.from_h3 "text" needs fonts.text')
    if "main" in rec:
        if rec["main"] != "card":
            out.append('main must be "card"')
        elif not isinstance(c, dict) or "surface" not in c:
            out.append('main "card" needs colours.surface')
    if "bands" in rec:
        b = rec["bands"]
        if not isinstance(b, dict) or not b or set(b) - BANDS:
            out.append('bands must be {"light": {"ground": hex, "ink": hex}, "dark": {...}}, each optional, and nothing else')
        else:
            for name, v in b.items():
                if name == "card":   # the strip behind a card: its ground (the text sits on the card), and a ring colour (site-kit#499)
                    if not (isinstance(v, dict) and set(v) - {"focus"} == {"ground"}
                            and all(isinstance(v[x], str) and HEX.fullmatch(v[x]) for x in v)):
                        out.append('bands.card must be {"ground": #rgb or #rrggbb hex, "focus": hex (optional)}')
                    continue
                if not isinstance(v, dict) or not {"ground", "ink"} <= set(v) <= {"ground", "ink", "font", "accent", "focus"} \
                        or not all(isinstance(v[x], str) and HEX.fullmatch(v[x]) for x in ("ground", "ink") + tuple(k for k in ("accent", "focus") if k in v)):
                    out.append(f'bands.{name} must be {{"ground": #rgb or #rrggbb hex, "ink": hex, "font": a role of fonts (optional), '
                               f'"accent": hex (optional), "focus": hex (optional)}}')
                elif "font" in v and not (isinstance(v["font"], str) and isinstance(rec.get("fonts"), dict) and v["font"] in rec["fonts"]):
                    out.append(f"bands.{name}.font {v['font']!r} is not a role of the brand's fonts")
    if "panels" in rec:   # site-kit#415: comic panels, a closed set; the shadow is one of the brand's own colour roles
        pn = rec["panels"]   # site-kit#478: optionally Foo's whole page ("page": "comic") and Foo's hero ("hero": "scene")
        if not (isinstance(pn, dict) and {"style", "shadow"} <= set(pn) <= {"style", "shadow", "tab", "page", "hero", "family_links", "cta", "cards", "prose"} and pn["style"] == "comic"
                and isinstance(rec.get("colours"), dict)
                and all(isinstance(pn.get(k, pn["shadow"]), str) and pn.get(k, pn["shadow"]) in rec["colours"] for k in ("shadow", "tab"))
                and pn.get("page", "comic") == "comic" and pn.get("hero", "scene") == "scene"
                and pn.get("family_links", "ink") == "ink" and pn.get("cta", "compact") == "compact"
                and all(pn.get(k, "surface") == "surface" and (k not in pn or "surface" in rec["colours"]) for k in ("cards", "prose"))
                and (pn.get("page") == "comic" or not {"family_links", "cta"} & set(pn))):
            out.append('panels must be {"style": "comic", "shadow": a role of the brand\'s colours}, with "tab" (another role, '
                       'the middle card\'s title strip), "page": "comic", "hero": "scene", "family_links": "ink" and "cta": "compact" (these two with "page") and "cards": "surface" and "prose": "surface" (each needs colours.surface) optional')
    if "body" in rec:   # site-kit#517: running text's size and line length, for reading (Seth on Key's pages); absent writes nothing
        bd = rec["body"]
        if not (isinstance(bd, dict) and bd and set(bd) <= {"size", "measure"}
                and ("size" not in bd or body_size(bd["size"])) and ("measure" not in bd or body_measure(bd["measure"]))):
            out.append('body must be {"size": "1rem" to "1.5rem", "measure": "45ch" to "90ch"}, each optional, and nothing else')
    if "looks" in rec:   # site-kit#413: the looks a visitor picks from; theme-picker checks each look at the build
        lk = rec["looks"]
        if not (isinstance(lk, dict) and set(lk) == {"label", "variants"} and _text(lk["label"]) and len(lk["label"]) <= 40
                and not re.search(r"[\x00-\x1f\x7f\u2028\u2029]", lk["label"])
                and isinstance(lk["variants"], list) and len(lk["variants"]) >= 2):
            out.append('looks must be {"label": the menu\'s one-line text, "variants": at least two looks, the default first}')
    s = rec.get("support")
    if "support" in rec:
        if not isinstance(s, dict) or set(s) != {"email", "url"}:
            out.append('support must be {"email": ..., "url": ...}')
        else:
            if not (isinstance(s["email"], str) and EMAIL.fullmatch(s["email"])):
                out.append(f"support.email: {s['email']!r} is not an email address")
            if not (isinstance(s["url"], str) and s["url"].startswith("https://")):
                out.append(f"support.url: {s['url']!r} must start with https://")
    return out


def body_size(v):
    """A body text size: rem, 1 to 1.5 (site-kit#517)."""
    m = isinstance(v, str) and re.fullmatch(r"(1(?:\.[0-9]{1,3})?)rem", v)
    return bool(m) and float(m.group(1)) <= 1.5


def body_measure(v):
    """A running-text line length: ch, 45 to 90 (site-kit#517)."""
    m = isinstance(v, str) and re.fullmatch(r"([4-9][0-9])ch", v)
    return bool(m) and 45 <= int(m.group(1)) <= 90


def _sender(value):
    """One From address: a plain address, or a quoted display name and the address in angle brackets."""
    if not isinstance(value, str):
        return False
    if EMAIL.fullmatch(value):
        return True
    name, sep, rest = value.partition(" <")
    return bool(sep) and rest.endswith(">") and FROM_NAME.fullmatch(name) is not None and EMAIL.fullmatch(rest[:-1]) is not None


def check(path, root):
    """Raise BrandError naming every problem with the record at `path`."""
    rec = load(path)
    found = problems(rec, root)
    if found:
        raise BrandError(f"{path}:\n  " + "\n  ".join(found))
    return rec


def _files(rec):
    return [rec["icons"][k] for k in ICONS] + [rec["share_image"]]


def leaks(a, b, build, root):
    """Every trace of brand `a` in `build` (brand `b`'s built site); both records must already pass check()."""
    root, build = pathlib.Path(root), pathlib.Path(build)
    if not build.is_dir():
        raise BrandError(f"{build}: the build folder does not exist")
    words, short = _words(a), _short(a) - _words(a)
    shared = (words | short) & (_words(b) | _short(b))
    if shared:
        raise BrandError(f"the two brands share {sorted(shared)}, so a leak cannot be told apart")
    words = sorted(words)
    # a hyphen joins a word too, so "--foo-ink" and ".foo-card" (a class or variable name) are not the short name
    whole = [(w, re.compile(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])")) for w in sorted(short)]
    names = {pathlib.PurePosixPath(f).name for f in _files(a)} - {pathlib.PurePosixPath(f).name for f in _files(b)}
    hashes = {hashlib.sha256((root / f).read_bytes()).hexdigest(): f for f in _files(a)}
    out = []
    for p in sorted(build.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(build).as_posix()
        data = p.read_bytes()
        if p.name in names:
            out.append(f"{rel}: named like A's file {p.name}")
        h = hashlib.sha256(data).hexdigest()
        if h in hashes:
            out.append(f"{rel}: the same bytes as A's {hashes[h]}")
        suffix = p.suffix.lower()
        if suffix == ".gz":
            try:
                data, suffix = gzip.decompress(data), pathlib.PurePosixPath(p.stem).suffix.lower()
            except (OSError, EOFError):
                out.append(f"{rel}: not a readable gzip file, so it cannot be checked")
                continue
        if suffix in TEXT:
            views = _views(data.decode("utf-8", "replace"))
            out += [f"{rel}: contains A's {w!r}" for w in words if any(w in v for v in views)]
            out += [f"{rel}: contains A's {w!r}" for w, rx in whole if any(rx.search(v) for v in views)]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", metavar="RECORD")
    g.add_argument("--leak", nargs=3, metavar=("RECORD_A", "RECORD_B", "BUILD_B"))
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    try:
        if args.check:
            check(args.check, args.root)
            print(f"brand ok: {args.check}")
            return 0
        a, b = check(args.leak[0], args.root), check(args.leak[1], args.root)
        found = leaks(a, b, args.leak[2], args.root)
        if found:
            print(f"brand leak: {len(found)} trace(s) of {a['name']} in {args.leak[2]}:\n  " + "\n  ".join(found),
                  file=sys.stderr)
            return 1
        print(f"no leak: {args.leak[2]} shows nothing of {a['name']}")
        return 0
    except BrandError as e:
        print(f"brand: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
