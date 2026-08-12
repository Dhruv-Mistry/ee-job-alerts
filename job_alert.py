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
    "power": 5,
    "battery": 5,
    "bess": 7,
    "substation": 8,
    "solar": 3,

    # Controls
    "controls": 7,
    "control systems": 8,
    "automation": 5,
    "instrumentation": 7,

    # Aerospace / robotics
    "avionics": 8,
    "robotics": 6,
    "sensor": 5,
    "telemetry": 7,

    # Validation / testing
    "hardware test": 8,
    "validation": 4,
    "test engineer": 4,
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
}


# Simplify has an explicit Hardware Engineering section.
CATEGORY_BONUS = {
    "Hardware Engineering": 4,
}


# 5+ = Discord notification
ALERT_THRESHOLD = 5

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

def send_discord(job):

    if not DISCORD_WEBHOOK_URL:

        raise RuntimeError(
            "DISCORD_WEBHOOK_URL "
            "environment variable is missing."
        )

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
            "text":
                "Nationwide US EE Internship Alert"
        },
    }

    payload = {

        "username":
            "EE Internship Alerts",

        "embeds": [
            embed
        ],
    }

    # Actual @mention if you add your
    # numeric Discord ID to GitHub Secrets.
    if DISCORD_USER_ID:

        payload["content"] = (
            f"<@{DISCORD_USER_ID}> "
            "New EE internship"
        )

        payload["allowed_mentions"] = {
            "users": [
                DISCORD_USER_ID
            ]
        }

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()


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
            "Austin, TX",

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

    print(
        "Test Discord alert sent."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if "--test" in sys.argv:

        test_alert()

        return

    # --------------------------------------------------------
    # DOWNLOAD BOTH SOURCES
    # --------------------------------------------------------

    jobright_text = download_text(
        JOBRIGHT_URL
    )

    simplify_text = download_text(
        SIMPLIFY_URL
    )

    # --------------------------------------------------------
    # PARSE BOTH SOURCES
    # --------------------------------------------------------

    jobright_jobs = parse_jobright(
        jobright_text
    )

    simplify_jobs = parse_simplify(
        simplify_text
    )

    raw_jobs = (
        jobright_jobs
        + simplify_jobs
    )

    # --------------------------------------------------------
    # UNITED STATES ONLY
    # --------------------------------------------------------

    us_jobs = [
        job
        for job in raw_jobs
        if is_us_job(job)
    ]

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique_jobs = deduplicate_jobs(
        us_jobs
    )

    # --------------------------------------------------------
    # SCORE EE RELEVANCE
    # --------------------------------------------------------

    strong_jobs = []
    review_jobs = []

    for job in unique_jobs:

        (
            score,
            positive,
            negative,
        ) = score_ee_job(job)

        job["match_score"] = score

        job["positive_matches"] = (
            positive
        )

        job["negative_matches"] = (
            negative
        )

        if score >= ALERT_THRESHOLD:

            strong_jobs.append(job)

        elif score >= REVIEW_THRESHOLD:

            review_jobs.append(job)

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print(
        "========== JOB ALERT REPORT =========="
    )

    print(
        f"Jobright fetched:          "
        f"{len(jobright_jobs)}"
    )

    print(
        f"Simplify fetched:          "
        f"{len(simplify_jobs)}"
    )

    print(
        f"Raw listings:              "
        f"{len(raw_jobs)}"
    )

    print(
        f"Non-US/ambiguous removed:  "
        f"{len(raw_jobs) - len(us_jobs)}"
    )

    print(
        f"Duplicates removed:        "
        f"{len(us_jobs) - len(unique_jobs)}"
    )

    print(
        f"Unique US listings:        "
        f"{len(unique_jobs)}"
    )

    print(
        f"Strong EE matches:         "
        f"{len(strong_jobs)}"
    )

    print(
        f"Possible EE matches:       "
        f"{len(review_jobs)}"
    )

    # --------------------------------------------------------
    # SHOW STRONG MATCHES
    # --------------------------------------------------------

    print(
        "\n=== STRONG MATCHES ==="
    )

    for job in strong_jobs:

        print(
            f"[{job['match_score']}] "
            f"{job['company']} — "
            f"{job['title']} "
            f"({job['location']}) "
            f"[{job['source']}]"
        )

    # --------------------------------------------------------
    # SHOW BORDERLINE MATCHES
    # --------------------------------------------------------

    print(
        "\n=== POSSIBLE MATCHES "
        "(not alerted) ==="
    )

    for job in review_jobs:

        print(
            f"[{job['match_score']}] "
            f"{job['company']} — "
            f"{job['title']} "
            f"({job['location']}) "
            f"[{job['source']}]"
        )

    # --------------------------------------------------------
    # LOAD PREVIOUS JOBS
    # --------------------------------------------------------

    seen = load_seen()

    # --------------------------------------------------------
    # FIRST RUN = BASELINE
    # --------------------------------------------------------

    if not STATE_FILE.exists():

        for job in strong_jobs:

            seen.add(
                job["normalized_url"]
            )

        save_seen(seen)

        print(
            "\nFirst run complete. "
            "Existing strong EE matches "
            "were saved without sending alerts."
        )

        return

    # --------------------------------------------------------
    # DETECT NEW JOBS
    # --------------------------------------------------------

    new_jobs = [

        job

        for job in strong_jobs

        if (
            job["normalized_url"]
            not in seen
        )
    ]

    print(
        f"\nNew strong EE matches:     "
        f"{len(new_jobs)}"
    )

    # --------------------------------------------------------
    # SEND ALERTS
    # --------------------------------------------------------

    for job in reversed(new_jobs):

        print(
            f"ALERT: "
            f"{job['company']} — "
            f"{job['title']}"
        )

        send_discord(job)

        seen.add(
            job["normalized_url"]
        )

    # --------------------------------------------------------
    # SAVE STATE
    # --------------------------------------------------------

    save_seen(seen)

    print(
        f"Discord alerts sent:       "
        f"{len(new_jobs)}"
    )

    print(
        "======================================"
    )


if __name__ == "__main__":
    main()
