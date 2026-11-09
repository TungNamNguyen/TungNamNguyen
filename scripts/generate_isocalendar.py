#!/usr/bin/env python3
"""
Production-grade generator for GitHub Profile SVG assets:
1. icons/isocalendar.svg  (3D Isometric Contributions Calendar - 52-week rolling window)
2. icons/github-stats.svg (GitHub Stats Card - native renderer, zero 3rd-party Vercel dependency)
3. icons/streak-stats.svg (GitHub Streak Stats Card - exact all-time multi-year history since 2022)

Architecture:
- Primary Data Engine: Official GitHub GraphQL API v4 + REST Search API (via GITHUB_TOKEN / GH_TOKEN).
- Fallback Data Engine: Multi-year GitHub HTML contributions + public REST API v3 (for local tokenless runs).
- Resilience: Exponential backoff retries, strict XML validation (ElementTree), and atomic POSIX file writes.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USERNAME = "TungNamNguyen"
DISPLAY_NAME = "Nam Tung Nguyen"
ACCOUNT_START_YEAR = 2022
ACCOUNT_START_DATE = "2022-05-27"
ACCOUNT_START_LABEL = "May 27, 2022"

ICONS_DIR = Path(__file__).resolve().parent.parent / "icons"
ISOCALENDAR_PATH = ICONS_DIR / "isocalendar.svg"
STATS_PATH = ICONS_DIR / "github-stats.svg"
STREAK_PATH = ICONS_DIR / "streak-stats.svg"

# GitHub default green contribution palette
PALETTE = {
    0: "#ebedf0",
    1: "#9be9a8",
    2: "#40c463",
    3: "#30a14e",
    4: "#216e39",
}

GRAPHQL_LEVEL_MAP = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


def get_github_token() -> str:
    """Return GitHub API token from environment if available."""
    return (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()


def http_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 30,
    max_retries: int = 4,
) -> tuple[str, dict[str, str]]:
    """Execute an HTTP request with exponential backoff retries."""
    req_headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    if headers:
        req_headers.update(headers)

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                return body, resp_headers
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"[HTTP Attempt {attempt}/{max_retries}] {method} {url} failed: {exc}")
            if attempt < max_retries:
                sleep_secs = attempt * 3
                time.sleep(sleep_secs)
            else:
                raise
    return "", {}


def atomic_write_svg(path: Path, svg_content: str) -> bool:
    """Validate XML/SVG syntax and write atomically via a temporary file."""
    content = svg_content.strip()
    if not content.startswith("<svg") or not content.endswith("</svg>"):
        print(f"Error: Invalid SVG boundary for {path.name}. Keeping existing file.")
        return False
    try:
        ET.fromstring(content)
    except ET.ParseError as exc:
        print(f"Error: XML validation failed for {path.name}: {exc}. Keeping existing file.")
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".svg.tmp")
    try:
        tmp_path.write_text(content + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
        print(f"Validated & wrote {path}")
        return True
    except Exception as exc:
        print(f"Error writing {path}: {exc}")
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False


def fetch_total_commits_search(username: str, token: str = "") -> int | None:
    """Fetch all-time commits authored by username via GitHub REST Search API."""
    url = f"https://api.github.com/search/commits?q=author:{username}"
    headers = {"Accept": "application/vnd.github.cloak-preview+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        body, _ = http_request(url, headers=headers, timeout=20, max_retries=3)
        payload = json.loads(body)
        total = payload.get("total_count")
        if isinstance(total, int) and total >= 0:
            return total
    except Exception as exc:
        print(f"Warning: commit search API fallback triggered: {exc}")
    return None


def fetch_via_graphql(username: str, token: str) -> dict[str, Any] | None:
    """
    Primary Production Engine:
    Fetch rolling contributions, multi-year history (2022..present), and user stats
    in a single official GitHub GraphQL API v4 call.
    """
    current_year = max(datetime.now(timezone.utc).year, ACCOUNT_START_YEAR)
    years = list(range(ACCOUNT_START_YEAR, current_year + 1))

    year_queries = []
    for y in years:
        year_queries.append(
            f"""
            y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") {{
              totalCommitContributions
              restrictedContributionsCount
              contributionCalendar {{
                totalContributions
                weeks {{
                  contributionDays {{
                    date
                    contributionCount
                    contributionLevel
                  }}
                }}
              }}
            }}
            """
        )

    query = f"""
    query($login: String!) {{
      user(login: $login) {{
        name
        createdAt
        followers {{ totalCount }}
        pullRequests(states: [OPEN, CLOSED, MERGED]) {{ totalCount }}
        openIssues: issues(states: OPEN) {{ totalCount }}
        closedIssues: issues(states: CLOSED) {{ totalCount }}
        repositoriesContributedTo(
          first: 1,
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
        ) {{ totalCount }}
        repositories(
          first: 100,
          ownerAffiliations: OWNER,
          isFork: false,
          orderBy: {{direction: DESC, field: STARGAZERS}}
        ) {{
          nodes {{
            stargazers {{ totalCount }}
          }}
        }}
        rolling: contributionsCollection {{
          totalCommitContributions
          totalPullRequestReviewContributions
          restrictedContributionsCount
          contributionCalendar {{
            totalContributions
            weeks {{
              contributionDays {{
                date
                contributionCount
                contributionLevel
              }}
            }}
          }}
        }}
        {"".join(year_queries)}
      }}
    }}
    """

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v4+json",
    }
    payload = json.dumps({"query": query, "variables": {"login": username}}).encode("utf-8")

    try:
        body, _ = http_request(
            "https://api.github.com/graphql",
            method="POST",
            headers=headers,
            data=payload,
            timeout=30,
            max_retries=4,
        )
        resp_json = json.loads(body)
        if "errors" in resp_json or not resp_json.get("data", {}).get("user"):
            print(f"GraphQL returned errors: {resp_json.get('errors')}")
            return None

        user = resp_json["data"]["user"]

        # Parse rolling 1-year window
        rolling_days: list[dict[str, Any]] = []
        for week in user["rolling"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                rolling_days.append(
                    {
                        "date": day["date"],
                        "count": int(day["contributionCount"]),
                        "level": GRAPHQL_LEVEL_MAP.get(day["contributionLevel"], 0),
                    }
                )
        rolling_days.sort(key=lambda x: x["date"])
        max_date = rolling_days[-1]["date"] if rolling_days else datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Parse all-time multi-year history
        all_days_map: dict[str, dict[str, Any]] = {}
        graphql_commits_sum = 0
        for y in years:
            y_col = user.get(f"y{y}")
            if not y_col:
                continue
            graphql_commits_sum += int(y_col.get("totalCommitContributions", 0)) + int(
                y_col.get("restrictedContributionsCount", 0)
            )
            for week in y_col["contributionCalendar"]["weeks"]:
                for day in week["contributionDays"]:
                    d_str = day["date"]
                    if ACCOUNT_START_DATE <= d_str <= max_date:
                        all_days_map[d_str] = {
                            "date": d_str,
                            "count": int(day["contributionCount"]),
                            "level": GRAPHQL_LEVEL_MAP.get(day["contributionLevel"], 0),
                        }

        all_days = [all_days_map[k] for k in sorted(all_days_map)]
        stars = sum(
            int(node["stargazers"]["totalCount"])
            for node in (user.get("repositories", {}).get("nodes") or [])
        )
        prs = int(user.get("pullRequests", {}).get("totalCount", 0))
        issues = int(user.get("openIssues", {}).get("totalCount", 0)) + int(
            user.get("closedIssues", {}).get("totalCount", 0)
        )
        followers = int(user.get("followers", {}).get("totalCount", 0))
        contributed_to = int(user.get("repositoriesContributedTo", {}).get("totalCount", 0))
        reviews = int(user["rolling"].get("totalPullRequestReviewContributions", 0))

        search_commits = fetch_total_commits_search(username, token=token)
        total_commits = search_commits if search_commits is not None else max(
            graphql_commits_sum, sum(d["count"] for d in all_days)
        )

        print("Successfully fetched all data via official GitHub GraphQL API.")
        return {
            "rolling_days": rolling_days,
            "all_days": all_days,
            "stats": {
                "stars": stars,
                "commits": total_commits,
                "prs": prs,
                "issues": issues,
                "reviews": reviews,
                "contributed_to": contributed_to,
                "followers": followers,
            },
        }
    except Exception as exc:
        print(f"Warning: GraphQL fetch failed ({exc}). Falling back to public endpoints.")
        return None


def parse_contributions_html(html: str) -> list[dict[str, Any]]:
    """Parse GitHub contributions HTML fragment into sorted list of daily dicts."""
    tds = re.findall(
        r'<td[^>]*data-date="([^"]+)"[^>]*id="([^"]+)"[^>]*data-level="(\d+)"[^>]*>',
        html,
    )
    tooltips = dict(
        re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>(.*?)</tool-tip>', html, flags=re.S)
    )

    days: list[dict[str, Any]] = []
    for date_str, elem_id, level_str in tds:
        tip = tooltips.get(elem_id, "")
        m = re.search(r"([\d,]+)\s+contribution", tip)
        count = int(m.group(1).replace(",", "")) if m else 0
        days.append({"date": date_str, "count": count, "level": int(level_str)})

    days.sort(key=lambda x: x["date"])
    return days


def fetch_via_public_endpoints(username: str) -> dict[str, Any] | None:
    """
    Fallback Engine (when GITHUB_TOKEN is not set locally):
    Fetches rolling window + multi-year history (2022..present) + REST API v3 user stats.
    """
    html_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        rolling_html, _ = http_request(
            f"https://github.com/users/{username}/contributions",
            headers=html_headers,
            timeout=30,
            max_retries=4,
        )
    except Exception as exc:
        print(f"Error: Failed to fetch rolling contributions HTML: {exc}")
        return None

    rolling_days = parse_contributions_html(rolling_html)
    if not rolling_days:
        return None

    max_date = rolling_days[-1]["date"]
    end_year = max(int(max_date[:4]), ACCOUNT_START_YEAR)

    all_days_map: dict[str, dict[str, Any]] = {}
    for year in range(ACCOUNT_START_YEAR, end_year + 1):
        url = f"https://github.com/users/{username}/contributions?from={year}-01-01&to={year}-12-31"
        try:
            year_html, _ = http_request(url, headers=html_headers, timeout=30, max_retries=4)
            for d in parse_contributions_html(year_html):
                if ACCOUNT_START_DATE <= d["date"] <= max_date:
                    all_days_map[d["date"]] = d
        except Exception as exc:
            print(f"Warning: Failed to fetch contributions for year {year}: {exc}")
            return None

    all_days = [all_days_map[k] for k in sorted(all_days_map)]

    # Fetch user stats via public GitHub REST API
    stats: dict[str, int] | None = None
    try:
        rest_headers = {"Accept": "application/vnd.github.v3+json"}
        user_body, _ = http_request(
            f"https://api.github.com/users/{username}", headers=rest_headers, timeout=20, max_retries=3
        )
        user_json = json.loads(user_body)
        followers = int(user_json.get("followers", 0))

        repos_body, _ = http_request(
            f"https://api.github.com/users/{username}/repos?per_page=100&type=owner",
            headers=rest_headers,
            timeout=20,
            max_retries=3,
        )
        repos_json = json.loads(repos_body)
        stars = sum(
            int(r.get("stargazers_count", 0))
            for r in repos_json
            if isinstance(r, dict) and not r.get("fork")
        )

        prs_body, _ = http_request(
            f"https://api.github.com/search/issues?q=author:{username}+type:pr",
            headers=rest_headers,
            timeout=20,
            max_retries=3,
        )
        prs = int(json.loads(prs_body).get("total_count", 0))

        issues_body, _ = http_request(
            f"https://api.github.com/search/issues?q=author:{username}+type:issue",
            headers=rest_headers,
            timeout=20,
            max_retries=3,
        )
        issues = int(json.loads(issues_body).get("total_count", 0))

        total_commits = fetch_total_commits_search(username)
        if total_commits is None:
            total_commits = sum(d["count"] for d in all_days)

        stats = {
            "stars": stars,
            "commits": total_commits,
            "prs": prs,
            "issues": issues,
            "reviews": 0,
            "contributed_to": 0,
            "followers": followers,
        }
    except Exception as exc:
        print(f"Warning: Public REST stats fetch encountered an error: {exc}")

    return {
        "rolling_days": rolling_days,
        "all_days": all_days,
        "stats": stats,
    }


def compute_streaks(days: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute exact Longest Streak and Current Streak across a chronological list of days.
    Current Streak remains active if either today (days[-1]) or yesterday (days[-2]) has count > 0,
    preventing premature reset at 00:00 UTC before the user commits on the new day.
    """
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
    curr_start = ""
    curr_end = ""

    if days:
        # Determine starting index for active streak (today if > 0, else yesterday if > 0)
        start_idx = -1
        if days[-1]["count"] > 0:
            start_idx = len(days) - 1
        elif len(days) >= 2 and days[-2]["count"] > 0:
            start_idx = len(days) - 2

        if start_idx >= 0:
            curr_end = days[start_idx]["date"]
            for idx in range(start_idx, -1, -1):
                if days[idx]["count"] > 0:
                    curr_start = days[idx]["date"]
                    current_streak += 1
                else:
                    break

    return {
        "best_streak": best_streak,
        "best_start": best_start,
        "best_end": best_end,
        "current_streak": current_streak,
        "curr_start": curr_start,
        "curr_end": curr_end,
    }


