---
name: brand
description: Give a site its brand as one record (.sitekit/brand.json), checked by brand.py --check, with brand.py --leak proving a white-label tenant's build shows nothing of the first brand.
scope: shared
---

# brand: one record per brand

Seth (2026-11-06, superintelligentfoo#152): "this should be templatized for white labeling". Ruled in site-kit#108:
site-kit owns the record's shape and its checks. Each site reads the record at build in its own stack (Svelte, Astro,
static HTML). The header, favicons, share image, JSON-LD logo and support link all come from it. Nothing is hard-coded
in a template. A white-label tenant is a second record, never a fork.

## The record

`.sitekit/brand.json` for the site's own brand, plus one file per tenant (for example `brands/smartwebutah.json`).
Paths are relative to the repo root.

```json
{
  "name": "Super Intelligent Foo",
  "wordmark": {"lead": "Super Intelligent ", "emphasis": "Foo"},
  "icons": {"16": "brand/icon-16.png", "32": "brand/icon-32.png", "180": "brand/icon-180.png",
            "192": "brand/icon-192.png", "512": "brand/icon-512.png", "ico": "brand/favicon.ico"},
  "share_image": "brand/share.png",
  "colours": {"ink": "#1d1d1f", "accent": "#0b57d0", "ground": "#ffffff"},
  "support": {"email": "help@example.com", "url": "https://example.com/help/"}
}
```

