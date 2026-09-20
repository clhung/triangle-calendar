#!/usr/bin/env python3
"""
sync_events.py - Triangle on the Cheap Kids Events Scraper & ICS Generator

Scrapes upcoming free and cheap kids events from:
https://triangleonthecheap.com/free-cheap-events-kids/
and outputs an RFC 5545-compliant .ics (iCalendar) calendar file.

Security & Environment:
- Uses only Python standard library (zero mandatory external dependencies).
- Reads sensitive settings or overrides strictly from environment variables
  or CLI flags; never exposes credentials.
- Can be run standalone or automated via GitHub Actions.
"""

import os
import sys
import re
import json
import html
import hashlib
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional, Tuple

USER_AGENT = os.environ.get(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 (KidsEventsCalendarSync/1.0)"
)
DEFAULT_URL = "https://triangleonthecheap.com/free-cheap-events-kids/"
AJAX_URL = "https://triangleonthecheap.com/wordpress/wp-admin/admin-ajax.php"
TIMEZONE_NAME = "America/New_York"


def fold_ics_line(line: str) -> str:
    """
    Folds an iCalendar line according to RFC 5545 (section 3.1).
    Lines of text SHOULD NOT be longer than 75 octets, excluding the CRLF.
    Continuation lines begin with a space.
    """
    # Work in UTF-8 bytes to properly calculate octet lengths
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line + "\r\n"

    chunks = []
    current = bytearray()
    max_len = 75

    for byte in encoded:
        if len(current) >= max_len:
            chunks.append(current.decode("utf-8", errors="ignore"))
            current = bytearray(b" " + bytes([byte]))
            max_len = 74  # Subsequent lines have a leading space, so 74 payload bytes
        else:
            current.append(byte)

    if current:
        chunks.append(current.decode("utf-8", errors="ignore"))

    return "\r\n".join(chunks) + "\r\n"


def escape_ics_text(text: str) -> str:
    """
    Escapes special characters in text values according to RFC 5545:
    Backslash (\) -> \\
    Semicolon (;) -> \;
    Comma (,)     -> \,
    Newline (\n)  -> \n
    """
    if not text:
        return ""
    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Escape backslashes first
    text = text.replace("\\", "\\\\")
    # Escape semicolons and commas
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    # Escape newlines
    text = text.replace("\n", "\\n")
    return text


def clean_html_text(text: str) -> str:
    """Removes HTML tags and unescapes HTML entities."""
    if not text:
        return ""
    # Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", text)
    # Unescape HTML entities (e.g., &#8217; -> ', &amp; -> &)
    cleaned = html.unescape(cleaned)
    # Collapse multiple whitespace characters into single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def parse_time_component(time_str: str) -> Optional[time]:
    """Parses time strings like '9:00 am', '5:30 pm', '12:00 pm', '7 pm'."""
    s = time_str.strip().lower()
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", s)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    meridiem = m.group(3)

    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def parse_event_time_range(time_text: str, event_date: date) -> Tuple[Optional[datetime], Optional[datetime], bool]:
    """
    Parses a time string from event meta, such as:
    - '9:00 am to 5:00 pm'
    - '12:00 pm - 4:00 pm'
    - '10:00 am to 12:00 pm'
    - 'All day'
    - '2:00 pm'
    Returns (start_dt, end_dt, is_all_day).
    """
    t_lower = time_text.strip().lower()
    if not t_lower or "all day" in t_lower:
        return (None, None, True)

    # Normalize delimiters: 'to', '-', '–', '—', 'until'
    split_pattern = r"\s+(?:to|until|-|–|—)\s+"
    parts = re.split(split_pattern, time_text.strip(), flags=re.IGNORECASE)

    if len(parts) >= 2:
        start_raw = parts[0].strip()
        end_raw = parts[1].strip()

        # If start_raw is missing am/pm but end_raw has it (e.g. "9 to 11 am")
        if not re.search(r"[ap]m", start_raw, re.I) and re.search(r"([ap]m)", end_raw, re.I):
            end_match = re.search(r"([ap]m)", end_raw, re.I)
            if end_match:
                start_raw += f" {end_match.group(1)}"

        start_t = parse_time_component(start_raw)
        end_t = parse_time_component(end_raw)

        if start_t and end_t:
            # Handle possible website typos like "9:00 am to 5:00 am" (meant 5:00 pm)
            if start_t.hour in range(7, 13) and end_t.hour in range(1, 7) and "am" in end_raw.lower():
                end_t = time(end_t.hour + 12, end_t.minute)

            start_dt = datetime.combine(event_date, start_t)
            end_dt = datetime.combine(event_date, end_t)
            if end_dt <= start_dt:
                # If it spans past midnight or still earlier, default end to start + 2 hours
                end_dt = start_dt + timedelta(hours=2)
            return (start_dt, end_dt, False)

        elif start_t:
            start_dt = datetime.combine(event_date, start_t)
            return (start_dt, start_dt + timedelta(hours=1), False)

    elif len(parts) == 1:
        start_t = parse_time_component(parts[0])
        if start_t:
            start_dt = datetime.combine(event_date, start_t)
            return (start_dt, start_dt + timedelta(hours=1), False)

    return (None, None, True)


