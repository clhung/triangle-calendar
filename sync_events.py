#!/usr/bin/env python3
"""
sync_events.py
Barebone Python script to scrape Triangle on the Cheap kids events
and save to an RFC 5545 .ics calendar file readable by Google Calendar.

Requirements: Python 3.7+ (Standard Library only - zero dependencies)
Usage:
    python3 sync_events.py
    python3 sync_events.py output.ics
"""

import sys
import os
import re
import html
import json
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional, Tuple

TARGET_URL = "https://triangleonthecheap.com/free-cheap-events-kids/"
AJAX_URL = "https://triangleonthecheap.com/wordpress/wp-admin/admin-ajax.php"
TIMEZONE = "America/New_York"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


def fold_line(line: str) -> str:
    """Folds lines to <= 75 octets per RFC 5545."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line + "\r\n"
    chunks = []
    curr = bytearray()
    max_len = 75
    for b in encoded:
        if len(curr) >= max_len:
            chunks.append(curr.decode("utf-8", errors="ignore"))
            curr = bytearray(b" " + bytes([b]))
            max_len = 74
        else:
            curr.append(b)
    if curr:
        chunks.append(curr.decode("utf-8", errors="ignore"))
    return "\r\n".join(chunks) + "\r\n"


def escape_ics(text: str) -> str:
    """Escapes special characters for iCalendar fields."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    return text


def clean_html(text: str) -> str:
    """Strips HTML tags and unescapes entities."""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_time(time_str: str) -> Optional[time]:
    """Parses standard clock strings like '9:30 am' or '5 pm'."""
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", time_str.strip().lower())
    if not m:
        return None
    hr, mn, meridiem = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if meridiem == "pm" and hr != 12:
        hr += 12
    elif meridiem == "am" and hr == 12:
        hr = 0
    return time(hr, mn) if 0 <= hr <= 23 and 0 <= mn <= 59 else None


def parse_time_range(time_text: str, ev_date: date) -> Tuple[Optional[datetime], Optional[datetime], bool]:
    """Extracts start and end datetimes or marks as all-day event."""
    t_lower = time_text.strip().lower()
    if not t_lower or "all day" in t_lower:
        return None, None, True

    parts = re.split(r"\s+(?:to|until|-|–|—)\s+", time_text.strip(), flags=re.I)
    if len(parts) >= 2:
        start_raw, end_raw = parts[0].strip(), parts[1].strip()
        if not re.search(r"[ap]m", start_raw, re.I) and re.search(r"([ap]m)", end_raw, re.I):
            end_match = re.search(r"([ap]m)", end_raw, re.I)
            if end_match:
                start_raw += f" {end_match.group(1)}"
        st, et = parse_time(start_raw), parse_time(end_raw)
        if st and et:
            if st.hour in range(7, 13) and et.hour in range(1, 7) and "am" in end_raw.lower():
                et = time(et.hour + 12, et.minute)
            s_dt = datetime.combine(ev_date, st)
            e_dt = datetime.combine(ev_date, et)
            if e_dt <= s_dt:
                e_dt = s_dt + timedelta(hours=2)
            return s_dt, e_dt, False
        if st:
            s_dt = datetime.combine(ev_date, st)
            return s_dt, s_dt + timedelta(hours=1), False
    elif len(parts) == 1:
        st = parse_time(parts[0])
        if st:
            s_dt = datetime.combine(ev_date, st)
            return s_dt, s_dt + timedelta(hours=1), False

    return None, None, True


