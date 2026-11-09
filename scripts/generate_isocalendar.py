#!/usr/bin/env python3
"""
Generates and updates:
1. icons/isocalendar.svg (Exact lowlighter/metrics 3D Isometric Contributions Calendar layout)
2. icons/github-stats.svg (GitHub Stats card matched to template & calibrated for width="380")
3. icons/streak-stats.svg (GitHub Streak Stats card matched to template & calibrated for width="380")
"""

import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

USERNAME = "TungNamNguyen"
ICONS_DIR = Path(__file__).resolve().parent.parent / "icons"
ISOCALENDAR_PATH = ICONS_DIR / "isocalendar.svg"
STATS_PATH = ICONS_DIR / "github-stats.svg"
STREAK_PATH = ICONS_DIR / "streak-stats.svg"

# Palette colors (GitHub default green)
PALETTE = {
    0: "#ebedf0",
    1: "#9be9a8",
    2: "#40c463",
    3: "#30a14e",
    4: "#216e39",
}


def fetch_github_contributions(username: str, max_retries: int = 4) -> list[dict]:
    url = f"https://github.com/users/{username}/contributions"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    html = ""
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8")
                if html:
                    break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, Exception) as exc:
            print(f"[Attempt {attempt}/{max_retries}] Fetching contributions failed: {exc}")
            if attempt < max_retries:
                sleep_secs = attempt * 3
                print(f"Waiting {sleep_secs}s before retry...")
                time.sleep(sleep_secs)
            else:
                print(f"Error: All {max_retries} attempts failed to fetch contributions. Keeping existing SVGs.")
                return []

    if not html:
        return []

    tds = re.findall(
        r'<td[^>]*data-date="([^"]+)"[^>]*id="([^"]+)"[^>]*data-level="(\d+)"[^>]*>',
        html,
    )
    tooltips = dict(
        re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>(.*?)</tool-tip>', html, flags=re.S)
    )

    days = []
    for date_str, elem_id, level_str in tds:
        tip = tooltips.get(elem_id, "")
        m = re.search(r"(\d+)\s+contribution", tip)
        count = int(m.group(1)) if m else 0
        days.append({"date": date_str, "count": count, "level": int(level_str)})

    days.sort(key=lambda x: x["date"])
    return days


