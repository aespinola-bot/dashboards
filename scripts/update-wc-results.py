#!/usr/bin/env python3
"""
World Cup 2026 results auto-fetcher.

Pulls actual scores from Wikipedia (group A-L pages), patches
`worldcup2026.html` MATCHES entries by adding/updating `actual:[h,a]`,
and regenerates the matching markdown table in `WorldCup2026_Calendar.md`.

Usage:
    python scripts/update-wc-results.py
    python scripts/update-wc-results.py --dry-run
    python scripts/update-wc-results.py --commit --push

Run after each matchday — idempotent (only adds/updates actual fields).
"""

import argparse
import json
import os
import re
import sys
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = REPO_ROOT / "worldcup2026.html"
MD_PATH   = Path(os.path.expanduser(
    r"~\OneDrive - Microsoft\Desktop\agency-output\WorldCup2026_Calendar.md"))

GROUPS = list("ABCDEFGHIJKL")

USER_AGENT = "WC2026-results-bot/1.0 (personal dashboard; toespino)"

IOC = {
    "MEX":"Mexico", "RSA":"South Africa", "KOR":"South Korea", "CZE":"Czech Republic",
    "CAN":"Canada", "BIH":"Bosnia & Herzegovina", "QAT":"Qatar", "SUI":"Switzerland",
    "BRA":"Brazil", "MAR":"Morocco", "SCO":"Scotland", "HAI":"Haiti",
    "USA":"United States", "AUS":"Australia", "PAR":"Paraguay", "TUR":"Turkey",
    "GER":"Germany", "CIV":"Ivory Coast", "CUW":"Curaçao", "ECU":"Ecuador",
    "NED":"Netherlands", "JPN":"Japan", "SWE":"Sweden", "TUN":"Tunisia",
    "BEL":"Belgium", "EGY":"Egypt", "IRN":"Iran", "NZL":"New Zealand",
    "ESP":"Spain", "KSA":"Saudi Arabia", "CPV":"Cape Verde", "URU":"Uruguay",
    "FRA":"France", "SEN":"Senegal", "IRQ":"Iraq", "NOR":"Norway",
    "ARG":"Argentina", "ALG":"Algeria", "AUT":"Austria", "JOR":"Jordan",
    "POR":"Portugal", "COD":"DR Congo", "UZB":"Uzbekistan", "COL":"Colombia",
    "ENG":"England", "CRO":"Croatia", "GHA":"Ghana", "PAN":"Panama",
}


def safe_print(msg: str) -> None:
    """Print, downgrading to ASCII if the console can't handle Unicode."""
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = (sys.stdout.encoding or "ascii")
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"))


def http_get(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_group_wikitext(group: str) -> str:
    url = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=parse&page=2026_FIFA_World_Cup_Group_{group}"
        "&format=json&prop=wikitext"
    )
    data = json.loads(http_get(url))
    return data["parse"]["wikitext"]["*"]


FOOTBALL_BOX_RE = re.compile(
    r"\{\{#invoke:football box\|main(?P<body>.*?)\n\}\}", re.DOTALL,
)
DATE_RE   = re.compile(r"\|date=\{\{Start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})\}\}")
TEAM1_RE  = re.compile(r"\|team1=\{\{#invoke:flag\|[^|]+\|([A-Z]{3})\}\}")
TEAM2_RE  = re.compile(r"\|team2=\{\{#invoke:flag\|[^|]+\|([A-Z]{3})\}\}")
SCORE_RE  = re.compile(r"\|score=\{\{score link\|[^|]*\|(\d+)\s*[-\u2013\u2014]\s*(\d+)\}\}")
SIMPLE_SCORE_RE = re.compile(r"\|score=\s*(\d+)\s*[-\u2013\u2014]\s*(\d+)\s*\|")