def parse_meta_line(meta_raw: str) -> Dict[str, str]:
    """
    Parses the '<p class="meta">...' line from LOTC event HTML.
    Example formats:
    - '9:00 am to 5:00 pm | $0-12.00 | Koka Booth Amphitheatre'
    - '12:00 pm to 4:00 pm | <strong>FREE</strong> | Downtown Durham'
    - '1:00 pm to 4:00 pm | For Garden&#8217;s Sake, Durham'
    """
    cleaned = clean_html_text(meta_raw)
    parts = [p.strip() for p in cleaned.split("|") if p.strip()]

    result = {
        "time": "",
        "cost": "",
        "location": "",
        "raw": cleaned
    }

    if not parts:
        return result

    if len(parts) == 1:
        # Check if it looks like a time, price, or location
        part = parts[0]
        if re.search(r"(?:am|pm|all day|\d:\d\d)", part, re.I):
            result["time"] = part
        else:
            result["location"] = part
    elif len(parts) == 2:
        part0, part1 = parts[0], parts[1]
        if re.search(r"(?:am|pm|all day|\d:\d\d)", part0, re.I):
            result["time"] = part0
            # Check whether part1 is a cost or location
            if re.search(r"^(?:free|\$|donation)", part1, re.I):
                result["cost"] = part1
            else:
                result["location"] = part1
        else:
            result["cost"] = part0
            result["location"] = part1
    else:
        # 3 or more parts
        result["time"] = parts[0]
        result["cost"] = parts[1]
        result["location"] = ", ".join(parts[2:])

    return result