- Every key is required, and an unknown key fails. `emphasis` may be `""` for a one-part wordmark.
- `short_name` is optional: what people call the brand for short (e.g. `"Foo"`).
- **Analytics (site-kit#240):** an optional `analytics` object, `{"cloudflare": "<32 lowercase hex token>", "ga4": "G-XXXXXXXXXX"}`, each key optional and nothing else allowed. A site picks Cloudflare, GA4, both or neither; site-templates writes the tags into every page's head. Both values are public site identifiers, not secrets. The Cloudflare value is the Web Analytics site's **`site_token`**, never its `site_tag`: both are 32 lowercase hex, so `brand.check` cannot tell them apart, but a beacon carrying the tag records nothing (sethshoultes.com and ohmsville.com both lost every page load that way, found 2026-11-09). The tag is what the analytics API filters by; the token is what `ops/cloudflare.sh web-analytics enable` prints in the snippet. Where the Cloudflare token comes from matters: on one Pages site a token from a zone-based Web Analytics entry never recorded a page load, while a host-based entry (`{host, auto_install: false}`) is the other shape Cloudflare offers; either way, confirm a page load in Cloudflare Web Analytics (see the site-templates skill). The check only sees the token's shape. The GA4 value is the measurement id, not the numeric property id.
- A tenant app can carry its own surfaces in the same record, all optional and checked for shape only (`--leak` never searches them): `app_url`, `api_url`, `help_url`, `terms_url`, `privacy_url` and `plugin_download_url` (each an `https://` URL or `null`); `plugin_admin_page` and `plugin_rest_namespace` (lowercase slugs such as `superintelligentfoo` and `superintelligentfoo/v1`); `plugin_free_slug` and `plugin_pro_slug` (the tenant's WordPress plugins, one lowercase segment such as `superintelligentfoo-pro`, superintelligentfoo#342); `unsplash`, `{"utm_source", "access_key_env"}`: the tenant's own Unsplash app name, which its photo credits carry, and the name of the environment variable holding its key, never the key itself (superintelligentfoo#342); `email`, `{"from", "reply_to"}`: the brand's own sender, `from` a plain address or `"Name" <address>` and `reply_to` a plain address or `null`, one address each with no list, and a name of at most 80 characters with no quote, backslash, bracket, line break or other control character, so a record can never add a header or a recipient (site-kit#274); and `fonts`, roles such as `display` and `text`, each `{"family", "fallback", "faces": [{"file", "weight", "style"}]}` with every face file present (superintelligentfoo#373; site-kit#243: `faces` may be `[]` for a system stack such as Georgia, serif, and the text is held to plain names: family is letters, digits, spaces and `. _ -`, fallback adds commas, a face's weight is `normal`, `bold` or `100`-`900` or a range like `300 700`, its style `normal`, `italic` or `oblique`, and its file `.woff2`, `.woff`, `.ttf` or `.otf`). The support email must be a plain address: letters, digits and `._%+-`, an `@`, then a domain.
- **The site's look (site-kit#243), config only:** a migrated site keeps its own look from this record, with no free CSS and no per-site stylesheet. Every key is optional, and a site that sets none builds byte for byte as it did. Colours take one more role, `heading` (see below); `fonts` is rendered by site-templates; and an optional `header` object takes a closed set of keys:

  ```json
  "colours": {"ink": "#1d1d1f", "ground": "#fff", "accent": "#0b57d0", "heading": "#e8505b"},
  "header": {"image": "brand/header.png", "image_alt": "Red hills under a low sun", "align": "center", "nav_case": "upper"}
  ```

  - `colours.heading`: the colour of `h1`-`h6` (not inside the closing call-to-action band, which keeps its own pair). Unset, headings take `ink` as before.
  - `header.image`: a `.png`, `.jpg` or `.webp` file, checked like `share_image` (present, not empty). The static site shows it as a full-width banner where the logo and the site's name would be, with the menu below it, under the fixed name `/header.<ext>` and with its width and height (PNG, JPEG or WebP). `header.image_alt` is required whenever `image` is set (one line of text) and is refused without an image.
  - `header.image_size`: only `"compact"`, and only with `header.image`: the banner keeps its own shape at a height capped at clamp(8.5rem,16vw,12rem), left-aligned, instead of filling the content width. For a logo lockup, where full width makes it hundreds of pixels tall.
  - `header.align`: only `"center"`: the logo and name above the menu, all centred.
  - `header.nav_case`: only `"upper"`: uppercase menu labels.
  - `header.logo_size`: only `"large"`: the logo at 96px instead of 48px. Ignored when `header.image` is set.
  - `header.title`: only `{"style": "stacked"}`, with an optional `"shadow"`: a role of the brand's `colours`. The header's
    site title becomes the wordmark stacked, `lead` small over `emphasis` big, beside the logo (key-site#18, Foo's lockup in
    live text). It needs a wordmark with both parts. Ignored when `header.image` is set.
  - `colours.surface` (a colour role like `heading`): a colour and nothing else. On its own it changes no layout; a site that sets it builds the same page as one that does not (it only reaches the palette). `band: "card"` sections and `main: "card"` use it.
  - `main`: a top-level key, only `"card"`: `<main>` becomes one card in `colours.surface` at the content width (68rem) with the page's `ground` around it. The brand check refuses it without `colours.surface`. A card (this or a `band: "card"` section) sets its own text colour: `bands.light.ink` if the brand defines a light band, else the page `ink` left alone when it contrasts 4.5:1 with the surface, else black or white by the surface's luminance. Links and outlined buttons in a card take that ink (links underlined) only when the accent fails 4.5:1 on the surface; filled buttons keep their accent / on-accent pair.
  - `text_align`: a top-level key, only `"center"`: centres the main area's text and its buttons.
  - `bands`: `{"light": {"ground": hex, "ink": hex}, "dark": {...}}`, each band optional, nothing else. A section in `layout.json` picks one with `"band": "light"` or `"dark"`; `"band": "card"` puts that section on a `colours.surface` card instead (the card rule is written only on a page that has such a section). The layout check refuses a band the brand does not define and `card` without `colours.surface`.
  - `panels` (site-kit#415, optional): `{"style": "comic", "shadow": a role of colours}`, comic borders and hard shadows (see site-templates). Optionally `"page": "comic"` and `"hero": "scene"`, Foo's whole page and Foo's hero, and `"tab"`, another colour role for the middle card's strip (site-kit#478). With `"page"`, `"family_links": "ink"` and `"cta": "compact"` (site-kit#517). Static-only.
  - `body` (site-kit#517, optional): `{"size": "1rem" to "1.5rem", "measure": "45ch" to "90ch"}`, each optional: running text's size and line length (see site-templates).
  - `looks` (site-kit#413, optional): `{"label": the menu's one-line text, "variants": two or more looks, the default first}`. The brand check holds that shape; each look is checked by theme-picker at the build (see site-templates). Static-only.
  - `bands.<name>.font` (optional): a role of the brand's `fonts` (e.g. `"text"`); that band's headings use it. The check refuses a role the brand does not define. Static-only.
  - `bands.<name>.accent` (optional, `light` and `dark` only): the accent inside that band and a footer on it, for its links, focus rings and marks; it wins over the page's accent and every `looks` variant's. Use it when no one accent reads on both the page and the band (a dark footer under a light variant). The build refuses one under 4.5:1 on the band's `ground`. Static-only.
  - `bands.<name>.focus` (optional, `light`, `dark` and `card`, site-kit#499): the focus ring's colour inside that band and a footer on it, where the accent is too light for the band (a ring needs 3:1). Without one, the ring keeps the accent, and a site with no band `focus` builds exactly as before. The build refuses one under 3:1 on the band's `ground`, and for `card` on `colours.surface` too. Static-only.
  - `header.in_card: true`: with `main: "card"`, the header (banner and menu) sits inside the same surface card as main, one card on the ground; the footer stays outside. Refused without `main: "card"`.
  - `header.nav_align: "left"`: the menu row at the left (under the banner, or under the logo row without one). Refused with `header.align: "center"`.
  - `header.nav_current: "bar"`: the current menu item gets a 4px accent bar under it in place of the underline.
  - `header.nav_home: true`: Home goes first in the menu, labelled "Home". Refused (by the layout check) when `layout.json` sets its own `menu`. (Pages have no `nav` title, so the label is always "Home".)
  - `headings`: `{"case": "upper", "size": "small"}`, each optional, nothing else. `case` uppercases the page title and section headings; `size` steps the heading scale down one step on a fixed scale (h1 clamp(1.6rem,4vw,2.25rem), h2 clamp(1.35rem,2.5vw,1.6rem), h3 1.1rem), written in the conditional style so `blocks.css` is unchanged. The colour is `colours.heading`.
  - `bands.card`: exactly `{"ground": hex}` (no ink): the strip behind a `band: "card"` run. Unset, the strip is the page's `ground`. Consecutive `band: "card"` sections share ONE `colours.surface` card (a rule, no key): it opens with the first and closes after the last, and a non-card section between two splits them into two cards. `bands.card.ground` reaches theme.json's palette as `band-card-ground`; the card styles are static-only.
  - `footer`: `{"band": "light" | "dark"}`, one key, nothing else: the footer takes that band's `ground` and `ink` from `bands`, as a section does. Refused when the brand does not define that band. Static-only.
  - `header.nav_style: "muted"`: the menu (header, and a hero's menu) takes the `muted` colour at a lighter weight; the current page keeps the text's own colour (the band's, inside a band), with the accent as its underline or bar (site-kit#370: accent text fails contrast on a light ground). Static-only.
  - Unset, each of these changes nothing (the page builds byte for byte as before). WordPress export: `surface` and the bands' colours reach theme.json's palette (`surface`, `band-<name>-ground`, `band-<name>-ink`); the card, alignment, logo size and band styles are static-only.
  - Any other `header` key, or any other value, is refused. A header knob a site needs that is not here comes back to site-kit as a new named knob.
- Icons are PNGs at the size their key names, and `ico` is an `.ico` file. A missing or empty file fails.
- Colours are `#rgb` or `#rrggbb`, keyed by role. The site decides which roles it reads.
- `support.url` is `https://`.

## The checks

```bash
python3 skills/brand/brand.py --check .sitekit/brand.json            # in CI, for every record
python3 skills/brand/brand.py --leak .sitekit/brand.json brands/smartwebutah.json dist-smartwebutah
```

`--leak A B BUILD_B` fails if the build of brand B has any of these:
- A's `short_name` as a whole word, case-insensitively, so "Tell Foo" fails and "food" or `.foo-card` doesn't. A hyphen joins a word, so a hyphenated "Foo-powered" isn't caught either: search the build by hand for those. A short name under 3 letters is skipped. Wordmark parts aren't guessed at, because they're often common words; set `short_name` for what people call the brand.
- A's name, wordmark, support email, support URL or their domains in a text file, read the way a person sees it: tags dropped (attributes are still read), entities decoded, NFKC, every run of space folded. A `.gz` file is opened first. Brotli (`.br`) files are not opened;
- a file named like one of A's icon or share files, unless B uses the same name;
- a file with the same bytes as one of A's.

If the two brands share a name, wordmark or support link, it refuses to run, because a leak couldn't be told apart.

## A site taking it

1. Write `.sitekit/brand.json`, and add `--check` to CI.
2. Make the build read every brand value from the record.
3. Build once with a second record and run `--leak` on that build in CI.
4. List `brand` in `.sitekit/features.json` with the issue number.