GOALS_BLOCK_RE = re.compile(r"\|goals(?P<side>1|2)=(?P<body>.*?)(?=\n\||\n\}\})", re.DOTALL)
GOAL_LINE_RE   = re.compile(r"\*\s*(?P<player>[^\n]+?)\s+(?P<minute>\d+(?:\+\d+)?)'", re.MULTILINE)
STADIUM_RE     = re.compile(r"\|stadium=\s*([^\n]+)")
ATTENDANCE_RE  = re.compile(r"\|attendance=\s*([^\n<]+)")
REFEREE_RE     = re.compile(r"\|referee=\s*([^\n<]+)")
FIFA_URL_RE    = re.compile(r"https?://(?:www\.)?fifa\.com/[^\s\"\]]+match-cent[^\s\"\]]+")


def _strip_wiki_links(s: str) -> str:
    """[[Page|Display]] -> Display ; [[Page]] -> Page ; strip refs/templates."""
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)               # {{...}}
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL)
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", s)  # [[A|B]] -> B
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)             # [[A]] -> A
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"<[^>]+>", "", s)                         # any other tags
    return s.strip()


GOAL_TEMPLATE_RE = re.compile(r"\{\{goal\|([^{}]+)\}\}", re.IGNORECASE)


def _parse_goal_line(line: str) -> list[dict]:
    """Parse one bullet line from a goals block. Returns one dict per goal.
    Supports multiple Wikipedia formats:
      *[[Player|Display]] 9' (pen.)
      *[[Player|Display]] {{goal|9}} {{goal|45+1|pen.}}
      *[[Player]] {{goal|9|45+1|o.g.}}
      *[[Player]] 74, 90                   (comma-separated, no apostrophe)
      *[[Player]] 90+7 pen                 (suffix modifier, no parens)
      [[Player]] 59'                       (no leading bullet)
    """
    text = line.lstrip("*").strip()
    if not text:
        return []
    # Pull out all {{goal|...}} occurrences first
    goal_chunks = GOAL_TEMPLATE_RE.findall(text)
    # Remove the goal templates from the line so the remainder is just the player name (+ refs)
    name_text = GOAL_TEMPLATE_RE.sub("", text)
    name_only = _strip_wiki_links(name_text).strip(" ,;:")
    out: list[dict] = []
    if goal_chunks:
        for chunk in goal_chunks:
            parts = [p.strip() for p in chunk.split("|") if p.strip()]
            mins: list[str] = []
            tag = ""
            for p in parts:
                if re.fullmatch(r"\d+(\+\d+)?", p):
                    mins.append(p)
                else:
                    pl = p.lower().rstrip(".")
                    if "pen" in pl: tag = "pen"
                    elif pl in ("o.g", "og") or "own goal" in pl: tag = "og"
            for mn in mins:
                out.append({"p": name_only, "m": mn + "'", **({"t": tag} if tag else {})})
        return out
    # Fallback: literal minutes format. Supports:
    #   "Krejčí 59'"        (apostrophe)
    #   "Manzambi 74, 90"   (comma-separated, no apostrophe)
    #   "Xhaka 90+7 pen"    (suffix modifier, no parens)
    stripped = _strip_wiki_links(text)
    # Any number (with optional stoppage), followed by optional apostrophe.
    minute_rx = re.compile(r"\b(\d{1,3}(?:\+\d+)?)'?\b")
    first = minute_rx.search(stripped)
    if not first:
        return []
    player = stripped[:first.start()].strip(" ,;:")
    if not player:
        return []
    rest = stripped[first.start():]
    rest_lc = rest.lower()
    # Tags apply to the whole line unless a per-minute tag is specified inline
    line_tag = ""
    if re.search(r"\bpen(?:alty|\.)?\b", rest_lc): line_tag = "pen"
    elif re.search(r"\b(?:o\.?g\.?|own\s+goal)\b", rest_lc): line_tag = "og"
    for mn in minute_rx.findall(rest):
        # Skip absurd values (jersey numbers, years) — real minutes are 1..120
        base = int(mn.split("+")[0])
        if base < 1 or base > 120:
            continue
        out.append({"p": player, "m": mn + "'", **({"t": line_tag} if line_tag else {})})
    return out


