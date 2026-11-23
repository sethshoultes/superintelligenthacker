// plugins/official-embed (site-kit#380): the render command as a page builder runs it. Its output is Instagram's blockquote with
// the plain link inside and one async embed.js; a refusal prints nothing on stdout and exits 1. Every case is in
// tests/test_official_embed_plugin.py.
const test = require("node:test");
const assert = require("node:assert");
const { spawnSync } = require("node:child_process");
const { mkdtempSync, writeFileSync, rmSync } = require("node:fs");
const { tmpdir } = require("node:os");
const path = require("node:path");

const PLUGIN = path.join(__dirname, "..", "plugin.py");
function run(config) {
  const dir = mkdtempSync(path.join(tmpdir(), "official-embed-"));
  try {
    const file = path.join(dir, "config.json");
    writeFileSync(file, JSON.stringify(config));
    return spawnSync("python3", [PLUGIN, "render", "--config", file], { encoding: "utf8" });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test("a profile renders as Instagram's blockquote, the fallback link inside, one async embed.js", () => {
  const out = run({ platform: "instagram", url: "https://www.instagram.com/redrockmodernquilt/", link_text: "See us on Instagram" });
  assert.strictEqual(out.status, 0, out.stderr);
  assert.match(out.stdout, /^<blockquote class="instagram-media" data-instgrm-permalink="https:\/\/www\.instagram\.com\/redrockmodernquilt\/"[^>]*><a href="https:\/\/www\.instagram\.com\/redrockmodernquilt\/" rel="noopener">See us on Instagram<\/a><\/blockquote><script async src="https:\/\/www\.instagram\.com\/embed\.js"><\/script>\n$/);
});

test("another host is refused: nothing on stdout, the reason on stderr, exit 1", () => {
  const out = run({ platform: "instagram", url: "https://evil.test/x/", link_text: "x" });
  assert.strictEqual(out.status, 1);
  assert.strictEqual(out.stdout, "");
  assert.match(out.stderr, /^refused: official-embed: url must be/);
});

// site-kit#573: the YouTube facade script, run against a small fake DOM. Nothing is created on load; one click makes one
// youtube-nocookie.com iframe with autoplay=1; a bad id does nothing.
const fs = require("node:fs");
const vm = require("node:vm");
function facade(id) {
  const made = [];
  const poster = { removed: false, remove() { this.removed = true; } };
  const frame = { attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, focus() { this.focused = true; } };
  const button = { hidden: true, handlers: {}, addEventListener(e, f) { this.handlers[e] = f; }, replaceWith(x) { this.replacedWith = x; } };
  const box = { getAttribute: (k) => ({ "data-video-id": id, "data-title": "Meet Foo" })[k],
                querySelector: (s) => (s.endsWith("__play") ? button : poster) };
  const document = { querySelectorAll: () => [box], createElement: (tag) => { made.push(tag); return frame; } };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "..", "assets", "official-embed.js"), "utf8"), { document, Array });
  return { made, frame, button, poster };
}

test("youtube facade: load only turns the button on; nothing is created until the click", () => {
  const { made, button } = facade("LRpT3j0kSx8");
  assert.strictEqual(button.hidden, false);
  assert.deepStrictEqual(made, []);
});

test("youtube facade: one click swaps in one youtube-nocookie iframe with autoplay, and removes the poster", () => {
  const { made, frame, button, poster } = facade("LRpT3j0kSx8");
  button.handlers.click();
  assert.deepStrictEqual(made, ["iframe"]);
  assert.strictEqual(frame.src, "https://www.youtube-nocookie.com/embed/LRpT3j0kSx8?rel=0&autoplay=1");
  assert.strictEqual(frame.title, "Meet Foo");
  assert.strictEqual(button.replacedWith, frame);
  assert.strictEqual(poster.removed, true);
});

test("youtube facade: a bad id leaves the button off and the link alone", () => {
  for (const id of ["short", "LRpT3j0kSx8/../x", "", null]) {
    const { made, button } = facade(id);
    assert.strictEqual(button.hidden, true);
    assert.strictEqual(button.handlers.click, undefined);
    assert.deepStrictEqual(made, []);
  }
});