def http_get(url: str) -> str:
    """Performs HTTP GET request with standard headers."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_post(url: str, form_data: dict, referer: str) -> str:
    """Performs HTTP POST request for AJAX endpoints."""
    data = urllib.parse.urlencode(form_data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": referer,
        }
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def scrape_events() -> List[Dict[str, Any]]:
    """Scrapes upcoming kid events from Triangle on the Cheap."""
    print(f"Fetching events from: {TARGET_URL}")
    page_html = http_get(TARGET_URL)

    # Find day list containers
    containers = []
    div_matches = re.findall(r'<div[^>]*class=[\'"][^\'"]*lotc-event-list[^\'"]*[\'"][^>]*>', page_html)
    for tag in div_matches:
        cls_m = re.search(r'data-class=[\'"]([^\'"]+)[\'"]', tag)
        dt_m = re.search(r'data-date=[\'"]([^\'"]+)[\'"]', tag)
        cat_m = re.search(r'data-category=[\'"]([^\'"]+)[\'"]', tag)
        limit_m = re.search(r'data-limit=[\'"]([^\'"]+)[\'"]', tag)
        if cls_m and dt_m:
            containers.append({
                "class": cls_m.group(1),
                "date": dt_m.group(1),
                "format": "list",
                "category": cat_m.group(1) if cat_m else "3",
                "limit": limit_m.group(1) if limit_m else "999",
                "settings": {
                    "_date": dt_m.group(1),
                    "_category": cat_m.group(1) if cat_m else "3",
                    "_format": "list",
                    "_limit": limit_m.group(1) if limit_m else "999",
                }
            })

    if not containers:
        print("Warning: No day containers found.")
        return []

    print(f"Found {len(containers)} calendar days. Requesting events...")
    day_results: Dict[str, str] = {}

    # Attempt multi-day batch request
    try:
        raw_res = http_post(AJAX_URL, {"action": "load_multi_days", "requests": json.dumps(containers)}, TARGET_URL)
        parsed = json.loads(raw_res)
        if parsed.get("success") and "data" in parsed and "results" in parsed["data"]:
            day_results = parsed["data"]["results"]
    except Exception as e:
        print(f"Batch request failed ({e}), falling back to single-day queries...")

    # Fallback to single day if needed
    if not day_results:
        for c in containers:
            try:
                res = http_post(AJAX_URL, {
                    "action": "load_single_day",
                    "class": c["class"],
                    "date": c["date"],
                    "category": c.get("category", "3"),
                    "format": "list",
                    "limit": "999"
                }, TARGET_URL)
                day_results[c["class"]] = res
            except Exception:
                pass

    # Parse event entries from HTML
    events: List[Dict[str, Any]] = []
    seen = set()

    for c in containers:
        cls_name = c["class"]
        date_str = c["date"]
        try:
            ev_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue

        html_chunk = day_results.get(cls_name, "")
        if not html_chunk:
            continue

        row_blocks = re.findall(r'<div[^>]*class=[\'"][^\'"]*lotc-v2[^\'"]*event[^\'"]*[\'"][\s\S]*?</div>\s*</div>', html_chunk)
        for row in row_blocks:
            # Extract title & url
            title, url = "", ""
            link_m = re.search(r'<h3[^>]*>\s*<a[^>]*href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>\s*</h3>', row, re.DOTALL)
            if link_m:
                url = link_m.group(1).strip()
                title = clean_html(link_m.group(2))
            else:
                h3_m = re.search(r'<h3[^>]*>(.*?)</h3>', row, re.DOTALL)
                if h3_m:
                    title = clean_html(h3_m.group(1))

            if not title:
                continue

            # Extract meta: time, cost, location
            meta_m = re.search(r'<p class=[\'"]meta[\'"]>(.*?)</p>', row, re.DOTALL)
            time_str, cost_str, loc_str = "", "", ""
            if meta_m:
                parts = [p.strip() for p in clean_html(meta_m.group(1)).split("|") if p.strip()]
                if len(parts) == 1:
                    if re.search(r"(?:am|pm|all day|\d:\d\d)", parts[0], re.I):
                        time_str = parts[0]
                    else:
                        loc_str = parts[0]
                elif len(parts) == 2:
                    if re.search(r"(?:am|pm|all day|\d:\d\d)", parts[0], re.I):
                        time_str, loc_str = parts[0], parts[1]
                    else:
                        cost_str, loc_str = parts[0], parts[1]
                elif len(parts) >= 3:
                    time_str = parts[0]
                    cost_str = parts[1]
                    loc_str = ", ".join(parts[2:])

            # Deduplicate
            fingerprint = (date_str, title, time_str, loc_str)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)

            # Generate unique deterministic UID
            uid_key = f"{date_str}_{time_str}_{loc_str}_{title}_{url}"
            uid = hashlib.sha256(uid_key.encode("utf-8")).hexdigest()[:24] + "@triangleonthecheap.com"

            start_dt, end_dt, is_all_day = parse_time_range(time_str, ev_date)

            events.append({
                "uid": uid,
                "title": title,
                "url": url,
                "date": ev_date,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "is_all_day": is_all_day,
                "time_str": time_str,
                "cost": cost_str,
                "location": loc_str,
            })

    return events


def generate_ics(events: List[Dict[str, Any]]) -> str:
    """Generates RFC 5545 iCalendar content compatible with Google Calendar."""
    now_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Triangle on the Cheap//Kids Events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Triangle Kids Events",
        f"X-WR-TIMEZONE:{TIMEZONE}",
        "X-WR-CALDESC:Free and cheap kids events from Triangle on the Cheap",
        "BEGIN:VTIMEZONE",
        f"TZID:{TIMEZONE}",
        f"X-LIC-LOCATION:{TIMEZONE}",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:-0500",
        "TZOFFSETTO:-0400",
        "TZNAME:EDT",
        "DTSTART:19700308T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:-0400",
        "TZOFFSETTO:-0500",
        "TZNAME:EST",
        "DTSTART:19701101T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]

    out = "".join(fold_line(l) for l in lines)

    for ev in events:
        ev_lines = [
            "BEGIN:VEVENT",
            f"UID:{ev['uid']}",
            f"DTSTAMP:{now_stamp}",
            f"SUMMARY:{escape_ics(ev['title'])}",
        ]

        if ev["is_all_day"]:
            d_str = ev["date"].strftime("%Y%m%d")
            next_d = (ev["date"] + timedelta(days=1)).strftime("%Y%m%d")
            ev_lines.append(f"DTSTART;VALUE=DATE:{d_str}")
            ev_lines.append(f"DTEND;VALUE=DATE:{next_d}")
        else:
            s_str = ev["start_dt"].strftime("%Y%m%dT%H%M%S")
            e_str = ev["end_dt"].strftime("%Y%m%dT%H%M%S")
            ev_lines.append(f"DTSTART;TZID={TIMEZONE}:{s_str}")
            ev_lines.append(f"DTEND;TZID={TIMEZONE}:{e_str}")

        # Assemble event description
        details = []
        if ev["cost"]:
            details.append(f"Cost: {ev['cost']}")
        if ev["time_str"]:
            details.append(f"Time: {ev['time_str']}")
        if ev["location"]:
            details.append(f"Location: {ev['location']}")
        if ev["url"]:
            details.append(f"Info: {ev['url']}")
        details.append("Source: Triangle on the Cheap")

        desc = "\\n".join(escape_ics(d) for d in details)
        ev_lines.append(f"DESCRIPTION:{desc}")

        if ev["location"]:
            ev_lines.append(f"LOCATION:{escape_ics(ev['location'])}")
        if ev["url"]:
            ev_lines.append(f"URL:{escape_ics(ev['url'])}")

        ev_lines.append("STATUS:CONFIRMED")
        ev_lines.append("END:VEVENT")

        out += "".join(fold_line(l) for l in ev_lines)

    out += fold_line("END:VCALENDAR")
    return out


def main():
    out_file = sys.argv[1] if len(sys.argv) > 1 else "kids_events.ics"
    events = scrape_events()
    print(f"Successfully parsed {len(events)} kid events.")

    ics_text = generate_ics(events)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(ics_text)

    # Also write to public/kids_events.ics if directory exists (for local preview/download)
    if os.path.isdir("public"):
        with open("public/kids_events.ics", "w", encoding="utf-8") as f:
            f.write(ics_text)

    size = os.path.getsize(out_file)
    print(f"Saved {size} bytes to '{out_file}'. Ready to import into Google Calendar!")


if __name__ == "__main__":
    main()