def parse_match_report(body: str) -> dict | None:
    """Extract match report fields (goals per side, stadium, attendance,
    referee, FIFA report URL) from a {{#invoke:football box}} body."""
    out: dict = {}
    for gm in GOALS_BLOCK_RE.finditer(body):
        side = "home" if gm.group("side") == "1" else "away"
        gb = gm.group("body")
        goals: list[dict] = []
        for line in gb.splitlines():
            # Some Wikipedia editors omit the leading "*" bullet marker,
            # especially when a side has only one scorer. Accept any line
            # that yields at least one goal on parse.
            stripped = line.strip()
            if not stripped:
                continue
            goals.extend(_parse_goal_line(stripped))
        if goals:
            out[f"goals_{side}"] = goals
    sm = STADIUM_RE.search(body)
    if sm: out["stadium"] = _strip_wiki_links(sm.group(1))
    am = ATTENDANCE_RE.search(body)
    if am:
        att = _strip_wiki_links(am.group(1)).strip()
        if att: out["attendance"] = att
    rm = REFEREE_RE.search(body)
    if rm: out["referee"] = _strip_wiki_links(rm.group(1))
    um = FIFA_URL_RE.search(body)
    if um: out["fifa"] = um.group(0)
    return out or None


def parse_group_results(wikitext: str):
    out = []
    for m in FOOTBALL_BOX_RE.finditer(wikitext):
        body = m.group("body")
        d = DATE_RE.search(body)
        t1 = TEAM1_RE.search(body)
        t2 = TEAM2_RE.search(body)
        sc = SCORE_RE.search(body) or SIMPLE_SCORE_RE.search(body)
        if not (d and t1 and t2 and sc):
            continue
        date = f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d}"
        home = IOC.get(t1.group(1))
        away = IOC.get(t2.group(1))
        if not home or not away:
            continue
        report = parse_match_report(body)
        out.append({"date": date, "home": home, "away": away,
                    "score": [int(sc.group(1)), int(sc.group(2))],
                    "report": report})
    return out


def collect_all_results():
    import time
    all_results = []
    for g in GROUPS:
        # Retry with exponential backoff on 429 rate-limit
        for attempt in range(3):
            try:
                wt = fetch_group_wikitext(g)
                break
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    delay = 5 * (attempt + 1)
                    print(f"  Group {g}: rate-limited, retrying in {delay}s...", file=sys.stderr)
                    time.sleep(delay)
                else:
                    print(f"  WARN Group {g}: fetch failed -- {e}", file=sys.stderr)
                    wt = None
                    break
        if wt is None:
            continue
        rs = parse_group_results(wt)
        print(f"  Group {g}: {len(rs)} finished")
        all_results.extend(rs)
        time.sleep(1.2)  # be nice to Wikipedia API (was 0.5, still 429ing)
    return all_results


# ---------- YouTube highlight lookup ----------

