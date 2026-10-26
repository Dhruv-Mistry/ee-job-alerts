import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


# ============================================================
# SOURCES
# ============================================================

JOBRIGHT_URL = (
    "https://raw.githubusercontent.com/"
    "jobright-ai/2026-Engineer-Internship/master/README.md"
)

SIMPLIFY_URL = (
    "https://raw.githubusercontent.com/"
    "SimplifyJobs/Summer2027-Internships/dev/README.md"
)

STATE_FILE = Path("seen_jobs.json")


# ============================================================
# DISCORD SECRETS
# ============================================================

DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL", ""
).strip()

BAY_AREA_DISCORD_WEBHOOK_URL = os.environ.get(
    "BAY_AREA_DISCORD_WEBHOOK_URL", ""
).strip()

DISCORD_USER_ID = os.environ.get(
    "DISCORD_USER_ID", ""
).strip()


# ============================================================
# EE JOB MATCHING
# ============================================================

POSITIVE_KEYWORDS = {

    # Core EE
    "electrical": 10,
    "electronics": 10,
    "electronic": 9,

    # Hardware / embedded
    "hardware": 9,
    "embedded": 9,
    "firmware": 9,
    "pcb": 9,
    "circuit": 8,
    "microcontroller": 8,

    # FPGA / ASIC / digital hardware
    "fpga": 10,
    "asic": 10,
    "rtl": 10,
    "digital design": 9,
    "verification": 6,

    # Analog / mixed-signal
    "analog": 9,
    "mixed signal": 10,
    "mixed-signal": 10,

    # RF / communications
    "rf": 10,
    "radio frequency": 10,
    "antenna": 9,
    "electromagnetic": 8,
    "emc": 7,
    "emi": 7,
    "signal integrity": 9,
    "signal processing": 7,
    "dsp": 8,
    "telecommunications": 7,
    "wireless": 7,
    "network hardware": 8,

    # Semiconductor
    "semiconductor": 9,
    "silicon": 8,
    "microelectronics": 9,
    "device engineering": 6,

    # Power
    "power electronics": 10,
    "power systems": 8,
    "power system": 8,
    "power": 2,
    "battery": 5,
    "bess": 7,
    "substation": 8,
    "solar": 3,

    # Controls
    "controls": 7,
    "control systems": 8,
    "automation": 2,
    "instrumentation": 7,

    # Aerospace / robotics
    "avionics": 8,
    "robotics": 6,
    "sensor": 5,
    "telemetry": 7,

    # Validation / testing
    "hardware test": 8,
    "validation": 4,
    "test engineer": 7,
    "test engineering": 7,
    "forward deployed": 3,
    "integration and test": 7,
    "systems test": 6,
    "failure analysis": 7,

    # Systems roles
    "systems architecture": 5,
    "systems integration": 4,
    "electrical systems": 9,
    "lv architecture": 7,
    "low voltage": 7,
}


NEGATIVE_KEYWORDS = {

    # Civil
    "civil": -12,
    "structural": -10,
    "geotechnical": -12,
    "roadway": -10,
    "water/wastewater": -10,

    # Other engineering
    "chemical": -10,
    "environmental": -9,
    "mechanical": -8,
    "aerodynamics": -8,

    # Data / ML
    "machine learning": -12,
    "artificial intelligence": -10,
    "data scientist": -10,
    "data science": -10,

    # Software alone is not very relevant,
    # but don't completely reject it because
    # embedded software can be useful to EE.
    "software": -4,

    "frontend": -12,
    "front end": -12,
    "backend": -12,
    "back end": -12,
    "full stack": -12,
    "fullstack": -12,
    "web developer": -12,

    "site reliability": -10,
    "devops": -10,
    "product management": -12,
    "mba": -12,
}


# Simplify has an explicit Hardware Engineering section.
CATEGORY_BONUS = {
    "Hardware Engineering": 4,
}


# 5+ = Discord notification
ALERT_THRESHOLD = 7

# 2-4 = show in Actions log but don't Discord ping
REVIEW_THRESHOLD = 2


# ============================================================
# UNITED STATES FILTER
# ============================================================

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}


