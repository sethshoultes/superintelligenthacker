"""official-embed (site-kit#380, #573): a platform's own embed in a site-templates slot, Instagram first, then YouTube.

A config is one embed. Instagram: `platform`, `url` (the profile or post) and `link_text` (the words of the plain link that
shows when the embed can't load); `render(config)` returns Instagram's own markup: its `instagram-media` blockquote, holding the
plain link, then its embed.js. With no script, or with embed.js blocked, the blockquote stays and its link is the fallback.

YouTube (site-kit#573): `platform`, `video_id` (11 characters), `title`, `poster` (a site-local image), `link_text` and an optional `priority` (true: the poster loads eagerly, for a video in the first screen). It renders
a facade: the poster, a play button and a plain link to the video. Nothing goes to YouTube on page load: the build links
this plugin's own same-origin script (slot_assets), which turns the button on, and on a click swaps in a youtube-nocookie.com
iframe. With no script the poster and the link remain.

Refused, with a plain reason: a missing or unknown setting, a platform this plugin doesn't know, a URL that is not https on
www.instagram.com, that carries a query, fragment, username or password, or whose path is not a profile (/<name>/) or a
post (/p/<id>/, /reel/<id>/, /tv/<id>/), and a control character in any setting. A refusal never echoes the URL.

    python3 plugins/official-embed/plugin.py render --config <file.json>"""
import argparse
import html
import json
import pathlib
import re
import sys
import urllib.parse

FIELDS = json.loads((pathlib.Path(__file__).resolve().parent / "plugin.json").read_text())["config"]["fields"]
SETTINGS = {"instagram": ("platform", "url", "link_text"), "youtube": ("platform", "video_id", "title", "poster", "link_text", "priority")}
OPTIONAL = {"priority"}
CONTROL = re.compile("[\x00-\x1f\x7f\x85  ]")
# A profile name has a letter, digit or underscore (so never "." or ".."), and is not one of Instagram's own paths.
INSTAGRAM_PATH = re.compile(r"/(?:(?:p|reel|tv)/[A-Za-z0-9_-]{1,64}|(?!(?:p|reel|tv|explore|accounts|stories|direct|reels|about|developer|legal)/)(?=[A-Za-z0-9._]*[A-Za-z0-9_])[A-Za-z0-9._]{1,30})/")
SCRIPT = {"instagram": "https://www.instagram.com/embed.js", "youtube": None}
LINK_LIMIT = 100
TITLE_LIMIT = 100
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
# A site-local image: one leading slash, plain path segments (no "..", no "//", no host), a web image extension.
POSTER = re.compile(r"/(?:[A-Za-z0-9_-][A-Za-z0-9._-]*/)*[A-Za-z0-9_-][A-Za-z0-9._-]*\.(?:webp|png|jpe?g|avif)")

hooks = {}


def checked(config):
    if not isinstance(config, dict):
        raise ValueError("official-embed: the config must be a JSON object of settings")
    platform = config.get("platform")
    if not isinstance(platform, str) or not platform.strip():
        raise ValueError('official-embed: "platform" is required and must be a non-empty string')
    if platform not in SCRIPT:
        raise ValueError(f'official-embed: platform "{platform}" is not one this plugin knows: {", ".join(SCRIPT)}')
    keys = SETTINGS[platform]
    for key in sorted(set(config) - set(keys)):
        raise ValueError(f'official-embed: "{key}" is not a setting for {platform}. Settings: {", ".join(keys)}')
    if "priority" in config and not isinstance(config["priority"], bool):
        raise ValueError('official-embed: "priority" must be the JSON value true or false')
    for key in keys:
        if key in OPTIONAL:
            continue
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f'official-embed: "{key}" is required and must be a non-empty string')
        if CONTROL.search(config[key]):
            raise ValueError(f'official-embed: "{key}" has a control character or line break; it must be one line')
    if len(config["link_text"]) > LINK_LIMIT:
        raise ValueError(f"official-embed: link_text is longer than {LINK_LIMIT} characters")
    if platform == "youtube":
        if not VIDEO_ID.fullmatch(config["video_id"]):
            raise ValueError("official-embed: video_id must be the 11 characters of a YouTube video id (letters, digits, - and _)")
        if len(config["title"]) > TITLE_LIMIT:
            raise ValueError(f"official-embed: title is longer than {TITLE_LIMIT} characters")
        if not POSTER.fullmatch(config["poster"]):
            raise ValueError("official-embed: poster must be a site-local image path such as /assets/poster.webp "
                             "(one leading slash, no host, no .., a .webp, .png, .jpg, .jpeg or .avif file)")
        return config
    try:
        u = urllib.parse.urlsplit(config["url"])
        host = u.hostname
    except ValueError:
        u, host = None, None
    if (u is None or u.scheme != "https" or host != "www.instagram.com" or u.port is not None or "@" in u.netloc
            or u.query or u.fragment or not INSTAGRAM_PATH.fullmatch(u.path)):
        raise ValueError("official-embed: url must be https://www.instagram.com/ and a profile (/<name>/) or a post "
                         "(/p/<id>/, /reel/<id>/, /tv/<id>/), with no query or fragment")
    return config


def render(config):
    c = checked(config)
    text = html.escape(c["link_text"], quote=True)
    if c["platform"] == "youtube":
        vid = c["video_id"]
        title = html.escape(c["title"], quote=True)
        load = 'loading="eager" fetchpriority="high"' if c.get("priority") is True else 'loading="lazy"'
        return (f'<div class="official-embed-youtube" data-video-id="{vid}" data-title="{title}">'
                f'<img class="official-embed-youtube__poster" src="{html.escape(c["poster"], quote=True)}" alt="" width="1280" height="720" {load} decoding="async">'
                f'<button type="button" class="official-embed-youtube__play" aria-label="Play video: {title}" hidden></button>'
                f'<a class="official-embed-youtube__link" href="https://www.youtube.com/watch?v={vid}" rel="noopener">{text}</a></div>')
    url = html.escape(c["url"], quote=True)
    return (f'<blockquote class="instagram-media" data-instgrm-permalink="{url}" data-instgrm-version="14">'
            f'<a href="{url}" rel="noopener">{text}</a></blockquote>'
            f'<script async src="{SCRIPT[c["platform"]]}"></script>')


def main(argv=None):
    parser = argparse.ArgumentParser(prog="plugin.py", description="Print one official embed for a config file.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("render", help="print the embed for one config").add_argument("--config", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        print(render(json.loads(args.config.read_text())))
    except (OSError, json.JSONDecodeError, ValueError) as err:
        print(f"refused: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