def generate_isocalendar(rolling_days: list[dict[str, Any]]) -> None:
    """Render and validate 3D isometric contribution calendar SVG."""
    if not rolling_days:
        print("Warning: No rolling contributions available. Keeping existing isocalendar.svg")
        return

    counts = [d["count"] for d in rolling_days]
    reference = max(counts) if counts else 1
    average = sum(counts) / len(counts) if counts else 0

    streaks = compute_streaks(rolling_days)
    best_streak = streaks["best_streak"]
    current_streak = streaks["current_streak"]

    # Group into weeks (each starting Sunday)
    weeks: list[list[dict[str, Any]]] = []
    cur_week: list[dict[str, Any]] = []
    for d in rolling_days:
        dt = datetime.strptime(d["date"], "%Y-%m-%d")
        dow = (dt.weekday() + 1) % 7  # 0 = Sunday
        if dow == 0 and cur_week:
            weeks.append(cur_week)
            cur_week = []
        cur_week.append(d)
    if cur_week:
        weeks.append(cur_week)

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
                f"</g>"
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

    atomic_write_svg(ISOCALENDAR_PATH, svg)


def calculate_rank(
    *,
    all_commits: bool,
    commits: int,
    prs: int,
    issues: int,
    reviews: int,
    stars: int,
    followers: int,
) -> tuple[str, float]:
    """
    Official anuraghazra/github-readme-stats rank & circle stroke-dashoffset calculation.
    """
    commits_median = 1000 if all_commits else 250
    commits_weight = 2
    prs_median = 50
    prs_weight = 3
    issues_median = 25
    issues_weight = 1
    reviews_median = 2
    reviews_weight = 1
    stars_median = 50
    stars_weight = 4
    followers_median = 10
    followers_weight = 1

    total_weight = (
        commits_weight
        + prs_weight
        + issues_weight
        + reviews_weight
        + stars_weight
        + followers_weight
    )

    thresholds = [1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
    levels = ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]

    exp_cdf = lambda x: 1.0 - (2.0 ** (-x))
    log_norm_cdf = lambda x: x / (1.0 + x)

    rank = (
        1.0
        - (
            commits_weight * exp_cdf(commits / commits_median)
            + prs_weight * exp_cdf(prs / prs_median)
            + issues_weight * exp_cdf(issues / issues_median)
            + reviews_weight * exp_cdf(reviews / reviews_median)
            + stars_weight * log_norm_cdf(stars / stars_median)
            + followers_weight * log_norm_cdf(followers / followers_median)
        )
        / total_weight
    ) * 100.0

    level = levels[next((i for i, t in enumerate(thresholds) if rank <= t), len(levels) - 1)]
    circumference = 2.0 * math.pi * 40.0
    progress = 100.0 - rank
    dashoffset = ((100.0 - progress) / 100.0) * circumference
    return level, dashoffset