US_STATE_NAMES = {
    "ALABAMA",
    "ALASKA",
    "ARIZONA",
    "ARKANSAS",
    "CALIFORNIA",
    "COLORADO",
    "CONNECTICUT",
    "DELAWARE",
    "FLORIDA",
    "GEORGIA",
    "HAWAII",
    "IDAHO",
    "ILLINOIS",
    "INDIANA",
    "IOWA",
    "KANSAS",
    "KENTUCKY",
    "LOUISIANA",
    "MAINE",
    "MARYLAND",
    "MASSACHUSETTS",
    "MICHIGAN",
    "MINNESOTA",
    "MISSISSIPPI",
    "MISSOURI",
    "MONTANA",
    "NEBRASKA",
    "NEVADA",
    "NEW HAMPSHIRE",
    "NEW JERSEY",
    "NEW MEXICO",
    "NEW YORK",
    "NORTH CAROLINA",
    "NORTH DAKOTA",
    "OHIO",
    "OKLAHOMA",
    "OREGON",
    "PENNSYLVANIA",
    "RHODE ISLAND",
    "SOUTH CAROLINA",
    "SOUTH DAKOTA",
    "TENNESSEE",
    "TEXAS",
    "UTAH",
    "VERMONT",
    "VIRGINIA",
    "WASHINGTON",
    "WEST VIRGINIA",
    "WISCONSIN",
    "WYOMING",
}


# Simplify sometimes abbreviates major cities.
US_CITY_ALIASES = {
    "NYC",
    "NEW YORK CITY",
    "SF",
    "SAN FRANCISCO",
    "LA",
    "LOS ANGELES",
}


# ============================================================
# BAY AREA ROUTING
# ============================================================

# Cities commonly used in internship listings across the
# San Francisco Bay Area. A multi-location posting counts as
# Bay Area if ANY listed location matches one of these cities.
BAY_AREA_CITIES = {
    "SAN FRANCISCO",
    "SOUTH SAN FRANCISCO",
    "DALY CITY",
    "SAN BRUNO",
    "BURLINGAME",
    "MILLBRAE",
    "SAN MATEO",
    "FOSTER CITY",
    "BELMONT",
    "SAN CARLOS",
    "REDWOOD CITY",
    "MENLO PARK",
    "PALO ALTO",
    "MOUNTAIN VIEW",
    "SUNNYVALE",
    "SANTA CLARA",
    "SAN JOSE",
    "MILPITAS",
    "CUPERTINO",
    "CAMPBELL",
    "LOS GATOS",
    "SARATOGA",
    "FREMONT",
    "NEWARK",
    "UNION CITY",
    "HAYWARD",
    "SAN LEANDRO",
    "OAKLAND",
    "ALAMEDA",
    "EMERYVILLE",
    "BERKELEY",
    "RICHMOND",
    "WALNUT CREEK",
    "CONCORD",
    "PLEASANTON",
    "DUBLIN",
    "LIVERMORE",
    "SAN RAMON",
    "PETALUMA",
    "NOVATO",
    "SAN RAFAEL",
}

BAY_AREA_PHRASES = {
    "BAY AREA",
    "SAN FRANCISCO BAY AREA",
    "SF BAY AREA",
    "SILICON VALLEY",
}


def is_bay_area_job(job):
    location = clean_text(
        job.get("location", "")
    ).upper()

    if not location:
        return False

    # Explicit regional wording.
    for phrase in BAY_AREA_PHRASES:
        if phrase in location:
            return True

    # Match city names only when the posting indicates California.
    # This also works for multi-location strings such as:
    # "Palo Alto, CA | Irvine, CA | Redmond, WA"
    has_california = (
        bool(re.search(r"\bCA\b", location))
        or "CALIFORNIA" in location
    )

    # ATS boards often return 'Los Angeles; San Francisco' with no CA.
    if not has_california and re.search(r"\b(SAN FRANCISCO|PALO ALTO|SAN JOSE|SANTA CLARA|MOUNTAIN VIEW|SUNNYVALE|MENLO PARK|REDWOOD CITY|CUPERTINO|BURLINGAME)\b", location):
        has_california = True
    if not has_california:
        return False

    for city in BAY_AREA_CITIES:
        if re.search(
            rf"(?<![A-Z]){re.escape(city)}(?![A-Z])",
            location,
        ):
            return True

    return False


# ============================================================
# GENERAL HELPERS
# ============================================================

def download_text(url):

    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "ee-internship-alert-bot/1.0"
        },
    )

    response.raise_for_status()

    return response.text


