#!/usr/bin/env python3
"""
sync_events.py
Barebone Python script to scrape Triangle on the Cheap kids events
and save to an RFC 5545 .ics calendar file readable by Google Calendar.

Supports:
- RSS Feed: https://triangleonthecheap.com/category/kids/feed/
- Structured Calendar API: load_multi_days via admin-ajax.php (category 3)

Requirements: Python 3.7+ (Standard Library only - zero pip dependencies)
Usage:
    python3 sync_events.py
    python3 sync_events.py kids_events.ics
"""

import sys
import os
import re
import html
import json
import hashlib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional, Tuple

# Primary endpoints
FEED_URL = "https://triangleonthecheap.com/category/kids/feed/"
AJAX_URL = "https://triangleonthecheap.com/wordpress/wp-admin/admin-ajax.php"
TIMEZONE = "America/New_York"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def fold_line(line: str) -> str:
    """Folds lines to <= 75 octets per RFC 5545 specification."""
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
    """Escapes special characters for iCalendar text fields."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    return text


def clean_html(text: str) -> str:
    """Strips HTML tags and decodes entities."""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_clock_time(time_str: str) -> Optional[time]:
    """Parses clock strings like '9:30 am', '5 pm', '11 a.m.'."""
    cleaned = re.sub(r"\.", "", time_str.strip().lower())
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", cleaned)
    if not m:
        return None
    hr = int(m.group(1))
    mn = int(m.group(2) or 0)
    meridiem = m.group(3)
    if meridiem == "pm" and hr != 12:
        hr += 12
    elif meridiem == "am" and hr == 12:
        hr = 0
    return time(hr, mn) if 0 <= hr <= 23 and 0 <= mn <= 59 else None


def parse_time_range(time_text: str, ev_date: date) -> Tuple[Optional[datetime], Optional[datetime], bool]:
    """Extracts start and end datetimes, or indicates an all-day event."""
    t_lower = time_text.strip().lower()
    if not t_lower or "all day" in t_lower:
        return None, None, True

    parts = re.split(r"\s+(?:to|until|-|–|—)\s+", time_text.strip(), flags=re.I)
    if len(parts) >= 2:
        start_raw, end_raw = parts[0].strip(), parts[1].strip()
        if not re.search(r"[ap]\.?m\.?", start_raw, re.I) and re.search(r"([ap]\.?m\.?)", end_raw, re.I):
            end_match = re.search(r"([ap]\.?m\.?)", end_raw, re.I)
            if end_match:
                start_raw += f" {end_match.group(1)}"
        st = parse_clock_time(start_raw)
        et = parse_clock_time(end_raw)
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
        st = parse_clock_time(parts[0])
        if st:
            s_dt = datetime.combine(ev_date, st)
            return s_dt, s_dt + timedelta(hours=1), False

    return None, None, True


def http_get(url: str, timeout: int = 30) -> str:
    """Performs HTTP GET with standard browser headers."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_post(url: str, form_data: dict, timeout: int = 30) -> str:
    """Performs HTTP POST for AJAX requests."""
    data = urllib.parse.urlencode(form_data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://triangleonthecheap.com/events/",
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_dates_from_text(title: str, text: str, reference_year: int) -> List[date]:
    """Finds calendar dates mentioned in event title or article text."""
    combined = f"{title} {text[:1500]}"
    pattern = r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?"
    matches = list(re.finditer(pattern, combined, re.I))
    results = []
    seen = set()
    for m in matches:
        month_str = m.group(1).lower()
        month = MONTH_MAP.get(month_str)
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else reference_year
        if month and 1 <= day <= 31:
            try:
                d = date(year, month, day)
                if d not in seen:
                    seen.add(d)
                    results.append(d)
            except ValueError:
                pass
    return results


def scrape_rss_feed(feed_url: str = FEED_URL) -> List[Dict[str, Any]]:
    """Scrapes events from the RSS category feed."""
    print(f"Fetching RSS feed from: {feed_url}")
    events: List[Dict[str, Any]] = []
    try:
        raw_xml = http_get(feed_url)
        root = ET.fromstring(raw_xml)
    except Exception as e:
        print(f"Warning: Failed to fetch or parse RSS feed: {e}")
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    items = channel.findall("item")
    print(f"Found {len(items)} items in RSS feed. Extracting event details...")

    today = date.today()
    current_year = today.year

    for item in items:
        title = clean_html(item.find("title").text or "")
        link = (item.find("link").text or "").strip()
        pub_date_raw = (item.find("pubDate").text or "").strip()

        # Skip the landing index page if present in feed
        if not title or "free-cheap-events-kids" in link:
            continue

        # Extract content
        encoded = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
        desc = item.find("description")
        content_html = encoded.text if (encoded is not None and encoded.text) else (desc.text if (desc is not None and desc.text) else "")
        clean_text = clean_html(content_html)

        # Extract dates
        dates = extract_dates_from_text(title, clean_text, current_year)
        if not dates:
            # Fallback to pubDate if no explicit event date in text
            try:
                # e.g., 'Fri, 25 Sep 2026 19:02:00 +0000'
                dt_pub = datetime.strptime(pub_date_raw[:16], "%a, %d %b %Y").date()
                dates = [dt_pub]
            except Exception:
                dates = [today]

        # Filter out dates that are more than 30 days in the past
        target_dates = [d for d in dates if d >= today - timedelta(days=30)]
        if not target_dates:
            target_dates = [dates[0]]

        # Extract time range: e.g., '11 a.m. to 2 p.m.' or '7 to 9 p.m.'
        time_str = ""
        time_m = re.search(
            r"(\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?\s*(?:to|-|–|—|until)\s*\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?))",
            clean_text[:2000],
            re.I
        )
        if time_m:
            time_str = time_m.group(1).strip()

        # Extract location: e.g., 'at Moore Square, 201 S Blount Street, Raleigh, North Carolina'
        loc_str = ""
        loc_m = re.search(r"\bat\s+([A-Z0-9][^,\.\n]+(?:,\s*[^,\.\n]+){1,3})", clean_text[:2000])
        if loc_m:
            loc_str = loc_m.group(1).strip()
            # Clean up trailing words like 'is hosting'
            loc_str = re.sub(r",?\s*(?:is hosting|hosts|will hold).*", "", loc_str, flags=re.I).strip()

        # Extract cost
        cost_str = ""
        cost_m = re.search(r"(\bfree\b|\$\d+(?:\.\d{2})?)", clean_text[:2000], re.I)
        if cost_m:
            c = cost_m.group(1)
            cost_str = "FREE" if c.lower() == "free" else c

        # Extract brief description
        snippet = clean_text[:400].strip()
        if len(clean_text) > 400:
            snippet += "..."

        for ev_date in target_dates[:3]:  # Limit multi-date series to first 3 dates
            start_dt, end_dt, is_all_day = parse_time_range(time_str, ev_date)
            uid_key = f"rss_{ev_date.strftime('%Y%m%d')}_{title}_{link}"
            uid = hashlib.sha256(uid_key.encode("utf-8")).hexdigest()[:24] + "@triangleonthecheap.com"

            events.append({
                "uid": uid,
                "title": title,
                "url": link,
                "date": ev_date,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "is_all_day": is_all_day,
                "time_str": time_str,
                "cost": cost_str,
                "location": loc_str,
                "description": snippet,
                "source": "rss",
            })

    return events


def scrape_calendar_api(days_ahead: int = 30) -> List[Dict[str, Any]]:
    """Directly queries the WordPress AJAX endpoint for kid events across date range."""
    print(f"Querying structured calendar API for the next {days_ahead} days...")
    today = date.today()
    containers = []
    for i in range(days_ahead):
        d = today + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        cls_name = f"lotc-day-{d_str}"
        containers.append({
            "class": cls_name,
            "date": d_str,
            "format": "list",
            "category": "3",  # Category 3 = Kids
            "limit": "999",
            "settings": {
                "_date": d_str,
                "_category": "3",
                "_format": "list",
                "_limit": "999",
            }
        })

    day_results: Dict[str, str] = {}
    try:
        raw_res = http_post(AJAX_URL, {"action": "load_multi_days", "requests": json.dumps(containers)})
        parsed = json.loads(raw_res)
        if parsed.get("success") and "data" in parsed and "results" in parsed["data"]:
            day_results = parsed["data"]["results"]
    except Exception as e:
        print(f"Warning: load_multi_days request failed: {e}")

    # Fallback to single day queries if batch failed
    if not day_results:
        for c in containers[:7]:
            try:
                res = http_post(AJAX_URL, {
                    "action": "load_single_day",
                    "class": c["class"],
                    "date": c["date"],
                    "category": "3",
                    "format": "list",
                    "limit": "999"
                })
                day_results[c["class"]] = res
            except Exception:
                pass

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

            fp = (date_str, title.lower(), time_str)
            if fp in seen:
                continue
            seen.add(fp)

            uid_key = f"cal_{date_str}_{title}_{url}"
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
                "description": "",
                "source": "calendar_api",
            })

    return events


