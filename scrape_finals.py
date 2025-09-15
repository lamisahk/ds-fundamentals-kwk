import os, re, time, urllib.parse
from datetime import date, timedelta
from typing import List, Dict, Optional, Set
import requests
import pandas as pd
from bs4 import BeautifulSoup
from ics import Calendar
from pytrends.request import TrendReq

# ------------------- SETTINGS -------------------
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FinalsICS/1.0)"}
TIMEOUT = 25
DELAY   = 1.5
MIN_YEAR = 2019
MAX_YEAR = date.today().year

PROJECT_ROOT = "."
DATA_RAW  = os.path.join(PROJECT_ROOT, "data_raw")
DATA_OUT  = os.path.join(PROJECT_ROOT, "data_derived")
os.makedirs(DATA_RAW, exist_ok=True)
os.makedirs(DATA_OUT, exist_ok=True)

# Schools + starting calendar pages 
SCHOOLS = [
    {"school": "Harvard",           "start": "https://registrar.fas.harvard.edu/academic-calendar"},
    {"school": "MIT",               "start": "https://registrar.mit.edu/calendar"},
    {"school": "Boston University", "start": "https://www.bu.edu/reg/administrative/calendar/"},
    {"school": "Northeastern",      "start": "https://registrar.northeastern.edu/article/academic-calendar/"},
    {"school": "Boston College",    "start": "https://www.bc.edu/bc-web/offices/student-services/academic-services/academic-calendars.html"},
    {"school": "UMass Boston",      "start": "https://www.umb.edu/registrar/academic-calendar/"},
    {"school": "Tufts",             "start": "https://students.tufts.edu/registrar/calendars"},
]

FINAL_KEYS = re.compile(r"\b(final|finals|exam|examination)\b", re.I)

KEYWORDS = ["pizza near me", "coffee near me"]   
GEO = "US-MA"
TIMEFRAME = f"2019-01-01 {date.today().isoformat()}"

# ------------------- HELPERS -------------------
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

