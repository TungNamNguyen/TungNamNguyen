#!/usr/bin/env python3
""" Fetches live GitHub contribution data for TungNamNguyen and renders icons/isocalendar.svg. """

import json
import math
import urllib.request
from datetime import datetime
from pathlib import Path

USERNAME = "TungNamNguyen"
OUT_PATH = Path(__file__).resolve().parent.parent / "icons" / "isocalendar.svg"


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    all_data = fetch_json(f"https://github-contributions-api.jogruber.de/v4/{USERNAME}")
    last_data = fetch_json(f"https://github-contributions-api.jogruber.de/v4/{USERNAME}?y=last")

    days_last = last_data["contributions"]
    counts_last = [d["count"] for d in days_last]
    max_day = max(counts_last) if counts_last else 1
    avg_day = sum(counts_last) / len(counts_last) if counts_last else 0

    all_days = sorted(all_data["contributions"], key=lambda x: x["date"])
    best_streak = 0
    cur = 0
    for d in all_days:
        if d["count"] > 0:
            cur += 1
            if cur > best_streak:
                best_streak = cur
        else:
            cur = 0

    cur_streak = 0
    for d in reversed(days_last):
        if d["count"] > 0:
            cur_streak += 1
        elif cur_streak > 0:
            break

    weeks = []
    current_week = []
    for d in days_last:
        dt = datetime.strptime(d["date"], "%Y-%m-%d")
        dow = (dt.weekday() + 1) % 7  # 0=Sun, 6=Sat
        if dow == 0 and current_week:
            weeks.append(current_week)
            current_week = []
        current_week.append((dow, d["count"], d["level"]))
    if current_week:
        weeks.append(current_week)

    colors = {
        0: ("#ebedf0", "#d5d8dc", "#c0c4c8"),
        1: ("#9be9a8", "#7bc98a", "#5fb06e"),
        2: ("#40c463", "#30a14e", "#23803b"),
        3: ("#30a14e", "#216e39", "#18542a"),
        4: ("#216e39", "#164b27", "#0f361b"),
    }

    dx = 6.2
    dy = 3.58
    origin_x = 84.0
    origin_y = 62.0
    max_bar_h = 34.0

    cubes_svg = []
    for w_idx, week in enumerate(weeks):
        for dow, count, level in week:
            cx = origin_x + (w_idx - dow) * dx
            cy = origin_y + (w_idx + dow) * dy
            if count == 0:
                h = 2.5
            else:
                ratio = math.pow(count / max_day, 0.65)
                h = 4.5 + ratio * (max_bar_h - 4.5)
            top_c, left_c, right_c = colors.get(level, colors[0])

            p_top = f"{cx:.2f},{cy - dy - h:.2f} {cx + dx:.2f},{cy - h:.2f} {cx:.2f},{cy + dy - h:.2f} {cx - dx:.2f},{cy - h:.2f}"
            p_left = f"{cx - dx:.2f},{cy - h:.2f} {cx:.2f},{cy + dy - h:.2f} {cx:.2f},{cy + dy:.2f} {cx - dx:.2f},{cy:.2f}"
            p_right = f"{cx:.2f},{cy + dy - h:.2f} {cx + dx:.2f},{cy - h:.2f} {cx + dx:.2f},{cy:.2f} {cx:.2f},{cy + dy:.2f}"

            cubes_svg.append(
                f'<g>'
                f'<polygon points="{p_left}" fill="{left_c}"/>'
                f'<polygon points="{p_right}" fill="{right_c}"/>'
                f'<polygon points="{p_top}" fill="{top_c}"/>'
                f'</g>'
            )

    cubes_str = "\n    ".join(cubes_svg)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="310" viewBox="0 0 480 310">
  <style>
    .title {{ font: 400 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: #0366d6; }}
    .sub {{ font: 400 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #0366d6; }}
    .stat {{ font: 400 11.5px 'Segoe UI', Ubuntu, Sans-Serif; fill: #666666; }}
  </style>

  <!-- Header: Contributions calendar -->
  <g transform="translate(18, 22)">
    <svg viewBox="0 0 16 16" width="16" height="16" fill="#777777">
      <path fill-rule="evenodd" d="M4.75 0a.75.75 0 01.75.75V2h5V.75a.75.75 0 011.5 0V2h1.25c.966 0 1.75.784 1.75 1.75v10.5A1.75 1.75 0 0113.25 16H2.75A1.75 1.75 0 011 14.25V3.75C1 2.784 1.784 2 2.75 2H4V.75A.75.75 0 014.75 0zm0 3.5h8.5a.25.25 0 01.25.25V6h-11V3.75a.25.25 0 01.25-.25h2zm-2.25 4v6.75c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25V7.5h-11z"/>
    </svg>
    <text x="26" y="13" class="title">Contributions calendar</text>
  </g>

  <!-- Right side stats: Commits streaks & Commits per day -->
  <g transform="translate(260, 56)">
    <!-- Commits streaks -->
    <g transform="translate(0, 0)">
      <svg viewBox="0 0 16 16" width="15" height="15" fill="#777777" y="1">
        <path fill-rule="evenodd" d="M2.5 1.75a.25.25 0 01.25-.25h8.5a.25.25 0 01.25.25v7.736a.75.75 0 101.5 0V1.75A1.75 1.75 0 0011.25 0h-8.5A1.75 1.75 0 001 1.75v11.5c0 .966.784 1.75 1.75 1.75h3.17a.75.75 0 000-1.5H2.75a.25.25 0 01-.25-.25V1.75zM4.75 4a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-4.5zM4 7.75A.75.75 0 014.75 7h2a.75.75 0 010 1.5h-2A.75.75 0 014 7.75zm11.774 3.537a.75.75 0 00-1.048-1.074L10.7 14.145 9.281 12.72a.75.75 0 00-1.062 1.058l1.943 1.95a.75.75 0 001.055.008l4.557-4.45z"/>
      </svg>
      <text x="23" y="12.5" class="sub">Commits streaks</text>

      <!-- Current streak -->
      <g transform="translate(0, 20)">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="#777777" y="1">
          <path fill-rule="evenodd" d="M7.998 14.5c2.832 0 5-1.98 5-4.5 0-1.463-.68-2.19-1.879-3.383l-.036-.037c-1.013-1.008-2.3-2.29-2.834-4.434-.322.256-.63.579-.864.953-.432.696-.621 1.58-.046 2.73.473.947.67 2.284-.278 3.232-.61.61-1.548.84-2.403.522a2.71 2.71 0 01-1.036-.724c-.159.442-.222.912-.222 1.401 0 2.52 2.168 4.24 4.598 4.24z"/>
        </svg>
        <text x="23" y="12" class="stat">Current streak {cur_streak} day{"s" if cur_streak != 1 else ""}</text>
      </g>

      <!-- Best streak -->
      <g transform="translate(0, 38)">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="#777777" y="1">
          <path fill-rule="evenodd" d="M8 .25a.75.75 0 01.75.75v3.19l2.255-2.255a.75.75 0 011.06 1.06L9.81 5.25H13a.75.75 0 010 1.5H9.81l2.255 2.255a.75.75 0 01-1.06 1.06L8.75 7.81V11a.75.75 0 01-1.5 0V7.81L4.995 10.065a.75.75 0 01-1.06-1.06L6.19 6.75H3a.75.75 0 010-1.5h3.19L3.935 2.995a.75.75 0 011.06-1.06L7.25 4.19V1A.75.75 0 018 .25z"/>
        </svg>
        <text x="23" y="12" class="stat">Best streak {best_streak} days</text>
      </g>
    </g>

    <!-- Commits per day -->
    <g transform="translate(0, 68)">
      <svg viewBox="0 0 16 16" width="15" height="15" fill="#777777" y="1">
        <path fill-rule="evenodd" d="M10.5 5a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0zm.061 3.073a4 4 0 10-5.123 0 6.004 6.004 0 00-3.431 5.142.75.75 0 001.498.07 4.5 4.5 0 018.99 0 .75.75 0 101.498-.07 6.005 6.005 0 00-3.432-5.142z"/>
      </svg>
      <text x="23" y="12.5" class="sub">Commits per day</text>

      <!-- Highest in a day -->
      <g transform="translate(0, 20)">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="#777777" y="1">
          <path fill-rule="evenodd" d="M8 2.5a.75.75 0 01.53.22l3.75 3.75a.75.75 0 01-1.06 1.06L8.75 5.06v6.69a.75.75 0 01-1.5 0V5.06L4.78 7.53a.75.75 0 01-1.06-1.06l3.75-3.75A.75.75 0 018 2.5zM2.75 13.5a.75.75 0 000 1.5h10.5a.75.75 0 000-1.5H2.75z"/>
        </svg>
        <text x="23" y="12" class="stat">Highest in a day at {max_day}</text>
      </g>

      <!-- Average per day -->
      <g transform="translate(0, 38)">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="#777777" y="1">
          <path fill-rule="evenodd" d="M8 1a.75.75 0 01.75.75v3.69l1.22-1.22a.75.75 0 111.06 1.06l-2.5 2.5a.75.75 0 01-1.06 0l-2.5-2.5a.75.75 0 011.06-1.06l1.22 1.22V1.75A.75.75 0 018 1zm0 14a.75.75 0 01-.75-.75v-3.69l-1.22 1.22a.75.75 0 01-1.06-1.06l2.5-2.5a.75.75 0 011.06 0l2.5 2.5a.75.75 0 11-1.06 1.06l-1.22-1.22v3.69A.75.75 0 018 15z"/>
        </svg>
        <text x="23" y="12" class="stat">Average per day at ~{avg_day:.2f}</text>
      </g>
    </g>
  </g>

  <!-- 3D Isometric Contributions Calendar -->
  <g transform="translate(10, 18)">
    {cubes_str}
  </g>
</svg>'''

    OUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Updated {OUT_PATH}")


if __name__ == "__main__":
    main()

