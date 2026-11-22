from argparse import ArgumentParser
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from subprocess import check_output

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
PIORA_REV = "3d931edd4f197370e43ddb3ef3108104ec22f819"
PIORA = f"https://github.com/kexijiang/pi-desktop/blob/{PIORA_REV}"
REPO = "https://github.com/kexijiang/dsh-piora-themes"
CC = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
SIZE = (960, 540)


def rgb(hex_color):
    return tuple(bytes.fromhex(hex_color[1:7]))


def color(channels):
    return "#" + bytes(channels).hex()


def mix(first, second, fraction):
    return color(round(a + (b - a) * fraction) for a, b in zip(rgb(first), rgb(second)))


def luminance(hex_color):
    def linear(channel):
        value = channel / 255
        if value <= 0.04045:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    return sum(w * linear(v) for w, v in zip((0.2126, 0.7152, 0.0722), rgb(hex_color)))


def contrast(first, second):
    brighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (brighter + 0.05) / (darker + 0.05)


def readable(foreground, fallback, *surfaces):
    for step in range(21):
        candidate = mix(foreground, fallback, step / 20)
        if all(contrast(candidate, surface) >= 4.5 for surface in surfaces):
            return candidate
    raise ValueError(f"{foreground} cannot reach 4.5:1 on {surfaces}")


def alpha(hex_color, opacity):
    return hex_color + f"{round(opacity * 255):02x}"


def palette(spec, mode):
    base, panel, text, accent, _ = spec
    dark = mode == "dark"
    hover = mix(panel, accent, 0.11)
    selected = mix(panel, accent, 0.20)
    user = mix(panel, accent, 0.15)
    background = (base, panel, hover, selected, user)
    accent = readable(accent, text, *background)
    accent_hover = mix(accent, text, 0.14)
    secondary = readable(mix(text, base, 0.29), text, *background)
    tertiary = readable(mix(text, base, 0.41), text, *background)
    on_accent = "#090a0c" if dark else "#ffffff"
    if min(contrast(on_accent, shade) for shade in (accent, accent_hover)) < 4.5:
        accent = readable(accent, text, *background, on_accent)
        accent_hover = mix(accent, text, 0.14)
    return {
        "base": base,
        "canvas": alpha(base, 0.18),
        "panel": panel,
        "sidebar": alpha(panel, 0.83 if dark else 0.79),
        "raised": panel,
        "hover": hover,
        "selected": selected,
        "border": mix(panel, text, 0.22),
        "border-strong": mix(panel, text, 0.43),
        "text": text,
        "secondary": secondary,
        "tertiary": tertiary,
        "accent": accent,
        "accent-hover": accent_hover,
        "on-accent": on_accent,
        "user": user,
        "composer": alpha(panel, 0.96),
        "code": panel,
        "code-heading": mix(panel, text, 0.11),
        "added": mix(panel, "#458c60", 0.29 if dark else 0.20),
        "deleted": mix(panel, "#be5763", 0.31 if dark else 0.20),
        "error": readable("#f3a2a1" if dark else "#a83240", text, panel, selected),
        "success": readable("#9fd7ae" if dark else "#3a6742", text, panel, selected),
        "warn": readable("#efca80" if dark else "#785522", text, panel, selected),
        "warn-bg": mix(panel, "#b58a48", 0.22),
        "popup": panel,
        "toast": panel if dark else text,
        "on-toast": text if dark else panel,
        "reading": alpha(base, 0.53 if dark else 0.54),
    }


def css_block(selector, mode, colors):
    lines = [f"{selector} {{", f"  color-scheme: {mode};"]
    lines.extend(f"  --piora-{key}: {value};" for key, value in colors.items())
    return "\n".join([*lines, "}"])


def rgba(hex_color, opacity):
    return f"rgba({', '.join(str(v) for v in rgb(hex_color))}, {opacity:.2f})"


def scrim(spec):
    base, _, _, _, (left, middle, right) = spec
    return f"linear-gradient(90deg, {rgba(base, left)}, {rgba(base, middle)} 55%, {rgba(base, right)} 86%)"