def find_youtube_highlight(home: str, away: str) -> str | None:
    """Best-effort lookup of an embed-friendly highlight video ID from
    YouTube search. Returns 11-char video ID or None. No API key needed.
    Strongly prefers third-party broadcasters (FOX Sports, Telemundo,
    FOX Soccer, ESPN) over the FIFA channel, because FIFA disables
    in-page embedding on its uploads.
    """
    from urllib.parse import quote
    import json as _json
    queries = [
        f"{home} vs {away} World Cup 2026 highlights",
        f"FOX Sports {home} {away} 2026 highlights",
    ]
    raw_ids: list[str] = []
    for q in queries:
        try:
            html = http_get(f"https://www.youtube.com/results?search_query={quote(q)}")
        except Exception:
            continue
        # Permissive: capture any 11-char ID after either "videoId":" or watch?v=
        for vid in re.findall(r'(?:videoId":"|watch\?v=)([a-zA-Z0-9_-]{11})', html):
            if vid not in raw_ids:
                raw_ids.append(vid)
            if len(raw_ids) >= 25:
                break
        if len(raw_ids) >= 25:
            break
    if not raw_ids:
        return None

    # Fetch oEmbed metadata (author + title) for ranking. Skip silently on failure.
    candidates = []  # (vid, author, title)
    for vid in raw_ids[:20]:
        try:
            meta = http_get(
                f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
            )
            j = _json.loads(meta)
            candidates.append((vid, (j.get("author_name") or ""), (j.get("title") or "")))
        except Exception:
            continue
    if not candidates:
        return None

    PREFERRED_CHANNELS = {"FOX Sports", "Telemundo Deportes", "FOX Soccer", "ESPN FC", "OneFootball"}
    # Channels that primarily post video-game/simulation content
    GAMING_CHANNELS = {"NuruBuzz", "JaviGameplay", "M2RTV", "PesXMods", "WorldCupOfficialEAFC", "Football Fox"}
    def score(author: str, title: str) -> int:
        a = author.strip()
        t = title.lower()
        s = 0
        if "highlight" in t: s += 6
        if "2026" in t: s += 3
        if "world cup" in t or "fifa" in t: s += 2
        if home.lower() in t and away.lower() in t: s += 4
        # Channel preferences — FIFA officially blocks embedding, so deprioritize hard
        if a in PREFERRED_CHANNELS: s += 8
        if a == "FIFA": s -= 5
        # Hard reject: video game / simulation content
        if a in GAMING_CHANNELS: s -= 30
        if any(g in t for g in (
            "ea fc", "ea sports fc", "fc 26", "fifa 26", "fifa26",
            "pes 2", "efootball", "video game", "videogame",
            "gameplay", "simulation", "predicted by ea", "let's play",
            "career mode", "ps5", "ps4", "xbox", "next gen graphics",
        )): s -= 30
        # Negative content
        if "#shorts" in t or "shorts" in t: s -= 4
        if "live" in t: s -= 2
        if "preview" in t or "prediction" in t: s -= 6
        if "anthem" in t or "ceremony" in t: s -= 6
        if "match before" in t or "friendly" in t: s -= 6
        if "press conference" in t or "post-match" in t: s -= 4
        if "fans celebrate" in t or "reaction" in t: s -= 3
        return s

    candidates.sort(key=lambda c: score(c[1], c[2]), reverse=True)
    best_vid, best_auth, best_title = candidates[0]
    # Refuse to return obviously-bad hits (gaming channels, etc.)
    best_score = score(best_auth, best_title)
    if best_score < 0:
        safe_print(f"    YT: {home} vs {away} -> NO clean highlight found (best={best_vid} [{best_auth}] score={best_score})")
        return None
    safe_print(f"    YT: {home} vs {away} -> {best_vid} [{best_auth}] ({best_title[:60]})")
    return best_vid


HIGHLIGHT_INLINE_RE = re.compile(r"\s*highlight:'[^']*',")


def patch_html_with_highlights(html: str) -> tuple[str, int]:
    """For every match that has actual:[..] but no highlight:'..',
    look up a YouTube video ID and inject highlight:'VIDEO_ID' before note:.
    """
    import time
    matches_in_html = list(MATCH_LINE_RE.finditer(html))
    # Build (id, home, away, has_actual, has_highlight) tuples
    todo = []
    for m in matches_in_html:
        rest = m.group("rest")
        if "actual:[" not in rest:
            continue
        if "highlight:'" in rest:
            continue
        todo.append((int(m.group("id")), m.group("home"), m.group("away")))

    if not todo:
        return html, 0
    print(f"  YT lookup needed for {len(todo)} match(es)...")

    found = {}
    for mid, home, away in todo:
        try:
            vid = find_youtube_highlight(home, away)
            if vid:
                found[mid] = vid
        except Exception as e:
            safe_print(f"    YT lookup error for M{mid} {home} vs {away}: {e}")
        time.sleep(0.6)  # be polite

    if not found:
        return html, 0

    def repl(m):
        mid = int(m.group("id"))
        vid = found.get(mid)
        if not vid:
            return m.group(0)
        head = m.group(1)
        rest = m.group("rest")
        tail = m.group(m.lastindex)
        new_rest = f" highlight:'{vid}',{rest}"
        return head + new_rest + tail

    new_html = MATCH_LINE_RE.sub(repl, html)
    return new_html, len(found)