def k_formatter(num: int) -> str:
    """Format large numbers matching github-readme-stats (e.g., 1065 -> '1.1k')."""
    if abs(num) > 999:
        val = round(num / 1000.0, 1)
        return f"{int(val)}k" if val.is_integer() else f"{val:.1f}k"
    return str(num)


def generate_github_stats(stats: dict[str, int] | None) -> None:
    """
    Natively render icons/github-stats.svg without any 3rd-party Vercel dependency.
    """
    if not stats:
        print(f"Warning: No stats data available. Keeping existing {STATS_PATH}")
        return

    stars = stats["stars"]
    commits = stats["commits"]
    prs = stats["prs"]
    issues = stats["issues"]
    reviews = stats.get("reviews", 0)
    contributed_to = stats["contributed_to"]
    followers = stats["followers"]

    rank_level, dashoffset = calculate_rank(
        all_commits=True,
        commits=commits,
        prs=prs,
        issues=issues,
        reviews=reviews,
        stars=stars,
        followers=followers,
    )

    stars_str = k_formatter(stars)
    commits_str = k_formatter(commits)
    prs_str = k_formatter(prs)
    issues_str = k_formatter(issues)
    contribs_str = k_formatter(contributed_to)

    svg = f"""<svg
        width="467"
        height="195"
        viewBox="0 0 467 195"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-labelledby="descId"
      >
        <title id="titleId">{DISPLAY_NAME}'s GitHub Stats, Rank: {rank_level}</title>
        <desc id="descId">Total Stars Earned: {stars}, Total Commits  : {commits}, Total PRs: {prs}, Total Issues: {issues}, Contributed to (last year): {contributed_to}</desc>
        <style>
          .header {{
            font: 600 19.5px 'Segoe UI', Ubuntu, Sans-Serif;
            fill: #0969da;
            animation: fadeInAnimation 0.8s ease-in-out forwards;
          }}
          .stat {{
            font: 600 16px 'Segoe UI', Ubuntu, "Helvetica Neue", Sans-Serif; fill: #0f172a;
          }}
          .stagger {{
            opacity: 0;
            animation: fadeInAnimation 0.3s ease-in-out forwards;
          }}
          .rank-text {{
            font: 800 25px 'Segoe UI', Ubuntu, Sans-Serif; fill: #0f172a;
            animation: scaleInAnimation 0.3s ease-in-out forwards;
          }}
          .rank-percentile-header {{
            font-size: 14px;
          }}
          .rank-percentile-text {{
            font-size: 16px;
          }}
          .not_bold {{ font-weight: 400 }}
          .bold {{ font-weight: 700 }}
          .icon {{
            fill: #0969da;
            display: block;
          }}
          .rank-circle-rim {{
            stroke: #0969da;
            fill: none;
            stroke-width: 6;
            opacity: 0.2;
          }}
          .rank-circle {{
            stroke: #0969da;
            stroke-dasharray: 250;
            fill: none;
            stroke-width: 6;
            stroke-linecap: round;
            opacity: 0.8;
            transform-origin: -10px 8px;
            transform: rotate(-90deg);
            animation: rankAnimation 1s forwards ease-in-out;
          }}
          @keyframes rankAnimation {{
            from {{
              stroke-dashoffset: 251.32741228718345;
            }}
            to {{
              stroke-dashoffset: {dashoffset};
            }}
          }}
          @keyframes scaleInAnimation {{
            from {{
              transform: translate(-5px, 5px) scale(0);
            }}
            to {{
              transform: translate(-5px, 5px) scale(1);
            }}
          }}
          @keyframes fadeInAnimation {{
            from {{
              opacity: 0;
            }}
            to {{
              opacity: 1;
            }}
          }}
        </style>
        <rect
          data-testid="card-bg"
          x="0.5"
          y="0.5"
          rx="6"
          height="99%"
          stroke="#cbd5e1" stroke-width="1.2"
          width="466"
          fill="#f8fafc"
          stroke-opacity="1"
        />
        <g data-testid="card-title" transform="translate(25, 35)">
          <g transform="translate(0, 0)">
            <text x="0" y="0" class="header" data-testid="header">{DISPLAY_NAME}'s GitHub Stats</text>
          </g>
        </g>
        <g data-testid="main-card-body" transform="translate(0, 55)">
          <g data-testid="rank-circle" transform="translate(396, 47.5)">
            <circle class="rank-circle-rim" cx="-10" cy="8" r="40" />
            <circle class="rank-circle" cx="-10" cy="8" r="40" />
            <g class="rank-text">
              <text x="-5" y="3" alignment-baseline="central" dominant-baseline="central" text-anchor="middle" data-testid="level-rank-icon">
                {rank_level}
              </text>
            </g>
          </g>
          <svg x="0" y="0">
            <g transform="translate(0, 0)">
              <g class="stagger" style="animation-delay: 450ms" transform="translate(25, 0)">
                <svg data-testid="icon" class="icon" viewBox="0 0 16 16" version="1.1" width="16" height="16">
                  <path fill-rule="evenodd" d="M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25zm0 2.445L6.615 5.5a.75.75 0 01-.564.41l-3.097.45 2.24 2.184a.75.75 0 01.216.664l-.528 3.084 2.769-1.456a.75.75 0 01.698 0l2.77 1.456-.53-3.084a.75.75 0 01.216-.664l2.24-2.183-3.096-.45a.75.75 0 01-.564-.41L8 2.694v.001z"/>
                </svg>
                <text class="stat  bold" x="25" y="12.5">Total Stars Earned:</text>
                <text class="stat  bold" x="248" y="12.5" data-testid="stars">{stars_str}</text>
              </g>
            </g>
            <g transform="translate(0, 25)">
              <g class="stagger" style="animation-delay: 600ms" transform="translate(25, 0)">
                <svg data-testid="icon" class="icon" viewBox="0 0 16 16" version="1.1" width="16" height="16">
                  <path fill-rule="evenodd" d="M1.643 3.143L.427 1.927A.25.25 0 000 2.104V5.75c0 .138.112.25.25.25h3.646a.25.25 0 00.177-.427L2.715 4.215a6.5 6.5 0 11-1.18 4.458.75.75 0 10-1.493.154 8.001 8.001 0 101.6-5.684zM7.75 4a.75.75 0 01.75.75v2.992l2.028.812a.75.75 0 01-.557 1.392l-2.5-1A.75.75 0 017 8.25v-3.5A.75.75 0 017.75 4z"/>
                </svg>
                <text class="stat  bold" x="25" y="12.5">Total Commits:</text>
                <text class="stat  bold" x="248" y="12.5" data-testid="commits">{commits_str}</text>
              </g>
            </g>
            <g transform="translate(0, 50)">
              <g class="stagger" style="animation-delay: 750ms" transform="translate(25, 0)">
                <svg data-testid="icon" class="icon" viewBox="0 0 16 16" version="1.1" width="16" height="16">
                  <path fill-rule="evenodd" d="M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z"/>
                </svg>
                <text class="stat  bold" x="25" y="12.5">Total PRs:</text>
                <text class="stat  bold" x="248" y="12.5" data-testid="prs">{prs_str}</text>
              </g>
            </g>
            <g transform="translate(0, 75)">
              <g class="stagger" style="animation-delay: 900ms" transform="translate(25, 0)">
                <svg data-testid="icon" class="icon" viewBox="0 0 16 16" version="1.1" width="16" height="16">
                  <path fill-rule="evenodd" d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm9 3a1 1 0 11-2 0 1 1 0 012 0zm-.25-6.25a.75.75 0 00-1.5 0v3.5a.75.75 0 001.5 0v-3.5z"/>
                </svg>
                <text class="stat  bold" x="25" y="12.5">Total Issues:</text>
                <text class="stat  bold" x="248" y="12.5" data-testid="issues">{issues_str}</text>
              </g>
            </g>
            <g transform="translate(0, 100)">
              <g class="stagger" style="animation-delay: 1050ms" transform="translate(25, 0)">
                <svg data-testid="icon" class="icon" viewBox="0 0 16 16" version="1.1" width="16" height="16">
                  <path fill-rule="evenodd" d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z"/>
                </svg>
                <text class="stat  bold" x="25" y="12.5">Contributed to (last year):</text>
                <text class="stat  bold" x="248" y="12.5" data-testid="contribs">{contribs_str}</text>
              </g>
            </g>
          </svg>
        </g>
      </svg>"""

    atomic_write_svg(STATS_PATH, svg)


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