def clean_text(text):

    text = re.sub(
        r"\s+",
        " ",
        text or "",
    ).strip()

    return text


def strip_company_icons(text):

    text = clean_text(text)

    for icon in (
        "🔥",
        "🛂",
        "🇺🇸",
        "🔒",
        "🎓",
    ):
        text = text.replace(icon, "")

    return clean_text(text)


def extract_markdown_link(cell):

    match = re.search(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        cell,
    )

    if match:

        return (
            clean_text(match.group(1)),
            match.group(2).strip(),
        )

    cleaned = re.sub(
        r"[*_`]",
        "",
        cell,
    )

    return clean_text(cleaned), None


# ============================================================
# URL NORMALIZATION
# ============================================================

def normalize_url(url):

    if not url:
        return ""

    parts = urlsplit(url)

    kept_params = []

    for key, value in parse_qsl(
        parts.query,
        keep_blank_values=True,
    ):

        key_lower = key.lower()

        # Remove tracking parameters.
        if key_lower.startswith("utm_"):
            continue

        if key_lower in {
            "ref",
            "source",
            "gh_src",
            "gh_jid",
            "lever-source",
        }:
            continue

        kept_params.append(
            (key, value)
        )

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            urlencode(
                kept_params,
                doseq=True,
            ),
            "",
        )
    )


# ============================================================
# DUPLICATE CHECKING
# ============================================================

def semantic_key(job):

    def normalize(value):

        value = value.lower()

        value = re.sub(
            r"[^a-z0-9]+",
            " ",
            value,
        )

        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

    return (
        normalize(job["company"]),
        normalize(job["title"]),
        normalize(job["location"]),
    )


# ============================================================
# KEYWORD MATCHING
# ============================================================

def contains_term(text, term):

    text = text.lower()
    term = term.lower()

    # Prevent "rf" from accidentally matching
    # random letters inside another word.
    if " " not in term and "-" not in term:

        pattern = (
            rf"(?<![a-z0-9])"
            rf"{re.escape(term)}"
            rf"(?![a-z0-9])"
        )

        return (
            re.search(pattern, text)
            is not None
        )

    return term in text


# ============================================================
# US-ONLY FILTER
# ============================================================

def is_us_job(job):

    location = clean_text(
        job.get("location", "")
    )

    upper = location.upper()

    if not upper:
        return False

    # Explicit US wording
    if (
        "UNITED STATES" in upper
        or re.search(r"\bUSA\b", upper)
        or re.search(r"\bU\.S\.A?\b", upper)
        or "US REMOTE" in upper
        or "REMOTE - US" in upper
        or "REMOTE, US" in upper
        or "REMOTE (US)" in upper
    ):
        return True

    # Structured ATS location tags, e.g. US-CA-SAN-JOSE
    if re.search(r"\bUS[-_/]CA[-_/]", upper):
        return True

    # Known US metro cities sometimes appear without a state in ATS feeds.
    if re.search(r"\b(SAN FRANCISCO|LOS ANGELES|SAN JOSE|SANTA CLARA|PALO ALTO|EL SEGUNDO|REDONDO BEACH|HAWTHORNE|ALAMEDA|SUNNYVALE|MOUNTAIN VIEW)\b", upper):
        return True

    # City, state abbreviation:
    # Austin, TX
    # San Jose, CA
    for code in US_STATE_CODES:

        if re.search(
            rf",\s*{code}\b",
            upper,
        ):
            return True

        if upper == code:
            return True

    # Full state names
    for state in US_STATE_NAMES:

        if re.search(
            rf"\b{re.escape(state)}\b",
            upper,
        ):
            return True

    # Common Simplify shorthand
    for city in US_CITY_ALIASES:

        if re.search(
            rf"(?<![A-Z])"
            rf"{re.escape(city)}"
            rf"(?![A-Z])",
            upper,
        ):
            return True

    # IMPORTANT:
    # A listing that ONLY says "Remote" is ambiguous.
    # We reject it rather than accidentally sending
    # Canadian/international remote roles.
    return False


# ============================================================
# JOBRIGHT PARSER
# ============================================================

