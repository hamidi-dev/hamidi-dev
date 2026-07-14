#!/usr/bin/env python3
"""Render the profile stat cards straight from the GitHub API.

Deliberately not using github-readme-stats.vercel.app: the shared instance
answers 503 under load, which turns the profile into two broken images.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

LOGIN = "hamidi-dev"
OUT = Path(__file__).parent

# Readable on both the light and the dark GitHub theme.
ACCENT = "#58a6ff"
TEXT = "#768390"
TITLE_SIZE = 16

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch():
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"login={LOGIN}"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)["data"]["user"]


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def legible(hex_color):
    """Lift very dark linguist colors so they stay visible on a dark theme.

    Lua ships as #000080, which is all but invisible against GitHub's dark
    background — and the card has no opaque backdrop to save it.
    """
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return ACCENT
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    floor = 96
    if luma >= floor:
        return f"#{h}"
    # Blend toward white. Scaling the channels instead would just saturate the
    # hue (navy -> pure blue) without ever getting bright enough to read.
    t = (floor - luma) / (255 - luma)
    r, g, b = (round(c + (255 - c) * t) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def card(width, height, title, body):
    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .title {{ font: 600 {TITLE_SIZE}px system-ui, -apple-system, 'Segoe UI', sans-serif; fill: {ACCENT}; }}
    .stat  {{ font: 400 13px system-ui, -apple-system, 'Segoe UI', sans-serif; fill: {TEXT}; }}
    .val   {{ font: 600 13px system-ui, -apple-system, 'Segoe UI', sans-serif; fill: {ACCENT}; }}
  </style>
  <text x="0" y="20" class="title">{esc(title)}</text>
{body}
</svg>
"""


def stats_card(user):
    repos = user["repositories"]["nodes"]
    stars = sum(r["stargazerCount"] for r in repos)
    c = user["contributionsCollection"]
    rows = [
        ("Total stars earned", stars),
        ("Public repositories", user["repositories"]["totalCount"]),
        ("Commits (past year)", c["totalCommitContributions"]),
        ("Pull requests (past year)", c["totalPullRequestContributions"]),
    ]
    body = "\n".join(
        f'  <text x="0" y="{52 + i * 24}" class="stat">{esc(label)}</text>'
        f'<text x="260" y="{52 + i * 24}" class="val">{value}</text>'
        for i, (label, value) in enumerate(rows)
    )
    return card(320, 52 + len(rows) * 24, "Mo's GitHub stats", body)


def langs_card(user, top=6):
    sizes = {}
    colors = {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = legible(edge["node"]["color"] or ACCENT)

    ranked = sorted(sizes.items(), key=lambda kv: -kv[1])[:top]
    total = sum(size for _, size in ranked) or 1

    bar_w, bar_x, bar_y = 300, 0, 34
    parts, legend, offset = [], [], 0.0
    for name, size in ranked:
        share = size / total
        w = share * bar_w
        parts.append(
            f'  <rect x="{bar_x + offset:.1f}" y="{bar_y}" width="{w:.1f}" '
            f'height="8" rx="2" fill="{colors[name]}"/>'
        )
        offset += w

    for i, (name, size) in enumerate(ranked):
        col, row = i % 2, i // 2
        x, y = col * 155, 68 + row * 22
        legend.append(
            f'  <circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{colors[name]}"/>'
            f'<text x="{x + 16}" y="{y}" class="stat">{esc(name)} '
            f'{size / total * 100:.1f}%</text>'
        )

    rows = (len(ranked) + 1) // 2
    body = "\n".join(parts + legend)
    return card(320, 68 + rows * 22 + 6, "Most used languages", body)


def main():
    user = fetch()
    (OUT / "stats.svg").write_text(stats_card(user))
    (OUT / "top-langs.svg").write_text(langs_card(user))
    print("wrote stats.svg and top-langs.svg", file=sys.stderr)


if __name__ == "__main__":
    main()
