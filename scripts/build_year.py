"""Build assets/year.svg from the generated 3D contribution graph."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "profile-3d-contrib" / "profile-night-rainbow.svg"
OUTPUT = ROOT / "assets" / "year.svg"

NS = "{http://www.w3.org/2000/svg}"
BASE_X = 140.0
BASE_Y = 154.18
LANG_COLORS = ("#58a6ff", "#79c0ff", "#388bfd", "#1f6feb", "#484f58")


def text_of(node: ET.Element) -> str:
    return "".join(node.itertext()).strip()


def flat_point(group: ET.Element) -> tuple[float, float, float]:
    height = 2.6
    flat = None
    for child in group:
        name = child.tag.split("}")[-1]
        if name == "animateTransform":
            flat = child.attrib.get("values", "").split(";")[0].strip()
        klass = child.attrib.get("class", "")
        if klass.endswith("-left") and child.attrib.get("height"):
            height = float(child.attrib["height"])
    if flat:
        x_text, y_text = flat.split()
        return float(x_text), float(y_text), max(0.0, height - 2.6)
    transform = group.attrib.get("transform", "")
    parts = transform.replace("translate(", "").replace(")", "").replace(",", " ").split()
    return float(parts[0]), float(parts[1]), max(0.0, height - 2.6)


def extract(path: Path) -> dict:
    root = ET.parse(path).getroot()
    children = list(root)
    bar_group = children[2]
    pie_group = children[4]
    stats_group = children[5]

    weeks: dict[int, float] = defaultdict(float)
    for group in bar_group:
        if not str(group.tag).endswith("g"):
            continue
        x_pos, y_pos, weight = flat_point(group)
        along = (x_pos - BASE_X) / 20.0
        across = (y_pos - BASE_Y) / 11.545
        week = round((along + across) / 2.0)
        day = round((across - along) / 2.0)
        if not 0 <= day <= 6:
            raise SystemExit(f"contribution grid did not line up (day {day})")
        weeks[week] += weight

    if not weeks:
        raise SystemExit("no contribution bars found")

    ordered = [weeks[index] for index in range(min(weeks), max(weeks) + 1)]

    total = None
    period = None
    for node in stats_group.iter(NS + "text"):
        value = text_of(node)
        if value.isdigit() and total is None and int(value) > 100:
            total = int(value)
        if "/" in value and value[:4].isdigit():
            period = value
    if total is None or period is None:
        raise SystemExit("contribution total or date range missing")

    start_text, end_text = [part.strip() for part in period.split("/")]
    languages = []
    for node in pie_group.iter(NS + "title"):
        name, count = text_of(node).rsplit(" ", 1)
        languages.append((name, int(count)))
    if not languages:
        raise SystemExit("language breakdown missing")

    return {
        "weeks": ordered,
        "total": total,
        "start": date.fromisoformat(start_text),
        "end": date.fromisoformat(end_text),
        "languages": languages,
    }


def month_labels(start: date, count: int) -> list[tuple[int, str]]:
    labels = []
    previous = None
    for index in range(count):
        day = start + timedelta(days=7 * index)
        if previous != day.month:
            labels.append((index, day.strftime("%b")))
            previous = day.month
    return labels


def percents(languages: list[tuple[str, int]]) -> list[tuple[str, int]]:
    total = sum(count for _, count in languages)
    rounded = [int(round(count * 100 / total)) for _, count in languages]
    drift = 100 - sum(rounded)
    if languages:
        largest = max(range(len(languages)), key=lambda index: languages[index][1])
        rounded[largest] += drift
    return [(languages[index][0], rounded[index]) for index in range(len(languages))]


def render_card(data: dict) -> str:
    weeks = data["weeks"]
    labels = month_labels(data["start"], len(weeks))
    shares = percents(data["languages"])
    peak = max(weeks) or 1
    period = f'{data["start"].strftime("%b %Y")}  \u2014  {data["end"].strftime("%b %Y")}'
    number = f'{data["total"]:,}'
    contributions_x = 48 + len(number) * 36 + 28

    width = 1200
    height = 456
    left = 48
    right = 1152
    chart_top = 168
    chart_bottom = 312
    slot = (right - left) / len(weeks)
    bar_width = slot * 0.62
    font = "Segoe UI, Helvetica, Arial, sans-serif"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{data["total"]:,} contributions, {period}">',
        "<defs>",
        f'<linearGradient id="activity" x1="0" y1="{chart_top}" x2="0" y2="{chart_bottom}" gradientUnits="userSpaceOnUse">',
        '<stop offset="0%" stop-color="#9ecbff"/>',
        '<stop offset="100%" stop-color="#1f6feb"/>',
        "</linearGradient>",
        f'<clipPath id="lang"><rect x="{left}" y="396" width="{right - left}" height="8" rx="4"/></clipPath>',
        "</defs>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="18" fill="#161b22" stroke="#30363d"/>',
        '<rect x="48" y="40" width="36" height="3" rx="1.5" fill="#58a6ff"/>',
        f'<text x="48" y="72" fill="#58a6ff" font-family="{font}" font-size="13" letter-spacing="3.4">THE YEAR</text>',
        f'<text x="48" y="132" fill="#f0f6fc" font-family="{font}" font-size="56" font-weight="700">{number}</text>',
        f'<text x="{contributions_x}" y="132" fill="#8b949e" font-family="{font}" font-size="20">contributions</text>',
        f'<text x="1152" y="128" fill="#8b949e" font-family="{font}" font-size="16" text-anchor="end">{period}</text>',
    ]

    for fraction in (0.5, 1):
        y_pos = chart_bottom - (chart_bottom - chart_top) * fraction
        lines.append(
            f'<line x1="{left}" y1="{y_pos:.1f}" x2="{right}" y2="{y_pos:.1f}" stroke="#30363d" stroke-dasharray="3 7"/>'
        )
    lines.append(f'<line x1="{left}" y1="{chart_bottom}" x2="{right}" y2="{chart_bottom}" stroke="#30363d"/>')

    for index, value in enumerate(weeks):
        x_pos = left + index * slot + (slot - bar_width) / 2
        if value <= 0:
            bar_height = 2.0
            fill = "#30363d"
        else:
            bar_height = max(6.0, value / peak * (chart_bottom - chart_top))
            fill = "url(#activity)"
        y_pos = chart_bottom - bar_height
        lines.append(
            f'<rect x="{x_pos:.2f}" y="{y_pos:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" rx="3" fill="{fill}"/>'
        )

    for index, name in labels:
        x_pos = left + index * slot + slot / 2
        lines.append(
            f'<text x="{x_pos:.1f}" y="338" fill="#6e7681" font-family="{font}" font-size="12" text-anchor="middle">{name}</text>'
        )

    lines.append(
        f'<text x="48" y="378" fill="#8b949e" font-family="{font}" font-size="13" letter-spacing="2.4">LANGUAGES</text>'
    )

    cursor = float(left)
    span = float(right - left)
    lines.append('<g clip-path="url(#lang)">')
    for (_name, percent), color in zip(shares, LANG_COLORS):
        segment = span * percent / 100
        lines.append(f'<rect x="{cursor:.2f}" y="396" width="{segment + 0.5:.2f}" height="8" fill="{color}"/>')
        cursor += segment
    lines.append("</g>")

    cursor = float(left)
    legend_y = 432
    for (name, percent), color in zip(shares, LANG_COLORS):
        label = f"{name}  {percent}%"
        lines.append(f'<circle cx="{cursor + 4:.1f}" cy="{legend_y - 4}" r="4" fill="{color}"/>')
        lines.append(
            f'<text x="{cursor + 16:.1f}" y="{legend_y}" fill="#c9d1d9" font-family="{font}" font-size="14">{label}</text>'
        )
        cursor += 16 + len(label) * 7.6 + 28

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def main() -> None:
    data = extract(SOURCE)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_card(data), encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