def parse_jobright(markdown):

    jobs = []

    last_company = ""
    last_company_url = ""

    for line in markdown.splitlines():

        if not line.startswith("|"):
            continue

        cells = [
            cell.strip()
            for cell
            in line.strip().strip("|").split("|")
        ]

        if len(cells) != 5:
            continue

        (
            company_cell,
            title_cell,
            location,
            work_model,
            date_posted,
        ) = cells

        # Skip header
        if company_cell == "Company":
            continue

        if (
            set(
                company_cell.replace(" ", "")
            )
            <= {"-"}
        ):
            continue

        # ↳ means same company
        if company_cell == "↳":

            company = last_company
            company_url = last_company_url

        else:

            (
                company,
                company_url,
            ) = extract_markdown_link(
                company_cell
            )

            company = strip_company_icons(
                company
            )

            if company:

                last_company = company

                last_company_url = (
                    company_url or ""
                )

        (
            title,
            job_url,
        ) = extract_markdown_link(
            title_cell
        )

        if not job_url:
            continue

        jobs.append(
            {
                "company": company,
                "company_url": company_url,
                "title": clean_text(title),
                "url": job_url,
                "location": clean_text(location),
                "work_model": clean_text(
                    work_model
                ),
                "date_posted": clean_text(
                    date_posted
                ),
                "source": "Jobright",
                "category":
                    "Engineering and Development",
            }
        )

    return jobs


# ============================================================
# SIMPLIFY PARSER
# ============================================================

def parse_simplify(markdown):

    jobs = []

    # Finds sections such as:
    #
    # ## 🔧 Hardware Engineering Internship Roles
    #
    heading_pattern = re.compile(
        r"^##\s+.+?\s+(.+?)\s+"
        r"Internship Roles\s*$",
        re.MULTILINE,
    )

    headings = list(
        heading_pattern.finditer(markdown)
    )

    for index, heading in enumerate(
        headings
    ):

        category = clean_text(
            heading.group(1)
        )

        section_start = heading.end()

        if index + 1 < len(headings):

            section_end = (
                headings[index + 1].start()
            )

        else:

            section_end = len(markdown)

        section = markdown[
            section_start:section_end
        ]

        soup = BeautifulSoup(
            section,
            "html.parser",
        )

        table = soup.find("table")

        if table is None:
            continue

        tbody = (
            table.find("tbody")
            or table
        )

        last_company = ""

        for row in tbody.find_all(
            "tr",
            recursive=False,
        ):

            cells = row.find_all(
                "td",
                recursive=False,
            )

            if len(cells) != 5:
                continue

            company_text = (
                strip_company_icons(
                    cells[0].get_text(
                        " ",
                        strip=True,
                    )
                )
            )

            if company_text == "↳":

                company = last_company

            else:

                company = company_text

                if company:
                    last_company = company

            title = clean_text(
                cells[1].get_text(
                    " ",
                    strip=True,
                )
            )

            location = clean_text(
                cells[2].get_text(
                    " | ",
                    strip=True,
                )
            )

            # Remove things like:
            # "5 locations | Seattle, WA | ..."
            location = re.sub(
                r"^\d+\s+locations?"
                r"\s*\|\s*",
                "",
                location,
                flags=re.IGNORECASE,
            )

            application_links = [
                a.get(
                    "href",
                    "",
                ).strip()
                for a
                in cells[3].find_all(
                    "a",
                    href=True,
                )
            ]

            # Simplify usually puts the actual
            # employer/ATS application first.
            job_url = next(
                (
                    url
                    for url
                    in application_links

                    if (
                        "/p/" not in url
                        or "simplify.jobs"
                        not in url
                    )
                ),
                (
                    application_links[0]
                    if application_links
                    else ""
                ),
            )

            age = clean_text(
                cells[4].get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                not company
                or not title
                or not job_url
            ):
                continue

            jobs.append(
                {
                    "company": company,
                    "company_url": "",
                    "title": title,
                    "url": job_url,
                    "location": location,
                    "work_model":
                        "Not listed",
                    "date_posted": age,
                    "source":
                        "Simplify 2027",
                    "category": category,
                }
            )

    return jobs


# ============================================================
# SCORE JOBS
# ============================================================