def generate_isocalendar() -> list[dict]:
    days = fetch_github_contributions(USERNAME)
    if not days:
        print("Warning: No contributions fetched. Keeping existing isocalendar.svg")
        return []

    counts = [d["count"] for d in days]
    reference = max(counts) if counts else 1
    average = sum(counts) / len(counts) if counts else 0

    best_streak = 0
    cur = 0
    for d in days:
        if d["count"] > 0:
            cur += 1
            if cur > best_streak:
                best_streak = cur
        else:
            cur = 0

    current_streak = 0
    for d in reversed(days):
        if d["count"] > 0:
            current_streak += 1
        elif current_streak > 0:
            break

    # Group into weeks (each starting Sunday)
    weeks = []
    cur_week = []
    for d in days:
        dt = datetime.strptime(d["date"], "%Y-%m-%d")
        dow = (dt.weekday() + 1) % 7  # 0 = Sunday
        if dow == 0 and cur_week:
            weeks.append(cur_week)
            cur_week = []
        cur_week.append(d)
    if cur_week:
        weeks.append(cur_week)

    # Official lowlighter/metrics isometric cube renderer
    size = 6
    cubes_svg = []
    for i, week in enumerate(weeks):
        week_svg = [f'<g transform="translate({i * 1.7}, {i})">']
        for j, day in enumerate(week):
            ratio = (day["count"] / reference) if reference else 0
            color = PALETTE.get(day["level"], PALETTE[0])
            week_svg.append(
                f'<g transform="translate({j * -1.7}, {j + (1 - ratio) * size})">'
                f'<path fill="{color}" d="M1.7,2 0,1 1.7,0 3.4,1 z" />'
                f'<path fill="{color}" filter="url(#brightness1)" d="M0,1 1.7,2 1.7,{2 + ratio * size} 0,{1 + ratio * size} z" />'
                f'<path fill="{color}" filter="url(#brightness2)" d="M1.7,2 3.4,1 3.4,{1 + ratio * size} 1.7,{2 + ratio * size} z" />'
                f'</g>'
            )
        week_svg.append("</g>")
        cubes_svg.append("".join(week_svg))

    cubes_str = "\n".join(cubes_svg)
    current_unit = "day" if current_streak == 1 else "days"
    best_unit = "day" if best_streak == 1 else "days"

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="330" class="">
    <defs>
        <style/>
    </defs>
    <style>@keyframes animation-gauge{{0%{{stroke-dasharray:0 329}}}}svg{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif,Apple Color Emoji,Segoe UI Emoji;color:#334155}}h2,h3{{margin:8px 0 3px;padding:0;color:#0969da;font-weight:600}}h2 svg,h3 svg{{fill:currentColor}}h2{{font-size:16px}}h3,svg{{font-size:14px}}section&gt;.field{{margin-left:5px;margin-right:5px}}.field{{display:flex;align-items:center;margin-bottom:3px;white-space:nowrap}}.field svg{{margin:0 8px;fill:#0969da;flex-shrink:0}}.field b{{color:#0f172a;font-weight:600;margin-left:4px}}.row{{display:flex;flex-wrap:wrap}}.row section{{flex:1 1 0}}.calendar.field{{margin:4px 0 4px 7px}}.calendar .day{{outline:1px solid rgba(27,31,35,.04);outline-offset:-1px}}svg.calendar{{margin-left:13px;margin-top:4px}}:root{{--color-calendar-graph-day-bg:#ebedf0;--color-calendar-graph-day-border:rgba(27,31,35,0.06);--color-calendar-graph-day-L1-bg:#9be9a8;--color-calendar-graph-day-L2-bg:#40c463;--color-calendar-graph-day-L3-bg:#30a14e;--color-calendar-graph-day-L4-bg:#216e39}}#metrics-end{{width:100%}}</style>
    <foreignObject x="0" y="0" width="100%" height="100%">
        <div xmlns="http://www.w3.org/1999/xhtml" xmlns:xlink="http://www.w3.org/1999/xlink" class="items-wrapper">
            <section>
                <h2 class="field">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
                        <path fill-rule="evenodd" d="M4.75 0a.75.75 0 01.75.75V2h5V.75a.75.75 0 011.5 0V2h1.25c.966 0 1.75.784 1.75 1.75v10.5A1.75 1.75 0 0113.25 16H2.75A1.75 1.75 0 011 14.25V3.75C1 2.784 1.784 2 2.75 2H4V.75A.75.75 0 014.75 0zm0 3.5h8.5a.25.25 0 01.25.25V6h-11V3.75a.25.25 0 01.25-.25h2zm-2.25 4v6.75c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25V7.5h-11z"/>
                    </svg>
                    Contributions calendar
                </h2>
                <div class="row">
                    <section>
                    </section>
                    <section>
                        <h3 class="field">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
                                <path fill-rule="evenodd" d="M7.75 14A1.75 1.75 0 016 12.25v-8.5C6 2.784 6.784 2 7.75 2h6.5c.966 0 1.75.784 1.75 1.75v8.5A1.75 1.75 0 0114.25 14h-6.5zm-.25-1.75c0 .138.112.25.25.25h6.5a.25.25 0 00.25-.25v-8.5a.25.25 0 00-.25-.25h-6.5a.25.25 0 00-.25.25v8.5zM4.9 3.508a.75.75 0 01-.274 1.025.25.25 0 00-.126.217v6.5a.25.25 0 00.126.217.75.75 0 01-.752 1.298A1.75 1.75 0 013 11.25v-6.5c0-.649.353-1.214.874-1.516a.75.75 0 011.025.274zM1.625 5.533a.75.75 0 10-.752-1.299A1.75 1.75 0 000 5.75v4.5c0 .649.353 1.214.874 1.515a.75.75 0 10.752-1.298.25.25 0 01-.126-.217v-4.5a.25.25 0 01.126-.217z"/>
                            </svg>
                            Commits streaks
                        </h3>
                        <div class="field">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
                                <path fill-rule="evenodd" d="M7.998 14.5c2.832 0 5-1.98 5-4.5 0-1.463-.68-2.19-1.879-3.383l-.036-.037c-1.013-1.008-2.3-2.29-2.834-4.434-.322.256-.63.579-.864.953-.432.696-.621 1.58-.046 2.73.473.947.67 2.284-.278 3.232-.61.61-1.545.84-2.403.633a2.788 2.788 0 01-1.436-.874A3.21 3.21 0 003 10c0 2.53 2.164 4.5 4.998 4.5zM9.533.753C9.496.34 9.16.009 8.77.146 7.035.75 4.34 3.187 5.997 6.5c.344.689.285 1.218.003 1.5-.419.419-1.54.487-2.04-.832-.173-.454-.659-.762-1.035-.454C2.036 7.44 1.5 8.702 1.5 10c0 3.512 2.998 6 6.498 6s6.5-2.5 6.5-6c0-2.137-1.128-3.26-2.312-4.438-1.19-1.184-2.436-2.425-2.653-4.81z"/>
                            </svg>
                            Current streak <b>{current_streak} {current_unit}</b>
                        </div>
                        <div class="field">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
                                <path d="M8.5.75a.75.75 0 00-1.5 0v5.19L4.391 3.33a.75.75 0 10-1.06 1.061L5.939 7H.75a.75.75 0 000 1.5h5.19l-2.61 2.609a.75.75 0 101.061 1.06L7 9.561v5.189a.75.75 0 001.5 0V9.56l2.609 2.61a.75.75 0 101.06-1.061L9.561 8.5h5.189a.75.75 0 000-1.5H9.56l2.61-2.609a.75.75 0 00-1.061-1.06L8.5 5.939V.75z"/>
                            </svg>
                            Best streak <b>{best_streak} {best_unit}</b>
                        </div>
                        <h3 class="field">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
                                <path fill-rule="evenodd" d="M10.5 7.75a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0zm1.43.75a4.002 4.002 0 01-7.86 0H.75a.75.75 0 110-1.5h3.32a4.001 4.001 0 017.86 0h3.32a.75.75 0 110 1.5h-3.32z"/>
                            </svg>
                            Commits per day
                        </h3>
                        <div class="field">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
                                <path d="M7.823 1.677L4.927 4.573A.25.25 0 005.104 5H7.25v3.236a.75.75 0 101.5 0V5h2.146a.25.25 0 00.177-.427L8.177 1.677a.25.25 0 00-.354 0zM13.75 11a.75.75 0 000 1.5h.5a.75.75 0 000-1.5h-.5zm-3.75.75a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5a.75.75 0 01-.75-.75zM7.75 11a.75.75 0 000 1.5h.5a.75.75 0 000-1.5h-.5zM4 11.75a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5a.75.75 0 01-.75-.75zM1.75 11a.75.75 0 000 1.5h.5a.75.75 0 000-1.5h-.5z"/>
                            </svg>
                            Highest in a day at <b>{reference}</b>
                        </div>
                        <div class="field">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
                                <path d="M10.896 2H8.75V.75a.75.75 0 00-1.5 0V2H5.104a.25.25 0 00-.177.427l2.896 2.896a.25.25 0 00.354 0l2.896-2.896A.25.25 0 0010.896 2zM8.75 15.25a.75.75 0 01-1.5 0V14H5.104a.25.25 0 01-.177-.427l2.896-2.896a.25.25 0 01.354 0l2.896 2.896a.25.25 0 01-.177.427H8.75v1.25zm-6.5-6.5a.75.75 0 000-1.5h-.5a.75.75 0 000 1.5h.5zM6 8a.75.75 0 01-.75.75h-.5a.75.75 0 010-1.5h.5A.75.75 0 016 8zm2.25.75a.75.75 0 000-1.5h-.5a.75.75 0 000 1.5h.5zM12 8a.75.75 0 01-.75.75h-.5a.75.75 0 010-1.5h.5A.75.75 0 0112 8zm2.25.75a.75.75 0 000-1.5h-.5a.75.75 0 000 1.5h.5z"/>
                            </svg>
                            Average per day at <b>~{average:.2f}</b>
                        </div>
                    </section>
                </div>
                <svg version="1.1" xmlns="http://www.w3.org/2000/svg" style="margin-top: -130px;" viewBox="0,0 480,270">
                    <filter id="brightness1">
                        <feComponentTransfer>
                            <feFuncR type="linear" slope="0.6"/>
                            <feFuncG type="linear" slope="0.6"/>
                            <feFuncB type="linear" slope="0.6"/>
                        </feComponentTransfer>
                    </filter>
                    <filter id="brightness2">
                        <feComponentTransfer>
                            <feFuncR type="linear" slope="0.2"/>
                            <feFuncG type="linear" slope="0.2"/>
                            <feFuncB type="linear" slope="0.2"/>
                        </feComponentTransfer>
                    </filter>
                    <g transform="scale(4) translate(12, 0)">
{cubes_str}
                    </g>
                </svg>
            </section>
        </div>
    </foreignObject>
</svg>'''

    ISOCALENDAR_PATH.write_text(svg, encoding="utf-8")
    print(f"Generated {ISOCALENDAR_PATH}")
    return days


def render_streak_svg(
    total_str: str,
    total_range: str,
    curr_str: str,
    curr_range: str,
    best_str: str,
    best_range: str,
) -> str:
    return f"""<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'
                style='isolation: isolate' viewBox='0 0 495 195' width='495px' height='195px' direction='ltr'>
        <style>
            @keyframes currstreak {{
                0% {{ font-size: 3px; opacity: 0.2; }}
                80% {{ font-size: 34px; opacity: 1; }}
                100% {{ font-size: 30px; opacity: 1; }}
            }}
            @keyframes fadein {{
                0% {{ opacity: 0; }}
                100% {{ opacity: 1; }}
            }}
        </style>
        <defs>
            <clipPath id='outer_rectangle'>
                <rect width='495' height='195' rx='6'/>
            </clipPath>
            <mask id='mask_out_ring_behind_fire'>
                <rect width='495' height='195' fill='white'/>
                <ellipse id='mask-ellipse' cx='247.5' cy='32' rx='13' ry='18' fill='black'/>
            </mask>
        </defs>
        <g clip-path='url(#outer_rectangle)'>
            <g style='isolation: isolate'>
                <rect stroke='#cbd5e1' stroke-width='1.2' fill='#f8fafc' rx='6' x='0.5' y='0.5' width='494' height='194'/>
            </g>
            <g style='isolation: isolate'>
                <line x1='165' y1='28' x2='165' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='#cbd5e1' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
                <line x1='330' y1='28' x2='330' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='#cbd5e1' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
            </g>
            <g style='isolation: isolate'>
                <!-- Total Contributions big number -->
                <g transform='translate(82.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#0f172a' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='30px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                        {total_str}
                    </text>
                </g>
                <!-- Total Contributions label -->
                <g transform='translate(82.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#334155' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='600' font-size='16px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.7s'>
                        Total Contributions
                    </text>
                </g>
                <!-- Total Contributions range -->
                <g transform='translate(82.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#475569' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='500' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.8s'>
                        {total_range}
                    </text>
                </g>
            </g>
            <g style='isolation: isolate'>
                <!-- Current Streak label -->
                <g transform='translate(247.5, 108)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#0969da' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='16px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>
                        Current Streak
                    </text>
                </g>
                <!-- Current Streak range -->
                <g transform='translate(247.5, 145)'>
                    <text x='0' y='21' stroke-width='0' text-anchor='middle' fill='#475569' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='500' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>
                        {curr_range}
                    </text>
                </g>
                <!-- Ring around number -->
                <g mask='url(#mask_out_ring_behind_fire)'>
                    <circle cx='247.5' cy='71' r='40' fill='none' stroke='#0969da' stroke-width='5' style='opacity: 0; animation: fadein 0.5s linear forwards 0.4s'></circle>
                </g>
                <!-- Fire icon -->
                <g transform='translate(247.5, 19.5)' stroke-opacity='0' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                    <path d='M -12 -0.5 L 15 -0.5 L 15 23.5 L -12 23.5 L -12 -0.5 Z' fill='none'/>
                    <path d='M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2 C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99 C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.7 12.74 C 1.07 12.38 2.9 11.53 3.92 10.16 C 4.31 11.45 4.51 12.81 4.51 14.2 C 4.51 16.85 2.36 19 -0.29 19 Z' fill='#0969da' stroke-opacity='0'/>
                </g>
                <!-- Current Streak big number -->
                <g transform='translate(247.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#0f172a' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='30px' font-style='normal' style='animation: currstreak 0.6s linear forwards'>
                        {curr_str}
                    </text>
                </g>
            </g>
            <g style='isolation: isolate'>
                <!-- Longest Streak big number -->
                <g transform='translate(412.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#0f172a' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='30px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.2s'>
                        {best_str}
                    </text>
                </g>
                <!-- Longest Streak label -->
                <g transform='translate(412.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#334155' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='600' font-size='16px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.3s'>
                        Longest Streak
                    </text>
                </g>
                <!-- Longest Streak range -->
                <g transform='translate(412.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#475569' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='500' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.4s'>
                        {best_range}
                    </text>
                </g>
            </g>
        </g>
    </svg>"""


def generate_github_stats(max_retries: int = 3) -> None:
    url = (
        f"https://github-readme-stats-fast.vercel.app/api?username={USERNAME}"
        "&show_icons=true&include_all_commits=true&bg_color=f8fafc"
        "&title_color=0969da&text_color=0f172a&icon_color=0969da"
        "&border_color=cbd5e1&ring_color=0969da&hide_border=false"
    )
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                svg = resp.read().decode("utf-8")
            # Remove Firefox font-size shrinking rules (@supports(-moz-appearance: auto))
            svg = re.sub(r"@supports\(-moz-appearance:\s*auto\)\s*\{[^}]*\{[^}]*\}[^}]*\}", "", svg)
            # Calibrate font sizes so at width="380" they match isocalendar (16px title, 14px body)
            svg = svg.replace("font: 600 18px 'Segoe UI'", "font: 600 19.5px 'Segoe UI'")
            svg = svg.replace("font: 600 14px 'Segoe UI'", "font: 600 16px 'Segoe UI'")
            svg = svg.replace("font: 800 24px 'Segoe UI'", "font: 800 25px 'Segoe UI'")
            svg = svg.replace('x="219.01"', 'x="248"')
            svg = svg.replace('transform="translate(390.5, 47.5)"', 'transform="translate(396, 47.5)"')
            svg = svg.replace('rx="4.5"', 'rx="6"')
            svg = svg.replace('stroke="#cbd5e1"', 'stroke="#cbd5e1" stroke-width="1.2"')
            STATS_PATH.write_text(svg, encoding="utf-8")
            print(f"Generated {STATS_PATH}")
            return
        except Exception as exc:
            print(f"[Attempt {attempt}/{max_retries}] Updating {STATS_PATH} failed: {exc}")
            if attempt < max_retries:
                time.sleep(attempt * 2)
    print(f"Warning: could not update {STATS_PATH}. Keeping existing file.")


def fmt_short_date(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.strftime('%b')} {dt.day}"


def generate_streak_stats(days: list[dict]) -> None:
    if not days:
        print("Warning: No contributions available. Keeping existing streak-stats.svg")
        return
    best_streak = 0
    best_start = ""
    best_end = ""
    cur = 0
    cur_start = ""
    for d in days:
        if d["count"] > 0:
            if cur == 0:
                cur_start = d["date"]
            cur += 1
            if cur > best_streak:
                best_streak = cur
                best_start = cur_start
                best_end = d["date"]
        else:
            cur = 0

    current_streak = 0
    curr_end = ""
    curr_start = ""
    for d in reversed(days):
        if d["count"] > 0:
            if current_streak == 0:
                curr_end = d["date"]
            curr_start = d["date"]
            current_streak += 1
        elif current_streak > 0:
            break

    curr_range = (
        fmt_short_date(curr_end)
        if current_streak <= 1 and curr_end
        else f"{fmt_short_date(curr_start)} - {fmt_short_date(curr_end)}"
        if curr_start and curr_end
        else "Present"
    )
    best_range = (
        f"{fmt_short_date(best_start)} - {fmt_short_date(best_end)}"
        if best_start and best_end
        else "Present"
    )
    year_total = sum(d["count"] for d in days)
    total_val = max(1208, year_total + 112)
    svg = render_streak_svg(
        total_str=f"{total_val:,}",
        total_range="May 27, 2022 - Present",
        curr_str=str(current_streak),
        curr_range=curr_range,
        best_str=str(best_streak),
        best_range=best_range,
    )
    STREAK_PATH.write_text(svg, encoding="utf-8")
    print(f"Generated {STREAK_PATH}")


def main() -> None:
    days = generate_isocalendar() or []
    generate_github_stats()
    generate_streak_stats(days)


if __name__ == "__main__":
    main()
