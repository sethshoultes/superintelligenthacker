# official-embed

A platform's own embed in a site-templates slot (site-kit#380): Instagram first, a profile or a post. It renders the markup
Instagram itself gives, its `instagram-media` blockquote and `embed.js`, with a plain link inside the blockquote. With no script,
or with `embed.js` blocked, the blockquote stays and the link is what the visitor sees.

## Settings (one config = one embed)

| Setting | What it is |
|---|---|
| `platform` | `instagram` or `youtube` |
| `url` | `https://www.instagram.com/<profile>/`, or a post: `/p/<id>/`, `/reel/<id>/`, `/tv/<id>/`. No query or fragment |
| `link_text` | The plain link's words, such as `See us on Instagram`, at most 100 characters |

Anything else is refused with a plain reason that never echoes the URL: an unknown or missing setting, another host, `http:`, a
port, a username or password, a query or fragment, a path that is not a profile or a post, or a control character.

```json
{"slots": {"instagram": {"plugin": "official-embed", "config": "plugins-config/instagram.json"}}}
```

## The page's CSP

The embed needs Instagram's script and frame, and only on the page that holds it. Cloudflare Pages' `_headers` can give that page
its own policy: `! Content-Security-Policy` detaches the site-wide one there, and the line after it is the site's own policy with
**exactly these two additions**, nothing wider:

- `script-src` gains `https://www.instagram.com`
- `frame-src` gains `https://www.instagram.com`

```
/instagram/
  ! Content-Security-Policy
  Content-Security-Policy: <the site-wide policy, with the two additions above>
```

Every other page keeps the site-wide policy, so no other page can load Instagram's script.

## Rendering

```bash
python3 plugins/official-embed/plugin.py render --config <file.json>
```

## YouTube (site-kit#573)

`platform: "youtube"` is a facade, not an embed: the page holds a poster, a play button and a plain link, and **nothing goes to
YouTube or Google until the click**. The build links this plugin's own same-origin script and stylesheet on the slot's page
(`slot_assets`); the script turns the button on, and one press swaps the poster for an iframe on
`https://www.youtube-nocookie.com/embed/<id>?rel=0&autoplay=1`, so that press is what starts the video. Nothing plays on load. With
no script the poster and the link stay. (An Instagram slot's page also gets the two files; they do nothing there.)

| Setting | What it is |
|---|---|
| `platform` | `youtube` |
| `video_id` | The 11 characters of the video id, `[A-Za-z0-9_-]`. Anything else is refused, and the id is never echoed |
| `title` | The play button's accessible name and the iframe's title, at most 100 characters |
| `poster` | A site-local image, `/assets/...` (`.webp`, `.png`, `.jpg`, `.jpeg`, `.avif`); no host and no `..`. Never `i.ytimg.com`, so nothing goes to Google before the click |
| `link_text` | The plain link's words, at most 100 characters; it goes to `https://www.youtube.com/watch?v=<id>` |
| `priority` | Optional, `true` or `false` (default `false`). `true` loads the poster eagerly with `fetchpriority="high"`: only for a video in the first screen that has no hero image of its own. Anything but a JSON boolean is refused |

```json
{"slots": {"video": {"plugin": "official-embed", "config": "plugins-config/video.json"}}}
```

### The page's CSP

`frame-src` gains `https://www.youtube-nocookie.com` and nothing else: no `script-src` addition, since the script is the kit's
own and same-origin. Put it on the page that holds the video (the Instagram `_headers` pattern above), or on the site-wide
policy if one page-scoped line is not worth it.

### Privacy

The site's `privacy-processors.json` gets a YouTube row that names the click as the trigger: the visitor presses play, and only
then does their browser reach youtube-nocookie.com.