def merge_and_deduplicate(api_events: List[Dict[str, Any]], rss_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges events from both sources, giving calendar API precision priority while enriching descriptions from RSS."""
    merged: List[Dict[str, Any]] = []
    index_by_link: Dict[str, Dict[str, Any]] = {}
    index_by_title_date: Dict[Tuple[str, str], Dict[str, Any]] = {}

    # First add API events (highly accurate times and dates)
    for ev in api_events:
        clean_t = re.sub(r"[^a-z0-9]", "", ev["title"].lower())
        d_str = ev["date"].strftime("%Y-%m-%d")
        if ev["url"]:
            norm_url = ev["url"].rstrip("/").lower()
            index_by_link[norm_url] = ev
        index_by_title_date[(clean_t[:25], d_str)] = ev
        merged.append(ev)

    # Now merge RSS events
    rss_added = 0
    for ev in rss_events:
        norm_url = ev["url"].rstrip("/").lower() if ev["url"] else ""
        clean_t = re.sub(r"[^a-z0-9]", "", ev["title"].lower())
        d_str = ev["date"].strftime("%Y-%m-%d")

        existing = index_by_link.get(norm_url) or index_by_title_date.get((clean_t[:25], d_str))
        if existing:
            # Enrich existing event with RSS snippet or location if missing
            if not existing.get("description") and ev.get("description"):
                existing["description"] = ev["description"]
            if not existing.get("location") and ev.get("location"):
                existing["location"] = ev["location"]
            if not existing.get("cost") and ev.get("cost"):
                existing["cost"] = ev["cost"]
        else:
            merged.append(ev)
            if norm_url:
                index_by_link[norm_url] = ev
            index_by_title_date[(clean_t[:25], d_str)] = ev
            rss_added += 1

    print(f"Total merged events: {len(merged)} ({len(api_events)} from Calendar API + {rss_added} unique from RSS feed)")
    # Sort chronologically
    merged.sort(key=lambda x: (x["date"], x["start_dt"] or datetime.min))
    return merged


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
        if ev.get("cost"):
            details.append(f"Cost: {ev['cost']}")
        if ev.get("time_str"):
            details.append(f"Time: {ev['time_str']}")
        if ev.get("location"):
            details.append(f"Location: {ev['location']}")
        if ev.get("description"):
            details.append(f"Details: {ev['description']}")
        if ev.get("url"):
            details.append(f"Info: {ev['url']}")
        details.append("Source: Triangle on the Cheap (Kids)")

        desc = "\\n".join(escape_ics(d) for d in details)
        ev_lines.append(f"DESCRIPTION:{desc}")

        if ev.get("location"):
            ev_lines.append(f"LOCATION:{escape_ics(ev['location'])}")
        if ev.get("url"):
            ev_lines.append(f"URL:{escape_ics(ev['url'])}")

        ev_lines.append("STATUS:CONFIRMED")
        ev_lines.append("END:VEVENT")

        out += "".join(fold_line(l) for l in ev_lines)

    out += fold_line("END:VCALENDAR")
    return out


def main():
    out_file = sys.argv[1] if len(sys.argv) > 1 else "kids_events.ics"

    # 1. Fetch RSS feed (open, unblocked feed for category/kids/)
    rss_events = scrape_rss_feed(FEED_URL)

    # 2. Fetch structured calendar API (bypasses blocked webpage, queries category 3)
    api_events = scrape_calendar_api(days_ahead=30)

    # 3. Merge and deduplicate
    events = merge_and_deduplicate(api_events, rss_events)
    if not events:
        print("Error: No events could be retrieved from either RSS feed or Calendar API.")
        sys.exit(1)

    print(f"Successfully prepared {len(events)} kid events.")

    # 4. Generate RFC 5545 iCalendar format
    ics_text = generate_ics(events)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(ics_text)

    # Also sync to public/kids_events.ics if directory exists
    if os.path.isdir("public"):
        with open("public/kids_events.ics", "w", encoding="utf-8") as f:
            f.write(ics_text)

    size = os.path.getsize(out_file)
    print(f"Saved {size} bytes ({len(events)} events) to '{out_file}'. Ready to import into Google Calendar!")


if __name__ == "__main__":
    main()