def score_ee_job(job):

    title = job["title"].lower()

    category = job.get(
        "category",
        "",
    )

    score = CATEGORY_BONUS.get(
        category,
        0,
    )

    positive_matches = []
    negative_matches = []

    if score:

        positive_matches.append(
            f"{category} category"
        )

    for (
        keyword,
        weight,
    ) in POSITIVE_KEYWORDS.items():

        if contains_term(
            title,
            keyword,
        ):

            score += weight

            positive_matches.append(
                keyword
            )

    for (
        keyword,
        weight,
    ) in NEGATIVE_KEYWORDS.items():

        if contains_term(
            title,
            keyword,
        ):

            score += weight

            negative_matches.append(
                keyword
            )

    # Every job that Simplify explicitly placed
    # in Hardware Engineering should at least be
    # visible in our "review" logs.
    if (
        category == "Hardware Engineering"
        and score < REVIEW_THRESHOLD
    ):
        score = REVIEW_THRESHOLD

    return (
        score,
        positive_matches,
        negative_matches,
    )


# ============================================================
# DEDUPLICATE SOURCES
# ============================================================

def deduplicate_jobs(jobs):

    deduped = []

    seen_urls = set()
    seen_semantic = set()

    for job in jobs:

        normalized = normalize_url(
            job["url"]
        )

        sem_key = semantic_key(job)

        # Exact URL duplicate
        if (
            normalized
            and normalized in seen_urls
        ):
            continue

        # Same company + title + location
        # appearing in both sources
        if sem_key in seen_semantic:
            continue

        if normalized:
            seen_urls.add(normalized)

        seen_semantic.add(sem_key)

        job["normalized_url"] = (
            normalized
            or job["url"]
        )

        deduped.append(job)

    return deduped


# ============================================================
# SEEN JOB STATE
# ============================================================

def load_seen():

    if not STATE_FILE.exists():
        return set()

    try:

        with STATE_FILE.open("r") as file:

            data = json.load(file)

        if isinstance(data, list):
            return set(data)

        return set()

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return set()


def save_seen(seen):

    with STATE_FILE.open("w") as file:

        json.dump(
            sorted(seen),
            file,
            indent=2,
        )


# ============================================================
# DISCORD
# ============================================================

def build_embed(job):
    is_bay = is_bay_area_job(job)
    matches = ", ".join(
        job.get(
            "positive_matches",
            [],
        )
    )

    if not matches:
        matches = "General EE match"

    embed = {

        "title": job["title"],

        "url": job["url"],

        "description":
            f"**{job['company']}**",

        "fields": [

            {
                "name": "Location",
                "value":
                    job["location"][:1024],
                "inline": False,
            },

            {
                "name": "Source",
                "value": job["source"],
                "inline": True,
            },

            {
                "name": "Posted / Age",
                "value":
                    job["date_posted"],
                "inline": True,
            },

            {
                "name": "EE Match Score",
                "value": str(
                    job["match_score"]
                ),
                "inline": True,
            },

            {
                "name": "Why it matched",
                "value": matches[:1024],
                "inline": False,
            },

        ],

        "footer": {
            "text": (
                "Bay Area EE Internship Alert"
                if is_bay
                else "Nationwide US EE Internship Alert"
            )
        },
    }

    return embed


def send_discord_batches(jobs, is_bay):
    """Send up to 10 embeds per Discord message, ping once per Bay batch group."""
    if not jobs:
        return 0
    webhook = BAY_AREA_DISCORD_WEBHOOK_URL if is_bay else DISCORD_WEBHOOK_URL
    if not webhook:
        raise RuntimeError("Missing Bay Area or nationwide Discord webhook secret")
    sent = 0
    for start in range(0, len(jobs), 10):
        group = jobs[start:start + 10]
        payload = {"username": "EE Internship Alerts",
                   "embeds": [build_embed(job) for job in group],
                   "allowed_mentions": {"parse": []}}
        if is_bay and start == 0 and DISCORD_USER_ID and DISCORD_USER_ID.isdigit():
            payload["content"] = f"<@{DISCORD_USER_ID}> {len(jobs)} new Bay Area EE internship(s)!"
            payload["allowed_mentions"] = {"users": [DISCORD_USER_ID]}
        response = requests.post(webhook, json=payload, timeout=30)
        response.raise_for_status()
        sent += len(group)
        yield group


def send_discord(job):
    # Backward-compatible test helper.
    list(send_discord_batches([job], is_bay_area_job(job)))


# ============================================================
# TEST ALERT
# ============================================================

