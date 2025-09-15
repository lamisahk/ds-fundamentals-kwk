import os, re, time, urllib.parse
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import requests
from bs4 import BeautifulSoup
from ics import Calendar

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FinalsICS-Appender/1.0)"}
TIMEOUT = 25
DELAY   = 1.5
MIN_YEAR = 2019
MAX_YEAR = date.today().year

DATA_RAW  = os.path.join(".", "data_raw")
os.makedirs(DATA_RAW, exist_ok=True)
FINALS_CSV = os.path.join(DATA_RAW, "finals_boston_universities.csv")

# >>> New set of Boston-area schools to try <<<
SCHOOLS = [
    {"school": "Suffolk University",          "start": "https://www.suffolk.edu/academics/academic-calendar"},
    {"school": "Emerson College",             "start": "https://emerson.edu/registrar/academic-calendar"},
    {"school": "Simmons University",          "start": "https://www.simmons.edu/academics/academic-calendar"},
    {"school": "Emmanuel College",            "start": "https://www.emmanuel.edu/academics/registrar/academic-calendar"},
    {"school": "Wentworth Institute of Tech", "start": "https://wit.edu/academics/academic-resources/academic-calendar"},
    {"school": "Berklee College of Music",    "start": "https://www.berklee.edu/registrar/academic-calendar"},
    {"school": "Lesley University",           "start": "https://lesley.edu/registrar/academic-calendar"},
    {"school": "MassArt",                     "start": "https://massart.edu/academic-calendar"},
    {"school": "Bentley University",          "start": "https://www.bentley.edu/offices/registrar/academic-calendars"},
    {"school": "Babson College",              "start": "https://www.babson.edu/academics/academic-calendar/"},
    {"school": "Brandeis University",         "start": "https://www.brandeis.edu/registrar/calendar/index.html"},
    # (Tufts/Harvard/MIT/BU/BC/Northeastern/UMass Boston were in earlier attempt)
]

FINAL_KEYS = re.compile(r"\b(final|finals|exam|examination)\b", re.I)

def get_html(url: str) -> Optional[str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"  ! HTTP {r.status_code} for {url}")
            return None
        return r.text
    except Exception as e:
        print(f"  ! Error fetching {url}: {e}")
        return None

def same_domain(base_url: str, link: str) -> bool:
    try:
        bu = urllib.parse.urlparse(base_url)
        lu = urllib.parse.urlparse(link)
        return (lu.netloc == "" or lu.netloc == bu.netloc)
    except Exception:
        return False

