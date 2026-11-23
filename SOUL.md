# SOUL: Super Intelligent Hacker

The first file a builder reads on this site (site-kit#6). A draft from the intake: the owner edits it.

## Style guide (read this first)

- [`canon/STYLEGUIDE.md`](canon/STYLEGUIDE.md): the words, the look and the pictures.
- Brand assets: `.sitekit/brand.json` and the icons it names.

## Who it is for

Visitors are people who run a website and want to know how someone trying to get in would see it. We want them to read what the check will look at and how it works, and come back when it runs.

## Voice and look

- **Voice:** plain, calm and on your side: the hacker who helps you shut each door, never one who scares you.
- **Look:** deep green ground, cream ink and an amber accent, Bangers headings over Comic Neue text, the family comic panels.

## Non-negotiables

- Facts only from the owner: no invented names, prices, reviews, results or photos.
- No authorship, persona or "AI-made" label on any page.
- Every page keeps its address; a page that moves is redirected.
- Accessibility and privacy as the public-site standard says.
- The check is coming and isn't running yet: no page says it runs today.
- Only the visitor's own site, only with their say-so.
- No real names or real sites as examples.

## Reuse (from the site-kit catalog)

Check [`CATALOG.md`](https://github.com/sethshoultes/site-kit/blob/main/CATALOG.md) before building anything. A new content
type or feature starts as a site-kit plugin proposal, not as code.

- **Plugins used:** agent-files: markdown twins, /a2a and /mcp
- **Skills used:** site-templates (the `product` starter, site-kit v0.96.191)
- **Image, voice and text recipes used:** none
- **Style recipes used:** none

## Where things live

- The brain: this file, the style guide, and `.agent/memory/` (one line per change).
- The page record is `.sitekit/layout.json`; edit it with `skills/site-templates/ops.py` and rebuild with `skills/site-templates/build.py`.
- The pages are .sitekit/layout.json and the brand is .sitekit/brand.json.
- The build is ./build.sh, which writes dist/.
- The deploy is the Cloudflare Pages project superintelligenthacker.
