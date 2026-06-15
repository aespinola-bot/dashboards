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
        out.append({"date": date, "home": home, "away": away,
                    "score": [int(sc.group(1)), int(sc.group(2))]})
    return out


def collect_all_results():
    import time
    all_results = []
    for g in GROUPS:
        try:
            wt = fetch_group_wikitext(g)
        except Exception as e:
            print(f"  WARN Group {g}: fetch failed -- {e}", file=sys.stderr)
            continue
        rs = parse_group_results(wt)
        print(f"  Group {g}: {len(rs)} finished")
        all_results.extend(rs)
        time.sleep(0.5)  # be nice to Wikipedia API
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

    if args.commit and not args.dry_run and (added or updated or yt_added):
        bits = []
        if added or updated: bits.append(f"{added+updated} score(s)")
        if yt_added: bits.append(f"{yt_added} highlight(s)")
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