def discover_ics_links(start_url: str, max_links: int = 10) -> List[str]:
    """Find .ics links on the page and a few same-domain 'calendar-like' subpages."""
    html = get_html(start_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urllib.parse.urljoin(start_url, href)
        links.append(full)


    ics_links = [u for u in links if u.lower().endswith(".ics") and same_domain(start_url, u)]
    if ics_links:
        return list(dict.fromkeys(ics_links))[:max_links]

    looks_calendar = re.compile(r"(calendar|academic|schedule|dates|exam|final|registrar)", re.I)
    subpages = [u for u in links if same_domain(start_url, u) and looks_calendar.search(u)]
    subpages = list(dict.fromkeys(subpages))[:max_links]

    found = []
    for sp in subpages:
        time.sleep(DELAY)
        html2 = get_html(sp)
        if not html2:
            continue
        soup2 = BeautifulSoup(html2, "lxml")
        for a in soup2.find_all("a", href=True):
            href2 = a["href"].strip()
            full2 = urllib.parse.urljoin(sp, href2)
            if full2.lower().endswith(".ics") and same_domain(start_url, full2):
                found.append(full2)

    return list(dict.fromkeys(found))[:max_links]

def parse_ics(url: str) -> List[Dict]:
    """Return flat list of events: title, description, start, end, source_url"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"    ! HTTP {r.status_code} for ICS {url}")
            return []
        cal = Calendar(r.text)
        out = []
        for ev in cal.events:
            if not ev.begin or not ev.end:
                continue
            start = ev.begin.date()
            end_exclusive = ev.end.date()
            # normalize to inclusive end
            end = end_exclusive - timedelta(days=1)
            out.append({
                "title": (ev.name or "").strip(),
                "description": (ev.description or "").strip(),
                "start": start,
                "end": end,
                "source_url": url
            })
        return out
    except Exception as e:
        print(f"    ! Error parsing ICS {url}: {e}")
        return []

def guess_term(month: int) -> str:
    if month in (4,5,6):  return "Spring"
    if month in (11,12):  return "Fall"
    return "Unknown"

def finals_from_events(events: List[Dict]) -> List[Dict]:
    rows = []
    for ev in events:
        s, e = ev["start"], ev["end"]
        if not (MIN_YEAR <= s.year <= MAX_YEAR or MIN_YEAR <= e.year <= MAX_YEAR):
            continue
        text = f"{ev['title']} {ev['description']}"
        if not FINAL_KEYS.search(text):
            continue
        if e < s:
            s, e = e, s
        rows.append({"start": s, "end": e, "source_url": ev["source_url"]})
    # dedupe
    dedup = {(r["start"], r["end"], r["source_url"]) for r in rows}
    return [{"start": s, "end": e, "source_url": u} for (s,e,u) in sorted(dedup)]

def load_existing() -> pd.DataFrame:
    if os.path.exists(FINALS_CSV):
        df = pd.read_csv(FINALS_CSV)
        # normalize dtypes if present
        for c in ["finals_start","finals_end"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c]).dt.date
        return df
    else:
        return pd.DataFrame(columns=["school","term","year","finals_start","finals_end","source_url"])

def backup_existing():
    if os.path.exists(FINALS_CSV):
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = FINALS_CSV.replace(".csv", f".backup-{ts}.csv")
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        pd.read_csv(FINALS_CSV).to_csv(backup, index=False)
        print(f"Backed up existing CSV → {backup}")

def main():
    print("Loading existing finals CSV (if any)…")
    existing = load_existing()

    backup_existing()

    new_rows = []
    print("\nDiscovering .ics feeds for additional Boston-area schools…")
    for item in SCHOOLS:
        school = item["school"]
        start  = item["start"]
        print(f"\n{school} → {start}")
        time.sleep(DELAY)
        ics_links = discover_ics_links(start)
        if not ics_links:
            print("  (no ICS links found)")
            continue
        for ics in ics_links:
            print(f"  ICS: {ics}")
            time.sleep(DELAY)
            events = parse_ics(ics)
            finals = finals_from_events(events)
            if not finals:
                print("    (no finals-like events in this ICS)")
                continue
            for w in finals:
                term = guess_term(w["start"].month)
                new_rows.append({
                    "school": school,
                    "term": term,
                    "year": w["start"].year,
                    "finals_start": w["start"],
                    "finals_end": w["end"],
                    "source_url": w["source_url"]
                })

    add_df = pd.DataFrame(new_rows)
    if add_df.empty:
        print("\nNo new finals rows discovered from these schools.")

        if not existing.empty:
            existing.to_csv(FINALS_CSV, index=False)
            print(f"Re-saved existing CSV → {FINALS_CSV} (rows={len(existing)})")
        else:

            empty = pd.DataFrame(columns=["school","term","year","finals_start","finals_end","source_url"])
            empty.to_csv(FINALS_CSV, index=False)
            print(f"Created empty finals CSV with headers → {FINALS_CSV}")
        return


    for c in ["finals_start","finals_end"]:
        add_df[c] = pd.to_datetime(add_df[c]).dt.date
        if c in existing.columns:
            existing[c] = pd.to_datetime(existing[c]).dt.date

    combined = pd.concat([existing, add_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["school","finals_start","finals_end"]).sort_values(
        ["school","year","finals_start"]
    )

    # Save
    combined.to_csv(FINALS_CSV, index=False)
    print(f"\n✅ Appended finals CSV → {FINALS_CSV} (rows={len(combined)})")
    # Show what was added
    new_only = pd.merge(add_df, existing, on=["school","finals_start","finals_end"], how="left", indicator=True)
    new_only = new_only[new_only["_merge"] == "left_only"].drop(columns=["_merge"])
    if not new_only.empty:
        print("\nNew rows added (sample):")
        print(new_only.head(10).to_string(index=False))
    else:
        print("\n(Note: all discovered rows were already present.)")

if __name__ == "__main__":
    main()
