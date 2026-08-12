import json
import os
import re
import sys
from pathlib import Path

import requests


SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "jobright-ai/2026-Engineer-Internship/master/README.md"
)

STATE_FILE = Path("seen_jobs.json")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
DISCORD_USER_ID = os.environ.get("DISCORD_USER_ID", "").strip()


# Change these whenever you want.
EE_KEYWORDS = [
    "electrical",
    "electronics",
    "hardware",
    "embedded",
    "firmware",
    "fpga",
    "asic",
    "pcb",
    "rf ",
    "radio frequency",
    "analog",
    "mixed signal",
    "mixed-signal",
    "power electronics",
    "power system",
    "controls",
    "control system",
    "circuit",
    "semiconductor",
    "silicon",
    "signal integrity",
    "electromagnetic",
    "antenna",
    "avionics",
    "telemetry",
    "instrumentation",
    "sensor",
    "validation engineer",
    "verification engineer",
    "test engineer",
    "systems architecture",
    "robotics",
]


def extract_markdown_link(cell):
    """
    Converts:
    **[Electrical Engineer Intern](https://example.com/job)**

    into:
    ("Electrical Engineer Intern", "https://example.com/job")
    """

    match = re.search(r"\[([^\]]+)\]\((https?://[^)]+)\)", cell)

    if match:
        return match.group(1).strip(), match.group(2).strip()

    # No link found
    cleaned = re.sub(r"[*_`]", "", cell).strip()
    return cleaned, None


def download_jobs():
    response = requests.get(SOURCE_URL, timeout=30)
    response.raise_for_status()
    return response.text


def parse_jobs(markdown):
    jobs = []

    last_company = ""
    last_company_url = ""

    for line in markdown.splitlines():

        if not line.startswith("|"):
            continue

        cells = [
            cell.strip()
            for cell in line.strip().strip("|").split("|")
        ]

        if len(cells) != 5:
            continue

        company_cell, title_cell, location, work_model, date_posted = cells

        # Skip table header
        if company_cell == "Company":
            continue

        if set(company_cell.replace(" ", "")) <= {"-"}:
            continue

        # Some rows use ↳ to mean same company as previous row
        if company_cell == "↳":
            company = last_company
            company_url = last_company_url

        else:
            company, company_url = extract_markdown_link(company_cell)

            if company:
                last_company = company
                last_company_url = company_url or ""

        title, job_url = extract_markdown_link(title_cell)

        if not job_url:
            continue

        jobs.append(
            {
                "company": company,
                "company_url": company_url,
                "title": title,
                "url": job_url,
                "location": location,
                "work_model": work_model,
                "date_posted": date_posted,
            }
        )

    return jobs


def is_ee_job(job):
    title = job["title"].lower()

    return any(keyword in title for keyword in EE_KEYWORDS)


def load_seen():
    if not STATE_FILE.exists():
        return set()

    try:
        with STATE_FILE.open("r") as file:
            return set(json.load(file))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(seen):
    with STATE_FILE.open("w") as file:
        json.dump(sorted(seen), file, indent=2)


def send_discord(job):
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL environment variable is missing."
        )

    embed = {
        "title": job["title"],
        "url": job["url"],
        "description": f"**{job['company']}**",
        "fields": [
            {
                "name": "Location",
                "value": job["location"],
                "inline": True,
            },
            {
                "name": "Work Model",
                "value": job["work_model"],
                "inline": True,
            },
            {
                "name": "Posted",
                "value": job["date_posted"],
                "inline": True,
            },
        ],
        "footer": {
            "text": "EE Internship Alert • Jobright"
        },
    }

    payload = {
        "username": "EE Internship Alerts",
        "embeds": [embed],
    }

    # Optional actual Discord ping
    if DISCORD_USER_ID:
        payload["content"] = f"<@{DISCORD_USER_ID}> New EE internship"
        payload["allowed_mentions"] = {
            "users": [DISCORD_USER_ID]
        }

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()


def test_alert():
    test_job = {
        "company": "Test Company",
        "title": "Electrical Hardware Engineering Intern",
        "location": "San Jose, CA",
        "work_model": "Hybrid",
        "date_posted": "Today",
        "url": "https://github.com/",
    }

    send_discord(test_job)

    print("Test Discord alert sent.")


def main():

    if "--test" in sys.argv:
        test_alert()
        return

    markdown = download_jobs()

    all_jobs = parse_jobs(markdown)

    ee_jobs = [
        job
        for job in all_jobs
        if is_ee_job(job)
    ]

    seen = load_seen()

    print(f"Found {len(all_jobs)} total jobs.")
    print(f"Found {len(ee_jobs)} potentially relevant EE jobs.")

    # First run:
    # Establish a baseline instead of spamming every existing listing.
    if not STATE_FILE.exists():

        for job in ee_jobs:
            seen.add(job["url"])

        save_seen(seen)

        print(
            "First run complete. Existing jobs were saved "
            "without sending alerts."
        )

        return

    new_jobs = [
        job
        for job in ee_jobs
        if job["url"] not in seen
    ]

    print(f"Found {len(new_jobs)} new EE jobs.")

    # Send oldest first so newest ends up at bottom of Discord
    for job in reversed(new_jobs):

        print(
            f"ALERT: {job['company']} — {job['title']}"
        )

        send_discord(job)

        seen.add(job["url"])

    save_seen(seen)


if __name__ == "__main__":
    main()