MATCH_LINE_RE = re.compile(
    r"(\{id:(?P<id>\d+),\s+group:'(?P<g>[A-L])',\s+date:'(?P<date>\d{4}-\d{2}-\d{2})',\s+timePT:'[^']*',\s+venue:'[^']*',\s+home:'(?P<home>[^']*)',\s+away:'(?P<away>[^']*)',\s+tv:'[^']*',\s+pred:\[\d+,\d+\],)(?P<rest>.*?)(\})",
    re.DOTALL,
)
ACTUAL_INLINE_RE = re.compile(r"\s*actual:\[\d+,\d+\],")


def patch_html(html: str, results: list):
    lookup = {(r["date"], r["home"], r["away"]): r["score"] for r in results}
    added = 0
    updated = 0

    def repl(m):
        nonlocal added, updated
        head = m.group(1)
        rest = m.group("rest")
        tail = m.group(m.lastindex)
        key = (m.group("date"), m.group("home"), m.group("away"))
        score = lookup.get(key)
        if not score:
            return m.group(0)
        new_actual = f" actual:[{score[0]},{score[1]}],"
        if ACTUAL_INLINE_RE.search(rest):
            new_rest = ACTUAL_INLINE_RE.sub(new_actual, rest, count=1)
            if new_rest != rest:
                updated += 1
            return head + new_rest + tail
        else:
            added += 1
            return head + new_actual + rest + tail

    return MATCH_LINE_RE.sub(repl, html), added, updated


MD_ROW_RE = re.compile(
    r"^(\|\s*(?P<id>\d+)\s*\|\s*\d{2}:\d{2}\s*\|\s*\*\*)(?P<bold>[^*]+?)(\*\*\s*\((?P<g>[A-L])\)\s*\|\s*)(?P<pred>[^|]+?)(\s*\|)",
    re.MULTILINE,
)


REPORTS_BLOCK_RE = re.compile(
    r"(// __MATCH_REPORTS_START__\n)(.*?)(\n\s*// __MATCH_REPORTS_END__)",
    re.DOTALL,
)


def patch_html_with_reports(html: str, results: list) -> tuple[str, int]:
    """Inject a MATCH_REPORTS = {...} JS const block into worldcup2026.html
    between // __MATCH_REPORTS_START__ and // __MATCH_REPORTS_END__ markers.
    Maps Wikipedia match-report dicts to the in-HTML match ids."""
    if not REPORTS_BLOCK_RE.search(html):
        return html, 0  # markers not present yet — caller must add them once

    # Build (date, home, away) -> id from the HTML
    id_lookup: dict[tuple[str, str, str], int] = {}
    for m in MATCH_LINE_RE.finditer(html):
        id_lookup[(m.group("date"), m.group("home"), m.group("away"))] = int(m.group("id"))

    reports: dict[int, dict] = {}
    for r in results:
        rep = r.get("report") or {}
        mid = id_lookup.get((r["date"], r["home"], r["away"]))
        if mid is None:
            continue
        # Best-effort: enrich with ESPN team statistics (possession, shots, ...)
        try:
            stats = fetch_espn_stats(r["date"], r["home"], r["away"])
            if stats:
                rep = dict(rep)  # don't mutate input
                rep["stats"] = stats
        except Exception as e:
            safe_print(f"  ESPN stats failed for M{mid} {r['home']}-{r['away']}: {e}")
        if rep:
            reports[mid] = rep

    if not reports:
        body = "const MATCH_REPORTS = {};"
    else:
        ordered = {str(k): reports[k] for k in sorted(reports.keys())}
        body = "const MATCH_REPORTS = " + json.dumps(ordered, ensure_ascii=False) + ";"

    new_html = REPORTS_BLOCK_RE.sub(
        lambda m: m.group(1) + body + m.group(3),
        html,
    )
    return new_html, len(reports)