def test_alert():

    test_job = {

        "company":
            "Test Company",

        "title":
            "Electrical Hardware "
            "Engineering Intern",

        "location":
            "San Jose, CA",

        "work_model":
            "Hybrid",

        "date_posted":
            "Today",

        "url":
            "https://github.com/",

        "source":
            "Test",

        "category":
            "Hardware Engineering",

        "match_score":
            20,

        "positive_matches": [
            "Hardware Engineering category",
            "electrical",
            "hardware",
        ],
    }

    send_discord(test_job)
    test_job["location"] = "El Segundo, CA"
    send_discord(test_job)
    print("Test sent to Bay Area (ping) and nationwide (no ping).")


# ============================================================
# EXTRA SOURCES: DIRECT COMPANY BOARDS + SEARCH INDEX
# ============================================================

import csv
import time
from datetime import datetime, timezone

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "").strip()
BOARDS_FILE = Path("company_boards.json")
REJECTED_REPORT = Path("job_diagnostics.csv")

# Searches include LinkedIn-indexed listings and employer career pages.
# Search engines cannot guarantee all LinkedIn listings are indexed.
SEARCH_QUERIES = [
    'site:linkedin.com/jobs/view/ ("electrical engineering intern" OR "hardware engineer intern") ("2027" OR "summer") California',
    'site:linkedin.com/jobs/view/ ("avionics" OR "embedded" OR "test engineer") internship 2027 ("Bay Area" OR "Los Angeles")',
    'site:linkedin.com/jobs/view/ ("FPGA" OR "RF" OR "power electronics") internship 2027 California',
    '(site:careers.rtx.com OR site:jobs.boeing.com) electrical hardware avionics intern 2027 California',
    '(site:northropgrumman.com OR site:lockheedmartinjobs.com) electrical engineering intern 2027 California',
    '(site:careers.l3harris.com OR site:careers.anduril.com) electrical hardware internship 2027',
    '(site:spacex.com/careers OR site:rocketlabcorp.com OR site:careers.relativityspace.com) avionics electrical internship 2027',
    '("Revel" OR "Astranis" OR "Planet Labs" OR "Varda") ("hardware" OR "test engineering" OR "electrical") intern 2027',
    '("General Atomics" OR "AeroVironment" OR "Shield AI" OR "Saronic") electrical intern 2027 California',
    '("NASA JPL" OR "The Aerospace Corporation" OR "Hermeus") electrical engineering internship 2027',
    '("NVIDIA" OR "Apple" OR "Qualcomm" OR "AMD") hardware electrical intern 2027 California',
    '("Tesla" OR "Applied Materials" OR "KLA" OR "Lam Research") electrical hardware intern 2027 California',
]

INTERNSHIP_RE = re.compile(r"\b(intern(ship)?|co[ -]?op|university student|student engineer)\b", re.I)
BAD_LEVEL_RE = re.compile(r"\b(senior|staff|principal|director|manager|full[- ]time|graduate program)\b", re.I)


def is_internship(job):
    title = job.get("title", "")
    return bool(INTERNSHIP_RE.search(title)) and not bool(BAD_LEVEL_RE.search(title))


def board_jobs():
    if not BOARDS_FILE.exists():
        return []
    config = json.loads(BOARDS_FILE.read_text())
    jobs = []
    for entry in config:
        company, platform, slug = entry["company"], entry["platform"].lower(), entry["slug"]
        try:
            if platform == "greenhouse":
                endpoint = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
                data = requests.get(endpoint, params={"content": "true"}, timeout=25).json()
                rows = [{"title": j.get("title", ""), "url": j.get("absolute_url", ""),
                         "location": j.get("location", {}).get("name", ""),
                         "description": j.get("content", ""), "date": j.get("updated_at", "")}
                        for j in data.get("jobs", [])]
            elif platform == "lever":
                endpoint = f"https://api.lever.co/v0/postings/{slug}"
                data = requests.get(endpoint, params={"mode": "json"}, timeout=25).json()
                rows = [{"title": j.get("text", ""), "url": j.get("hostedUrl", ""),
                         "location": j.get("categories", {}).get("location", ""),
                         "description": j.get("descriptionPlain", ""), "date": ""}
                        for j in data]
            elif platform == "ashby":
                endpoint = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
                data = requests.get(endpoint, timeout=25).json()
                rows = [{"title": j.get("title", ""), "url": j.get("jobUrl", ""),
                         "location": j.get("location", ""),
                         "description": j.get("descriptionPlain", ""), "date": j.get("publishedAt", "")}
                        for j in data.get("jobs", []) if j.get("isListed", True)]
            else:
                print(f"SKIP unknown board platform: {platform} / {company}")
                continue
            for row in rows:
                if not row["url"]:
                    continue
                jobs.append({"company": company, "title": row["title"],
                             "url": row["url"], "location": row["location"],
                             "description": BeautifulSoup(row["description"] or "", "html.parser").get_text(" ", strip=True)[:7000],
                             "work_model": "Not listed", "date_posted": row["date"] or "Unknown",
                             "source": f"{company} ({platform})", "category": "Direct company careers"})
            print(f"BOARD OK {company}: {len(rows)} postings")
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            print(f"BOARD ERROR {company}: {type(exc).__name__}: {str(exc)[:160]}")
    return jobs