def fetch_url(url: str, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 25) -> str:
    """Safe HTTP GET/POST with custom headers and timeout."""
    default_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        default_headers.update(headers)

    req = urllib.request.Request(url, data=data, headers=default_headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def get_event_day_containers(html_content: str) -> List[Dict[str, str]]:
    """
    Extracts all .lotc-event-list container metadata from the kid events page.
    """
    containers = []
    div_matches = re.findall(r'<div[^>]*class=[\'"][^\'"]*lotc-event-list[^\'"]*[\'"][^>]*>', html_content)

    for div_tag in div_matches:
        cls_m = re.search(r'data-class=[\'"]([^\'"]+)[\'"]', div_tag)
        dt_m = re.search(r'data-date=[\'"]([^\'"]+)[\'"]', div_tag)
        cat_m = re.search(r'data-category=[\'"]([^\'"]+)[\'"]', div_tag)
        limit_m = re.search(r'data-limit=[\'"]([^\'"]+)[\'"]', div_tag)

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

    return containers


def fetch_events_for_containers(containers: List[Dict[str, str]], verbose: bool = False) -> Dict[str, str]:
    """
    Fetches event HTML from LOTC admin-ajax.php using load_multi_days batching,
    with graceful fallback to load_single_day if batching fails.
    """
    if not containers:
        return {}

    # Attempt load_multi_days batch request
    try:
        if verbose:
            print(f"[*] Requesting multi-day batch for {len(containers)} dates...")

        post_data = urllib.parse.urlencode({
            "action": "load_multi_days",
            "requests": json.dumps(containers)
        }).encode("utf-8")

        response_json = fetch_url(
            AJAX_URL,
            data=post_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": DEFAULT_URL,
            },
            timeout=30
        )
        parsed = json.loads(response_json)
        if parsed.get("success") and "data" in parsed and "results" in parsed["data"]:
            results = parsed["data"]["results"]
            if verbose:
                print(f"[+] Multi-day batch returned results for {len(results)} date buckets.")
            return results
    except Exception as e:
        if verbose:
            print(f"[!] Batch fetch failed ({e}); falling back to single-day requests...")

    # Fallback to single-day requests
    results = {}
    for c in containers:
        cls_name = c["class"]
        date_val = c["date"]
        try:
            post_data = urllib.parse.urlencode({
                "action": "load_single_day",
                "class": cls_name,
                "date": date_val,
                "category": c.get("category", "3"),
                "format": "list",
                "limit": "999"
            }).encode("utf-8")

            html_res = fetch_url(
                AJAX_URL,
                data=post_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": DEFAULT_URL,
                },
                timeout=15
            )
            if html_res:
                results[cls_name] = html_res
        except Exception as single_err:
            if verbose:
                print(f"[!] Error fetching day {date_val}: {single_err}")

    return results


def parse_events_from_html(day_html: str, target_date: date) -> List[Dict[str, Any]]:
    """
    Parses event rows from the returned HTML snippet for a specific day.
    """
    events = []
    # Find all event row blocks: <div class="lotc-v2 row event">...</div>
    row_blocks = re.findall(
        r'<div[^>]*class=[\'"][^\'"]*lotc-v2[^\'"]*event[^\'"]*[\'"][\s\S]*?</div>\s*</div>',
        day_html
    )

    for row in row_blocks:
        # Title and URL
        title = ""
        url = ""
        link_m = re.search(r'<h3[^>]*>\s*<a[^>]*href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>\s*</h3>', row, re.DOTALL)
        if link_m:
            url = link_m.group(1).strip()
            title = clean_html_text(link_m.group(2))
        else:
            h3_m = re.search(r'<h3[^>]*>(.*?)</h3>', row, re.DOTALL)
            if h3_m:
                title = clean_html_text(h3_m.group(1))

        if not title:
            continue

        # Meta paragraph: time, cost, location
        meta_m = re.search(r'<p class=[\'"]meta[\'"]>(.*?)</p>', row, re.DOTALL)
        meta_parsed = parse_meta_line(meta_m.group(1)) if meta_m else {"time": "", "cost": "", "location": "", "raw": ""}

        time_str = meta_parsed["time"]
        cost_str = meta_parsed["cost"]
        location_str = meta_parsed["location"]

        start_dt, end_dt, is_all_day = parse_event_time_range(time_str, target_date)

        # Generate a deterministic UID so re-importing the .ics doesn't duplicate events
        uid_base = f"{target_date.isoformat()}_{title}_{url}"
        uid = hashlib.sha256(uid_base.encode("utf-8")).hexdigest()[:24] + "@triangleonthecheap.com"

        events.append({
            "uid": uid,
            "title": title,
            "url": url,
            "date": target_date,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "is_all_day": is_all_day,
            "time_str": time_str,
            "cost": cost_str,
            "location": location_str,
            "raw_meta": meta_parsed["raw"],
        })

    return events