def discover_ics_links(start_url: str, max_links: int = 8) -> List[str]:
    """Find .ics links on the page and immediate same-domain pages that look like calendars."""
    html = get_html(start_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")

    # Collect candidate links on the start page
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urllib.parse.urljoin(start_url, href)
        links.append(full)

    # Filter any direct .ics links
    ics_links = [u for u in links if u.lower().endswith(".ics") and same_domain(start_url, u)]
    if ics_links:
        return list(dict.fromkeys(ics_links))[:max_links]

    # If none, follow a few same-domain "calendar-y" pages and look there for .ics
    looks_calendar = re.compile(r"(calendar|academic|schedule|dates|exam|final)", re.I)
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
    """Return list of events (title, description, start_date, end_date, source_url)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"    ! HTTP {r.status_code} for ICS {url}")
            return []
        cal = Calendar(r.text)
        out = []
        for ev in cal.events:
            # Event times: ics uses inclusive start, exclusive end for all-day
            start = ev.begin.date() if hasattr(ev.begin, "date") else None
            end   = ev.end.date()   if hasattr(ev.end, "date")   else None
            if not start or not end:
                continue
            # Normalize to inclusive end date
            end_inclusive = end - timedelta(days=1)
            title = (ev.name or "").strip()
            desc  = (ev.description or "").strip()
            out.append({
                "title": title,
                "description": desc,
                "start": start,
                "end": end_inclusive,
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
        if not (MIN_YEAR <= ev["start"].year <= MAX_YEAR or MIN_YEAR <= ev["end"].year <= MAX_YEAR):
            continue
        text = f"{ev['title']} {ev['description']}"
        if not FINAL_KEYS.search(text):
            continue
        s, e = ev["start"], ev["end"]
        if e < s:
            s, e = e, s
        rows.append({"start": s, "end": e, "source_url": ev["source_url"]})
    # de-dup
    dedup = {(r["start"], r["end"], r["source_url"]) for r in rows}
    return [{"start": s, "end": e, "source_url": u} for (s,e,u) in sorted(dedup)]

def build_finals_csv() -> pd.DataFrame:
    all_rows = []
    print("Discovering .ics feeds and extracting finals…")
    for item in SCHOOLS:
        school, start = item["school"], item["start"]
        print(f"\n{school} → {start}")
        time.sleep(DELAY)
        ics_links = discover_ics_links(start)
        if not ics_links:
            print("  (no ICS links found on initial pages)")
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
                all_rows.append({
                    "school": school,
                    "term": term,
                    "year": w["start"].year,
                    "finals_start": w["start"].isoformat(),
                    "finals_end": w["end"].isoformat(),
                    "source_url": w["source_url"]
                })

    df = pd.DataFrame(all_rows)
    if df.empty:
        # create empty with headers for downstream compatibility
        df = pd.DataFrame(columns=["school","term","year","finals_start","finals_end","source_url"])
    else:
        df = df.drop_duplicates(subset=["school","finals_start","finals_end"]).sort_values(
            ["school","year","finals_start"]
        )
    out = os.path.join(DATA_RAW, "finals_boston_universities.csv")
    df.to_csv(out, index=False)
    print(f"\nSaved finals → {out} (rows={len(df)})")
    return df

# ---------- google Trends + merge  ----------
def get_trends(keywords, geo, timeframe):
    pytrends = TrendReq(hl="en-US", tz=0)
    all_df = None
    for kw in keywords:
        pytrends.build_payload([kw], timeframe=timeframe, geo=geo, cat=0, gprop="")
        df = pytrends.interest_over_time().reset_index()
        if df.empty:
            raise RuntimeError(f"Empty Trends for '{kw}'. Try broader geo/shorter timeframe.")
        col = kw.replace(" ", "_")
        df = df.rename(columns={"date": "date", kw: col})
        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[["date", col]]
        all_df = df if all_df is None else pd.merge(all_df, df, on="date", how="outer")
    return all_df.sort_values("date").reset_index(drop=True)

def to_week_start(d):
    d_ts = pd.to_datetime(d)
    return (d_ts - pd.to_timedelta(d_ts.weekday(), unit="D")).date()

def expand_finals_to_daily(df_finals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df_finals.iterrows():
        s = pd.to_datetime(r["finals_start"]).date()
        e = pd.to_datetime(r["finals_end"]).date()
        d = s
        while d <= e:
            rows.append({"date": d, "school": r["school"]})
            d += timedelta(days=1)
    return pd.DataFrame(rows)

def finals_weekly_intensity(df_finals: pd.DataFrame) -> pd.DataFrame:
    if df_finals.empty:
        return pd.DataFrame(columns=["week_start","finals_school_count_week","is_finals_week"])
    daily = expand_finals_to_daily(df_finals)
    daily["week_start"] = daily["date"].apply(to_week_start)
    g = daily.groupby("week_start")["school"].nunique().reset_index(name="finals_school_count_week")
    g["is_finals_week"] = (g["finals_school_count_week"] > 0).astype(int)
    return g

def align_trends_to_week(trends_df):
    df = trends_df.copy()
    df["week_start"] = df["date"].apply(to_week_start)
    value_cols = [c for c in df.columns if c not in ["date","week_start"]]
    return df.groupby("week_start", as_index=False)[value_cols].mean()

def add_features(merged):
    df = merged.copy()
    df["week_end"] = pd.to_datetime(df["week_start"]) + pd.Timedelta(days=6)
    df["month"] = pd.to_datetime(df["week_start"]).dt.month
    df["year"]  = pd.to_datetime(df["week_start"]).dt.year
    for col in [c for c in df.columns if c.endswith("_near_me")]:
        df[f"{col}_ma4"] = df[col].rolling(4, min_periods=1).mean()
    return df

def main():
    # 1) finals CSV from discovered ICS feeds
    finals_df = build_finals_csv()

    # 2) save a snapshot of Trends
    print("\nPulling Google Trends…")
    trends = get_trends(KEYWORDS, GEO, TIMEFRAME)
    trends_path = os.path.join(DATA_RAW, "trends_us_ma_2019_to_today.csv")
    trends.to_csv(trends_path, index=False)
    print(f"Saved Trends → {trends_path} (rows={len(trends)})")

    # 3) week by week aggregation & merge
    print("\nAggregating and merging…")
    finals_weekly = finals_weekly_intensity(finals_df)
    finals_weekly.to_csv(os.path.join(DATA_OUT, "finals_weekly_intensity.csv"), index=False)

    trends_weekly = align_trends_to_week(trends)
    merged = pd.merge(trends_weekly, finals_weekly, on="week_start", how="left")
    if "finals_school_count_week" not in merged.columns:
        merged["finals_school_count_week"] = 0
        merged["is_finals_week"] = 0
    merged[["finals_school_count_week","is_finals_week"]] = merged[
        ["finals_school_count_week","is_finals_week"]
    ].fillna(0).astype(int)

    final_df = add_features(merged)
    out_path = os.path.join(DATA_OUT, "pizza_vs_finals_weekly_tidy.csv")
    final_df.to_csv(out_path, index=False)
    print(f"\n✅ Done. Saved tidy dataset → {out_path} (rows={len(final_df)})")
    print("\nColumns:", ", ".join(final_df.columns))

if __name__ == "__main__":
    main()