# ---- ESPN team-statistics enrichment ----------------------------------------
# ESPN exposes WC2026 stats at site.api.espn.com (no auth, no rate-limit hassle).

ESPN_TEAM_ALIASES = {
    "south korea": ["korea republic"],
    "korea republic": ["south korea"],
    "ivory coast": ["côte d'ivoire", "cote d'ivoire"],
    "côte d'ivoire": ["ivory coast"],
    "cape verde": ["cabo verde"],
    "cabo verde": ["cape verde"],
    "iran": ["ir iran"],
    "united states": ["usa"],
    "usa": ["united states"],
    "czech republic": ["czechia"],
    "czechia": ["czech republic"],
    "bosnia & herzegovina": ["bosnia-herzegovina", "bosnia and herzegovina"],
    "bosnia-herzegovina": ["bosnia & herzegovina"],
    "turkey": ["türkiye", "turkiye"],
    "türkiye": ["turkey"],
    "curacao": ["curaçao"],
    "curaçao": ["curacao"],
}

# ESPN stat key -> (label, format)  -- order matters for display
ESPN_STAT_MAP = [
    ("possessionPct",   "Possession",      "{:.0f}%"),
    ("totalShots",      "Shots",           "{:.0f}"),
    ("shotsOnTarget",   "Shots on target", "{:.0f}"),
    ("blockedShots",    "Shots blocked",   "{:.0f}"),
    ("wonCorners",      "Corners",         "{:.0f}"),
    ("offsides",        "Offsides",        "{:.0f}"),
    ("foulsCommitted",  "Fouls",           "{:.0f}"),
    ("yellowCards",     "Yellow cards",    "{:.0f}"),
    ("redCards",        "Red cards",       "{:.0f}"),
    ("saves",           "Saves",           "{:.0f}"),
    ("totalPasses",     "Passes",          "{:.0f}"),
    ("passPct",         "Pass accuracy",   "{:.0%}"),
]


def _team_match(name: str, espn_name: str) -> bool:
    a = name.strip().lower()
    b = espn_name.strip().lower()
    if a == b:
        return True
    for x, alts in ESPN_TEAM_ALIASES.items():
        if (a == x and b in alts) or (b == x and a in alts):
            return True
    return False


_ESPN_SCOREBOARD_CACHE: dict[str, dict] = {}


def _espn_scoreboard(date: str) -> dict:
    """date 'YYYY-MM-DD' -> ESPN scoreboard JSON for that day (cached)."""
    if date in _ESPN_SCOREBOARD_CACHE:
        return _ESPN_SCOREBOARD_CACHE[date]
    yyyymmdd = date.replace("-", "")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={yyyymmdd}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    _ESPN_SCOREBOARD_CACHE[date] = data
    return data