def indexed_search_jobs():
    if not SERPAPI_KEY:
        print("SEARCH DISABLED: add SERPAPI_KEY secret to enable indexed LinkedIn and career-site searches")
        return []
    jobs = []
    for query in SEARCH_QUERIES:
        try:
            resp = requests.get("https://serpapi.com/search.json", params={
                "engine": "google", "api_key": SERPAPI_KEY, "q": query,
                "num": 20, "gl": "us", "hl": "en"}, timeout=40)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                print(f"SEARCH ERROR: {data['error']}")
                continue
            for row in data.get("organic_results", []):
                link = row.get("link", "")
                title = row.get("title", "")
                snippet = row.get("snippet", "")
                if not link or not INTERNSHIP_RE.search(title + " " + snippet):
                    continue
                # Search snippets do not always contain structured locations.
                # Keep them for review if geography cannot be verified.
                location_match = re.search(
                    r"\b(?:San Francisco|South San Francisco|San Jose|Palo Alto|Mountain View|Sunnyvale|Santa Clara|Menlo Park|Redwood City|Fremont|Oakland|Berkeley|Burlingame|Los Angeles|El Segundo|Redondo Beach|Long Beach|Pasadena|Irvine|San Diego|Goleta|Santa Monica|Hawthorne|Torrance|Palmdale|Mojave|Sunnyvale|Cupertino|San Mateo|Sacramento)\s*,?\s*(?:CA|California)\b",
                    title + " " + snippet, re.I)
                location = location_match.group(0) if location_match else "Unverified location"
                company = "Unknown (search result)"
                for name in ("Revel", "RTX", "Raytheon", "Northrop Grumman", "Lockheed Martin", "Boeing", "L3Harris", "Anduril", "SpaceX", "Rocket Lab", "Relativity Space", "Astranis", "Planet Labs", "Varda", "General Atomics", "AeroVironment", "Shield AI", "Saronic", "JPL", "Aerospace Corporation", "NVIDIA", "Apple", "Qualcomm", "AMD", "Tesla", "Applied Materials", "KLA", "Lam Research"):
                    if name.lower() in (title + " " + snippet).lower():
                        company = name
                        break
                # Remove typical search-result company suffix while preserving title.
                clean_title = re.sub(r"\s+[|–-]\s+(LinkedIn|Jobs|Careers).*?$", "", title, flags=re.I)
                jobs.append({"company": company, "title": clean_title, "url": link,
                             "location": location, "description": snippet,
                             "work_model": "Not listed", "date_posted": row.get("date", "Unknown"),
                             "source": "Indexed LinkedIn" if "linkedin.com/jobs" in link else "Indexed career page",
                             "category": "Search-index discovery"})
            print(f"SEARCH OK: {query[:62]} ...")
        except (requests.RequestException, ValueError) as exc:
            print(f"SEARCH ERROR {type(exc).__name__}: {str(exc)[:120]}")
    return jobs


