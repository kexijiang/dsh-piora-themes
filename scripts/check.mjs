import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { installSkins } from "../index.js";

const root = fileURLToPath(new URL("../", import.meta.url));
const skinRoot = join(root, "skins");
const ids = readdirSync(skinRoot).sort();
const origins = JSON.parse(readFileSync(join(root, "scripts", "artwork-sources.json"), "utf8"));
const version = JSON.parse(readFileSync(join(root, "package.json"), "utf8")).version;

function asset(dir, relative) {
  assert.match(relative, /^[a-z0-9_-]+\/[a-z0-9_.-]+$/);
  return readFileSync(join(dir, relative));
}

function luminance(hex) {
  const rgb = hex.match(/[0-9a-f]{2}/gi).map((byte) => parseInt(byte, 16) / 255);
  const linear = rgb.map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrast(first, second) {
  const [dark, light] = [luminance(first), luminance(second)].sort((a, b) => a - b);
  return (light + 0.05) / (dark + 0.05);
}

test("14 Skin Center v2 entries have separate palettes and complete local artwork", () => {
  assert.equal(ids.length, 14);
  assert.deepEqual(Object.keys(origins).sort(), ids);
  const hashes = new Set();
  const accents = new Set();
  for (const id of ids) {
    const dir = join(skinRoot, id);
    const manifest = JSON.parse(readFileSync(join(dir, "skin.json"), "utf8"));
    assert.equal(manifest.id, id);
    assert.equal(manifest.version, version);
    assert.equal(manifest.skinManifestVersion, 2);
    assert.equal(manifest.sourceUrl, origins[id].upstream);
    const { light, dark } = manifest.contributes.backgroundMedia;
    assert.equal(light.type, "image");
    assert.equal(dark.type, "image");
    assert.equal(light.src, dark.src);
    assert.notEqual(light.scrim, dark.scrim);
    const webp = asset(dir, light.src);
    assert.equal(webp.toString("ascii", 8, 12), "WEBP");
    const hash = createHash("sha256").update(webp).digest("hex");
    assert.equal(hash, origins[id].sha256);
    hashes.add(hash);
    accents.add(manifest.accent);

    const lightPreview = asset(dir, manifest.preview.light);
    const darkPreview = asset(dir, manifest.preview.dark);
    for (const preview of [lightPreview, darkPreview]) {
      assert.equal(preview.readUInt16BE(0), 0xffd8, `${id} preview has a JPEG header`);
      assert.equal(preview.readUInt16BE(preview.length - 2), 0xffd9, `${id} preview is complete`);
    }
    assert.notDeepEqual(lightPreview, darkPreview);
    assert.ok(existsSync(join(dir, "NOTICE.md")));

    assert.equal(manifest.contributes.stylesheet, "skin.css");
    const css = readFileSync(join(dir, "skin.css"), "utf8");
    const blocks = [...css.matchAll(/color-scheme: (light|dark);([^}]+)/g)];
    assert.deepEqual(blocks.map((block) => block[1]), ["light", "dark"]);
    for (const [, mode, properties] of blocks) {
      const colors = Object.fromEntries([...properties.matchAll(/--piora-([\w-]+): (#[0-9a-f]+);/g)]
        .map(([, key, value]) => [key, value]));
      for (const surface of ["base", "panel", "selected", "user"]) {
        for (const ink of ["text", "secondary", "tertiary", "accent"]) {
          assert.ok(contrast(colors[ink], colors[surface]) >= 4.5, `${id} ${mode} ${ink} on ${surface}`);
        }
      }
      for (const fill of ["accent", "accent-hover"]) {
        assert.ok(contrast(colors["on-accent"], colors[fill]) >= 4.5, `${id} ${mode} button label`);
      }
    }
  }
  assert.equal(hashes.size, 14);
  assert.equal(accents.size, 14);
});

test("installation fills missing skins and preserves existing ones", () => {
  const temp = realpathSync(tmpdir());
  const fixture = mkdtempSync(join(temp, "dsh-piora-check-"));
  try {
    const target = join(fixture, "skins");
    const first = ids[0];
    const local = join(target, first, "skin.json");
    cpSync(join(skinRoot, first), join(target, first), { recursive: true });
    const changed = JSON.parse(readFileSync(local, "utf8"));
    changed.name = "Locally customized";
    writeFileSync(local, JSON.stringify(changed));
    const { installed, existing } = installSkins(target);
    assert.deepEqual(installed.sort(), ids.slice(1));
    assert.deepEqual(existing, [first]);
    assert.deepEqual(readdirSync(target).sort(), ids);

    for (const id of installed) {
      const dir = join(target, id);
      const skin = JSON.parse(readFileSync(join(dir, "skin.json"), "utf8"));
      const paths = [skin.preview.light, skin.preview.dark, skin.contributes.backgroundMedia.light.src, "skin.css", "NOTICE.md"];
      for (const path of paths) {
        assert.deepEqual(readFileSync(join(dir, path)), readFileSync(join(skinRoot, id, path)));
      }
    }
    assert.deepEqual(installSkins(target), { installed: [], existing: ids });
    assert.deepEqual(JSON.parse(readFileSync(local, "utf8")), changed);
    assert.deepEqual(readdirSync(fixture), ["skins"]);
  } finally {
    if (dirname(resolve(fixture)) === temp && basename(fixture).startsWith("dsh-piora-check-")) {
      rmSync(fixture, { recursive: true, force: true });
    }
  }
});