def generate_vcalendar(events: List[Dict[str, Any]], calendar_name: str = "Triangle Free & Cheap Kids Events") -> str:
    """
    Generates a complete, standard RFC 5545 iCalendar (.ics) string.
    Includes proper VTIMEZONE block for America/New_York and folded lines.
    """
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # Timezone definition for America/New_York
    vtimezone = [
        "BEGIN:VTIMEZONE",
        f"TZID:{TIMEZONE_NAME}",
        f"X-LIC-LOCATION:{TIMEZONE_NAME}",
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

    header_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Triangle on the Cheap//Kids Events Calendar Sync//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics_text(calendar_name)}",
        f"X-WR-TIMEZONE:{TIMEZONE_NAME}",
        "X-WR-CALDESC:Free and cheap kids events in Raleigh, Durham, Chapel Hill & beyond from Triangle on the Cheap",
    ]

    ics_content = ""
    for hl in header_lines:
        ics_content += fold_ics_line(hl)

    for tzl in vtimezone:
        ics_content += fold_ics_line(tzl)

    for ev in events:
        vevent = [
            "BEGIN:VEVENT",
            f"UID:{ev['uid']}",
            f"DTSTAMP:{dtstamp}",
            f"SUMMARY:{escape_ics_text(ev['title'])}",
        ]

        if ev["is_all_day"]:
            date_str = ev["date"].strftime("%Y%m%d")
            next_day_str = (ev["date"] + timedelta(days=1)).strftime("%Y%m%d")
            vevent.append(f"DTSTART;VALUE=DATE:{date_str}")
            vevent.append(f"DTEND;VALUE=DATE:{next_day_str}")
        else:
            s_str = ev["start_dt"].strftime("%Y%m%dT%H%M%S")
            e_str = ev["end_dt"].strftime("%Y%m%dT%H%M%S")
            vevent.append(f"DTSTART;TZID={TIMEZONE_NAME}:{s_str}")
            vevent.append(f"DTEND;TZID={TIMEZONE_NAME}:{e_str}")

        # Description text assembling
        desc_parts = []
        if ev["cost"]:
            desc_parts.append(f"Cost: {ev['cost']}")
        if ev["time_str"]:
            desc_parts.append(f"Time: {ev['time_str']}")
        if ev["location"]:
            desc_parts.append(f"Location: {ev['location']}")
        if ev["url"]:
            desc_parts.append(f"More info: {ev['url']}")
        desc_parts.append("Source: Triangle on the Cheap (Kids Events)")

        description = "\\n".join([escape_ics_text(p) for p in desc_parts])
        vevent.append(f"DESCRIPTION:{description}")

        if ev["location"]:
            vevent.append(f"LOCATION:{escape_ics_text(ev['location'])}")

        if ev["url"]:
            vevent.append(f"URL:{escape_ics_text(ev['url'])}")

        vevent.append("CATEGORIES:Kids,Family,Community")
        vevent.append("STATUS:CONFIRMED")
        vevent.append("END:VEVENT")

        for vl in vevent:
            ics_content += fold_ics_line(vl)

    ics_content += fold_ics_line("END:VCALENDAR")
    return ics_content