def fetch_espn_stats(date: str, home: str, away: str) -> dict | None:
    """Return {'home':{stat:val,...}, 'away':{...}} or None on failure.
    Tries the listed date, then date+1 to cover late-night PT → next-day UTC."""
    from datetime import datetime, timedelta
    candidates = [date]
    try:
        d0 = datetime.strptime(date, "%Y-%m-%d")
        candidates.append((d0 + timedelta(days=1)).strftime("%Y-%m-%d"))
    except Exception:
        pass
    event = None
    espn_home_first = True
    for try_date in candidates:
        sb = _espn_scoreboard(try_date)
        for e in sb.get("events", []):
            comps = (e.get("competitions") or [{}])[0].get("competitors") or []
            names = [(c.get("team") or {}).get("displayName", "") for c in comps]
            if len(names) != 2:
                continue
            if (_team_match(home, names[0]) and _team_match(away, names[1])) or \
               (_team_match(home, names[1]) and _team_match(away, names[0])):
                event = e
                espn_home_first = _team_match(home, names[0])
                break
        if event:
            break
    if not event:
        return None
    if not (event.get("status", {}).get("type", {}) or {}).get("completed"):
        return None
    eid = event["id"]
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={eid}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urlopen(req, timeout=15) as r:
        summary = json.loads(r.read().decode("utf-8"))
    teams = (summary.get("boxscore") or {}).get("teams") or []
    if len(teams) != 2:
        return None
    raw = []
    for t in teams:
        d = {s.get("name"): s.get("displayValue") for s in (t.get("statistics") or [])}
        raw.append((t.get("team", {}).get("displayName", ""), d))
    # Re-order so [0]=home, [1]=away based on user's match orientation
    if not espn_home_first:
        raw = [raw[1], raw[0]]
    out: dict = {"home": {"team": home, "rows": []}, "away": {"team": away, "rows": []}}
    def _norm(key, val):
        if val is None: return None
        s = str(val).strip()
        if key == "passPct":
            try:
                # ESPN returns 0.9 meaning 90% (or sometimes already a %)
                f = float(s.rstrip("%"))
                if f <= 1.5: f *= 100
                return f"{round(f)}%"
            except: return s
        if key == "possessionPct" and not s.endswith("%"):
            return s + "%"
        return s
    for key, label, _fmt in ESPN_STAT_MAP:
        h = raw[0][1].get(key)
        a = raw[1][1].get(key)
        if h is None and a is None:
            continue
        out["home"]["rows"].append({"k": label, "v": _norm(key, h)})
        out["away"]["rows"].append({"k": label, "v": _norm(key, a)})
    return out






def _ai_accuracy_marker(pred, actual):
    if pred == actual:
        return "\u2713\u2713"  # ✓✓ exact
    p_out = "H" if pred[0] > pred[1] else ("A" if pred[0] < pred[1] else "D")
    a_out = "H" if actual[0] > actual[1] else ("A" if actual[0] < actual[1] else "D")
    return "\u2713" if p_out == a_out else "\u2717"  # ✓ outcome / ✗ miss


def regen_md(md: str, html_matches: list):
    by_id = {m["id"]: m for m in html_matches}
    locked = 0

    def repl(m):
        nonlocal locked
        mid = int(m.group("id"))
        info = by_id.get(mid)
        if not info:
            return m.group(0)
        home, away = info["home"], info["away"]
        actual = info.get("actual")
        ai_pred = info["pred"]
        head = m.group(1)
        if actual:
            marker = _ai_accuracy_marker(ai_pred, actual)
            new_bold = f"\U0001F512 {home} {actual[0]}\u2013{actual[1]} {away}"
            # Show AI pred + accuracy marker in the Pred column
            new_pred = f"AI: {ai_pred[0]}\u2013{ai_pred[1]} {marker}"
            locked += 1
        else:
            new_bold = f"{home} vs {away}"
            new_pred = f"{ai_pred[0]}\u2013{ai_pred[1]}"
        return f"{head}{new_bold}** ({info['group']}) | {new_pred} |"

    new_md = MD_ROW_RE.sub(repl, md)

    # Rename column header "Pred" -> "AI Pred" once
    new_md = re.sub(r"\|\s*Pred\s*\|", "| AI Pred |", new_md)

    note_marker = "Locked real result"
    note_text = (
        f"> \U0001F512 = Locked real result. "
        f"As of last update, **{locked} of 72** matches finalized. "
        f"AI accuracy marker: \u2713\u2713 exact, \u2713 outcome, \u2717 miss."
    )
    if note_marker not in new_md:
        new_md = re.sub(r"(\n---\n)", "\n" + note_text + "\n" + r"\1", new_md, count=1)
    else:
        # Replace the entire existing legend line in place
        new_md = re.sub(r"^>\s*\U0001F512[^\n]*", note_text, new_md, flags=re.MULTILINE)

    return new_md, locked