def gradient(image, hex_color, stops):
    width, height = image.size
    mask = Image.new("L", (width, 1))
    for (start, before), (end, after) in zip(stops, stops[1:]):
        for x in range(start, end):
            opacity = before + (after - before) * (x - start) / (end - start)
            mask.putpixel((x, 0), round(opacity * 255))
    shade = Image.new("RGBA", image.size, rgb(hex_color))
    shade.putalpha(mask.resize((width, height), Image.Resampling.NEAREST))
    image.alpha_composite(shade)


def draw_preview(art, name, scene, spec, colors, path):
    image = ImageOps.fit(art, SIZE, Image.Resampling.LANCZOS).convert("RGBA")
    left, middle, right = spec[4]
    width, _ = SIZE
    gradient(image, colors["base"], [(0, left), (528, middle), (826, right), (width, right)])
    gradient(image, colors["base"], [(0, 0.45), (493, 0.45), (680, 0), (width, 0)])

    draw = ImageDraw.Draw(image, "RGBA")
    ink = colors["text"]
    dim = colors["secondary"]
    edge = colors["border"]
    accent = colors["accent"]

    def label(x, y, text, size, ink=ink):
        draw.text((x, y), text, fill=ink, font=ImageFont.load_default(size=size))

    def surface(box, radius, fill, stroke=None):
        draw.rounded_rectangle(box, radius, fill=fill, outline=stroke, width=1)

    draw.rectangle((0, 0, 181, 540), fill=colors["sidebar"])
    draw.line((181, 0, 181, 540), fill=edge)
    label(24, 32, "DSH NEXT", 19)
    surface((19, 72, 162, 117), 11, colors["panel"], edge)
    label(36, 84, "+  New chat", 15)
    label(27, 150, "Workspace", 13, dim)
    surface((19, 181, 162, 221), 9, colors["selected"])
    draw.ellipse((30, 195, 40, 205), fill=accent)
    label(49, 191, "Theme preview", 13)
    label(219, 37, "Appearance", 13, dim)
    draw.line((219, 66, 617, 66), fill=edge)

    surface((279, 109, 629, 167), 15, colors["user"], edge)
    label(301, 125, "How does this palette look?", 18)
    label(219, 205, name, 32)
    label(220, 250, scene, 17)
    label(220, 278, "Chat, controls and code in matching tones.", 14, dim)
    surface((219, 317, 591, 377), 10, colors["code"], edge)
    label(237, 337, "accent", 15, dim)
    surface((318, 334, 361, 359), 7, accent)
    label(374, 337, accent, 15, accent)

    surface((212, 435, 631, 510), 16, colors["composer"], edge)
    label(232, 462, "Write a message…", 16, dim)
    surface((580, 452, 615, 488), 10, accent)
    draw.line((590, 468, 597, 461, 604, 468), fill=colors["on-accent"], width=2)
    draw.line((597, 461, 597, 480), fill=colors["on-accent"], width=2)
    image.convert("RGB").save(path, quality=87, optimize=True, progressive=True)


def from_piora(checkout, path):
    return check_output(["git", "-C", str(checkout), "show", f"{PIORA_REV}:{path}"])