def score_with_context(job):
    # Title matches count fully; descriptions provide a capped, modest bonus.
    score, positives, negatives = score_ee_job(job)
    desc = job.get("description", "").lower()
    signals = ["pcb", "schematic", "avionics", "instrumentation", "oscilloscope",
               "data acquisition", "sensor", "hardware bring-up", "rf telemetry",
               "power distribution", "analog circuit", "fpga", "embedded system",
               "electrical design", "circuit design", "hardware test", "test stand"]
    found = [term for term in signals if contains_term(desc, term)]
    bonus = min(5, len(found) * 2)
    if any(contains_term(job["title"], term) for term in ("full stack", "frontend", "backend", "data science")):
        bonus = 0
    score += bonus
    if bonus:
        positives.extend(["description: " + term for term in found[:3]])
    # 'Test engineer' title alone is a possible EE role, not a sure thing.
    if re.search(r"\btest (engineer|engineering)\b", job["title"], re.I) and score < 7 and found:
        score = max(score, 7)
    return score, positives, negatives


def diagnostic_csv(rows):
    with REJECTED_REPORT.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["status", "company", "title", "location", "source", "score", "url"])
        for status, job in rows:
            writer.writerow([status, job.get("company", ""), job.get("title", ""),
                             job.get("location", ""), job.get("source", ""),
                             job.get("match_score", ""), job.get("url", "")])


# ============================================================
# MAIN
# ============================================================

def main():
    if "--test" in sys.argv:
        test_alert()
        return

    diagnostics = []
    feeds = []
    for label, url, parser in (("Jobright", JOBRIGHT_URL, parse_jobright),
                               ("Simplify", SIMPLIFY_URL, parse_simplify)):
        try:
            jobs = parser(download_text(url))
            feeds.extend(jobs)
            print(f"SOURCE {label}: {len(jobs)} jobs")
        except requests.RequestException as exc:
            print(f"SOURCE FAILED {label}: {exc}")

    boards = board_jobs()
    indexed = indexed_search_jobs()
    raw = feeds + boards + indexed
    print(f"RAW: {len(raw)}; direct boards: {len(boards)}; indexed: {len(indexed)}")
    if not raw:
        raise RuntimeError("No sources returned any jobs; refusing to update seen state")

    # Check internship and location BEFORE deduplication so a poorer
    # duplicate cannot displace a richer record from another source.
    candidates = []
    for job in raw:
        if not is_internship(job):
            diagnostics.append(("not_internship", job))
        elif not is_us_job(job):
            diagnostics.append(("location_unverified_or_non_us", job))
        else:
            candidates.append(job)

    # Prioritize direct employer listings and rich descriptions.
    candidates.sort(key=lambda j: ("Direct company careers" not in j.get("category", ""),
                                   -len(j.get("description", ""))))
    unique = deduplicate_jobs(candidates)
    strong, review = [], []
    for job in unique:
        score, positive, negative = score_with_context(job)
        job["match_score"], job["positive_matches"], job["negative_matches"] = score, positive, negative
        if score >= ALERT_THRESHOLD:
            strong.append(job)
            diagnostics.append(("strong", job))
        elif score >= REVIEW_THRESHOLD:
            review.append(job)
            diagnostics.append(("review_only", job))
        else:
            diagnostics.append(("low_score", job))
    diagnostic_csv(diagnostics)
    print(f"US internship candidates: {len(candidates)}; unique: {len(unique)}")
    print(f"Strong EE: {len(strong)}; review: {len(review)}")
    print("Diagnostics saved: job_diagnostics.csv")
    for job in review[:35]:
        print(f"REVIEW [{job['match_score']}]: {job['company']} | {job['title']} | {job['location']}")

    first_run = not STATE_FILE.exists()
    seen = load_seen()
    if first_run:
        seen.update(j["normalized_url"] for j in strong)
        save_seen(seen)
        print("First run baseline created. No alerts sent.")
        return

    new = [j for j in strong if j["normalized_url"] not in seen]
    bay = [j for j in new if is_bay_area_job(j)]
    nationwide = [j for j in new if not is_bay_area_job(j)]
    print(f"NEW {len(new)}: Bay Area {len(bay)}; other US {len(nationwide)}")

    # Post all discoveries in grouped Discord batches. Discord limits embeds
    # to 10 per message. Save seen immediately after EACH successful batch.
    for group in send_discord_batches(bay, True):
        seen.update(j["normalized_url"] for j in group)
        save_seen(seen)
        print(f"SENT Bay Area batch: {len(group)}")
    for group in send_discord_batches(nationwide, False):
        seen.update(j["normalized_url"] for j in group)
        save_seen(seen)
        print(f"SENT nationwide batch: {len(group)}")
    print(f"Done. Sent {len(new)} new internships in this run.")


if __name__ == "__main__":
    main()
