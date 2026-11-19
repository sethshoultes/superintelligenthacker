# superintelligenthacker

Super Intelligent Hacker is the hacker on your side: a check of your own website, the way someone trying to get in would look at it, then plain words on how to shut each door. Only your site, only with your say-so. The check is coming; it isn't running yet. This repo is its site, superintelligenthacker.com, in the Key, Foo and Memory family.

- **Edit:** `.sitekit/layout.json` (the pages) and `.sitekit/brand.json` (the brand). `brand/` comes from `brand/mark.html` and `brand/share.html`: `scripts/make-brand.sh` makes the icons and the share image.
- **Build:** `./build.sh` writes `dist/`.
- **Deploy:** the Cloudflare Pages project `superintelligenthacker` in Seth's personal Cloudflare account: `wrangler pages deploy dist --project-name superintelligenthacker --branch main`.
- **Kit:** `skills/` and the kit's files in `.sitekit/` are vendored from site-kit by `site_sync.py`. Change them only with `site_sync.py sync <tag>`, never by hand.

Source: https://github.com/sethshoultes/superintelligenthacker

Refs sethshoultes/superintelligenthacker#1