def fmt_short_date(date_str: str, ref_year: int | None = None) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if ref_year is not None and dt.year != ref_year:
        return f"{dt.strftime('%b')} {dt.day}, {dt.year}"
    return f"{dt.strftime('%b')} {dt.day}"


def generate_streak_stats(all_days: list[dict[str, Any]]) -> None:
    """
    Generate icons/streak-stats.svg from exact all-time multi-year contribution history (zero hardcode).
    """
    if not all_days:
        print("Warning: No all-time contributions available. Keeping existing streak-stats.svg")
        return

    ref_year = int(all_days[-1]["date"][:4])
    streaks = compute_streaks(all_days)
    best_streak = streaks["best_streak"]
    best_start = streaks["best_start"]
    best_end = streaks["best_end"]
    current_streak = streaks["current_streak"]
    curr_start = streaks["curr_start"]
    curr_end = streaks["curr_end"]

    if current_streak == 0:
        curr_range = fmt_short_date(all_days[-1]["date"], ref_year)
    elif current_streak == 1 and curr_end:
        curr_range = fmt_short_date(curr_end, ref_year)
    elif curr_start and curr_end:
        curr_range = f"{fmt_short_date(curr_start, ref_year)} - {fmt_short_date(curr_end, ref_year)}"
    else:
        curr_range = "Present"

    if best_start and best_end:
        best_range = f"{fmt_short_date(best_start, ref_year)} - {fmt_short_date(best_end, ref_year)}"
    else:
        best_range = "Present"

    total_val = sum(d["count"] for d in all_days)
    svg = render_streak_svg(
        total_str=f"{total_val:,}",
        total_range=f"{ACCOUNT_START_LABEL} - Present",
        curr_str=str(current_streak),
        curr_range=curr_range,
        best_str=str(best_streak),
        best_range=best_range,
    )
    atomic_write_svg(STREAK_PATH, svg)


def main() -> None:
    token = get_github_token()
    data: dict[str, Any] | None = None

    if token:
        print("GITHUB_TOKEN detected. Using primary GitHub GraphQL API engine...")
        data = fetch_via_graphql(USERNAME, token)

    if data is None:
        print("Using multi-year public GitHub endpoints engine...")
        data = fetch_via_public_endpoints(USERNAME)

    if not data:
        print("Warning: Could not fetch fresh data from GitHub. Existing SVGs preserved.")
        return

    generate_isocalendar(data["rolling_days"])
    generate_github_stats(data["stats"])
    generate_streak_stats(data["all_days"])


if __name__ == "__main__":
    main()