HTML_MATCH_RE = re.compile(
    r"\{id:(?P<id>\d+),\s+group:'(?P<g>[A-L])',\s+date:'(?P<date>[\d-]+)',\s+timePT:'(?P<t>[^']*)',\s+venue:'(?P<v>[^']*)',\s+home:'(?P<home>[^']*)',\s+away:'(?P<away>[^']*)',\s+tv:'(?P<tv>[^']*)',\s+pred:\[(?P<ph>\d+),(?P<pa>\d+)\](?P<rest>.*?)\}",
    re.DOTALL,
)
HTML_ACTUAL_RE = re.compile(r"actual:\[(\d+),(\d+)\]")


def extract_matches_from_html(html: str):
    out = []
    for m in HTML_MATCH_RE.finditer(html):
        rec = {
            "id": int(m.group("id")),
            "group": m.group("g"),
            "date": m.group("date"),
            "home": m.group("home"),
            "away": m.group("away"),
            "pred": [int(m.group("ph")), int(m.group("pa"))],
        }
        a = HTML_ACTUAL_RE.search(m.group("rest"))
        if a:
            rec["actual"] = [int(a.group(1)), int(a.group(2))]
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--skip-md", action="store_true")
    ap.add_argument("--skip-yt", action="store_true", help="Skip YouTube highlight lookup.")
    args = ap.parse_args()

    print("Fetching results from Wikipedia (12 group pages)...")
    results = collect_all_results()
    print(f"  -> {len(results)} finished matches total\n")

    if not HTML_PATH.exists():
        print(f"ERR HTML not found: {HTML_PATH}", file=sys.stderr)
        sys.exit(1)

    html = HTML_PATH.read_text(encoding="utf-8")
    new_html, added, updated = patch_html(html, results)
    print(f"HTML patch: +{added} added, ~{updated} updated")

    # Look up YouTube highlight video IDs for any finished match that doesn't have one yet
    yt_added = 0
    if not args.skip_yt:
        new_html, yt_added = patch_html_with_highlights(new_html)
        print(f"YouTube highlights: +{yt_added} found")

    # Inject match reports (goalscorers, attendance, referee, ...) if markers exist
    new_html, reports_count = patch_html_with_reports(new_html, results)
    print(f"Match reports: {reports_count} synced")

    if not args.dry_run and new_html != html:
        HTML_PATH.write_text(new_html, encoding="utf-8")
        print(f"  wrote {HTML_PATH}")

    md_locked = 0
    if not args.skip_md and MD_PATH.exists():
        md = MD_PATH.read_text(encoding="utf-8")
        matches = extract_matches_from_html(new_html)
        new_md, md_locked = regen_md(md, matches)
        print(f"MD: {md_locked}/72 matches marked locked")
        if not args.dry_run and new_md != md:
            MD_PATH.write_text(new_md, encoding="utf-8")
            print(f"  wrote {MD_PATH}")
    elif not MD_PATH.exists():
        print(f"  WARN MD not found at {MD_PATH} -- skipping MD regen.")

    if args.commit and not args.dry_run and (added or updated or yt_added or reports_count):
        bits = []
        if added or updated: bits.append(f"{added+updated} score(s)")
        if yt_added: bits.append(f"{yt_added} highlight(s)")
        if reports_count: bits.append(f"{reports_count} report(s)")
        msg = f"WC2026: auto-sync {' + '.join(bits)} from Wikipedia/YouTube"
        subprocess.run(["git", "-C", str(REPO_ROOT), "add", "worldcup2026.html"], check=True)
        subprocess.run(["git", "-C", str(REPO_ROOT), "commit", "-m", msg], check=True)
        print(f"  committed: {msg}")
        if args.push:
            subprocess.run(["git", "-C", str(REPO_ROOT), "push"], check=True)
            print(f"  pushed")

    print("\nDone.")


if __name__ == "__main__":
    main()