def generate(checkout):
    specs = json.loads((ROOT / "scripts/themes.json").read_text(encoding="utf-8"))
    template = (ROOT / "scripts/skin-template.css").read_text(encoding="utf-8")
    provenance_path = ROOT / "scripts/artwork-sources.json"
    if checkout:
        path = "public/themes/character-backgrounds/provenance.json"
        upstream = json.loads(from_piora(checkout, path))
        references = {item["id"]: item["source"] for item in upstream["artwork"]}
        sources = {}
    else:
        sources = json.loads(provenance_path.read_text(encoding="utf-8"))

    for index, spec in enumerate(specs, start=1):
        file = spec["file"]
        character = spec["family"] == "character"
        id_ = f"piora-{file.removeprefix('anime-')}"
        directory = ROOT / "skins" / id_
        filename = f"{file}.webp"
        asset = f"assets/{filename}"
        artwork_path = directory / asset
        source_path = f"public/themes/{spec['family']}-backgrounds/{filename}"
        (directory / "assets").mkdir(parents=True, exist_ok=True)
        (directory / "preview").mkdir(exist_ok=True)

        if checkout:
            original = from_piora(checkout, source_path)
            artwork_path.write_bytes(original)
            sources[id_] = {"upstream": f"{PIORA}/{source_path}", "sha256": sha256(original).hexdigest()}
            if character:
                sources[id_]["reference"] = references[f"character-{file}"]["url"]
        else:
            original = artwork_path.read_bytes()
            if sha256(original).hexdigest() != sources[id_]["sha256"]:
                raise ValueError(f"The source image for {id_} differs from the pinned artwork")

        source = sources[id_]
        attribution = "Piora contributors"
        if character:
            attribution += ", original design by ZipZipPipe, supplemental sheets by lmy414"
        manifest = {
            "$schema": "https://schemas.linxin666.org/dsh-skin/v2.json",
            "skinManifestVersion": 2,
            "id": id_,
            "name": spec["name"],
            "nameEn": f"{spec['name']} · {spec['title']}",
            "version": VERSION,
            "author": "Piora contributors",
            "tagline": spec["tagline"],
            "description": f"{spec['title']}。{spec['tagline']}，亮暗配色共享同一幅 Piora 背景。",
            "accent": palette(spec["light"], "light")["accent"],
            "order": 100 + index,
            "tags": ["piora", spec["family"], "light", "dark"],
            "license": "CC BY-NC-SA 4.0 (artwork), MIT (CSS)" if character else "MIT",
            "licenseUrl": CC if character else f"{REPO}/blob/main/LICENSE",
            "noticeUrl": f"{REPO}/blob/main/NOTICE.md",
            "sourceUrl": source["upstream"],
            "attribution": attribution,
            "contributes": {"stylesheet": "skin.css", "backgroundMedia": {}},
            "preview": {},
        }

        blocks = ["/* Piora artwork palette. See NOTICE.md. */"]
        with Image.open(BytesIO(original)) as art:
            for mode, selector in (("light", ":root"), ("dark", "body[data-ds-dark-theme]")):
                colors = palette(spec[mode], mode)
                blocks.append(css_block(selector, mode, colors))
                manifest["contributes"]["backgroundMedia"][mode] = {
                    "type": "image", "src": asset, "scrim": scrim(spec[mode]),
                }
                preview = f"preview/{mode}.jpg"
                draw_preview(art, spec["title"], spec["scene"], spec[mode], colors, directory / preview)
                manifest["preview"][mode] = preview

        (directory / "skin.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (directory / "skin.css").write_text("\n\n".join([*blocks, template]), encoding="utf-8")
        notice = [
            f"# {spec['name']} · {spec['title']}",
            "",
            f"- [Piora artwork]({source['upstream']})",
            f"- Original asset SHA-256: `{source['sha256']}`",
        ]
        if character:
            notice.extend([
                f"- [Reference by lmy414]({source['reference']})",
                "- Original character design: [ZipZipPipe（胖次狐）](https://space.bilibili.com/4168597)",
                f"- Piora's new adaptation contribution and its card previews: [CC BY-NC-SA 4.0]({CC}). Original design rights are retained.",
            ])
        else:
            notice.append("- Original Piora scenery and its card previews: MIT.")
        notice.append("- Adaptation for DSH: the WebP is unchanged. We added a stylesheet and composited the illustrative card previews.")
        notice.append(f"- [Full attribution and license]({REPO}/blob/main/NOTICE.md)")
        (directory / "NOTICE.md").write_text("\n".join(notice) + "\n", encoding="utf-8")

    if checkout:
        provenance_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = ArgumentParser(description="Regenerate the DSH palettes and card previews.")
    parser.add_argument("--piora", type=Path, help="Optional Piora checkout for restoring the pinned source artwork")
    generate(parser.parse_args().piora)