def scrape_triangle_kid_events(url: str = DEFAULT_URL, max_days: Optional[int] = None, verbose: bool = False) -> List[Dict[str, Any]]:
    """
    Primary workflow function:
    1. Downloads main webpage.
    2. Identifies all day containers.
    3. Fetches event markup for each day via batch or single requests.
    4. Parses structured event records.
    """
    if verbose:
        print(f"[*] Fetching landing page: {url}")

    page_html = fetch_url(url)
    containers = get_event_day_containers(page_html)

    if not containers:
        if verbose:
            print("[!] No .lotc-event-list containers detected on page.")
        # Fallback: synthesize current and upcoming dates
        today = date.today()
        num_days = max_days or 30
        for offset in range(num_days):
            d = today + timedelta(days=offset)
            d_str = d.strftime("%Y-%m-%d")
            cls_name = f"event-day-{d.strftime('%Y%m%d')}-cat-3"
            containers.append({
                "class": cls_name,
                "date": d_str,
                "format": "list",
                "category": "3",
                "limit": "999",
                "settings": {"_date": d_str, "_category": "3", "_format": "list", "_limit": "999"}
            })

    if max_days and max_days > 0:
        containers = containers[:max_days]

    if verbose:
        print(f"[+] Found {len(containers)} calendar day slots to query.")

    results = fetch_events_for_containers(containers, verbose=verbose)

    all_events: List[Dict[str, Any]] = []
    for c in containers:
        cls_name = c["class"]
        date_str = c["date"]
        try:
            t_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            t_date = date.today()

        day_html = results.get(cls_name, "")
        if day_html:
            day_events = parse_events_from_html(day_html, t_date)
            all_events.extend(day_events)

    if verbose:
        print(f"[+] Total kid events successfully parsed: {len(all_events)}")

    return all_events


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Triangle on the Cheap Kid Events and generate a valid .ics calendar file."
    )
    parser.add_argument(
        "--output", "-o",
        default=os.environ.get("OUTPUT_FILE", "kids_events.ics"),
        help="Path to output .ics calendar file (default: kids_events.ics)"
    )
    parser.add_argument(
        "--url", "-u",
        default=os.environ.get("TARGET_URL", DEFAULT_URL),
        help=f"Target webpage URL (default: {DEFAULT_URL})"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=int(os.environ.get("DAYS_AHEAD", "30")),
        help="Maximum days ahead to query (default: 30)"
    )
    parser.add_argument(
        "--json-output",
        default=os.environ.get("JSON_OUTPUT_FILE", ""),
        help="Optional path to output raw parsed events as JSON"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=True,
        help="Display detailed progress and logs (default: True)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress informational console output"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and parse without writing output files to disk"
    )

    args = parser.parse_args()
    verbose = not args.quiet

    if verbose:
        print("=" * 60)
        print(" Triangle on the Cheap - Kids Event Calendar Sync")
        print("=" * 60)

    try:
        events = scrape_triangle_kid_events(url=args.url, max_days=args.days, verbose=verbose)

        if not events:
            if verbose:
                print("[!] Warning: 0 events extracted. Check site structure or connectivity.")

        ics_data = generate_vcalendar(events)

        if not args.dry_run:
            out_dir = os.path.dirname(args.output)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            with open(args.output, "w", encoding="utf-8") as f:
                f.write(ics_data)

            if verbose:
                file_size = os.path.getsize(args.output)
                print(f"[✓] Saved valid iCalendar (.ics) to: {args.output} ({file_size} bytes, {len(events)} events)")

            if args.json_output:
                json_dir = os.path.dirname(args.json_output)
                if json_dir:
                    os.makedirs(json_dir, exist_ok=True)

                # Prepare JSON-serializable list
                serializable_events = []
                for ev in events:
                    serializable_events.append({
                        "uid": ev["uid"],
                        "title": ev["title"],
                        "url": ev["url"],
                        "date": ev["date"].isoformat(),
                        "is_all_day": ev["is_all_day"],
                        "start_time": ev["start_dt"].strftime("%I:%M %p") if ev["start_dt"] else None,
                        "end_time": ev["end_dt"].strftime("%I:%M %p") if ev["end_dt"] else None,
                        "time_str": ev["time_str"],
                        "cost": ev["cost"],
                        "location": ev["location"],
                    })

                with open(args.json_output, "w", encoding="utf-8") as jf:
                    json.dump({
                        "generated_at": datetime.utcnow().isoformat() + "Z",
                        "event_count": len(serializable_events),
                        "events": serializable_events
                    }, jf, indent=2)

                if verbose:
                    print(f"[✓] Saved JSON event preview to: {args.json_output}")

        else:
            if verbose:
                print(f"[✓] Dry run complete. Parsed {len(events)} events. First 300 bytes of ICS:\n")
                print(ics_data[:300])

        return 0

    except Exception as e:
        sys.stderr.write(f"[ERROR] Sync failed: {e}\n")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
