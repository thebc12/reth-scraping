#!/usr/bin/env python3
"""
Scrape GitHub users who have opened issues, submitted PRs, or starred
the paradigmxyz/reth repository in the last 90 days.

Usage:
    export GITHUB_TOKEN=your_token_here
    python scrape_reth_contributors.py

Output:
    reth_contributors.csv
"""

import csv
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

REPO = "paradigmxyz/reth"
DAYS = 90
OUTPUT_FILE = "reth_contributors.csv"
BASE_URL = "https://api.github.com"


def get_headers():
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        print("Warning: GITHUB_TOKEN not set. Requests will be rate-limited to 60/hour.", file=sys.stderr)
    return headers


HEADERS = get_headers()


def paginate(url, params=None):
    """Yield items from all pages of a GitHub API endpoint."""
    params = params or {}
    params.setdefault("per_page", 100)
    while url:
        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code == 403:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 1)
            print(f"  Rate limited. Sleeping {wait:.0f}s ...", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        yield from resp.json()
        # Follow Link: <url>; rel="next" header
        link = resp.links.get("next", {})
        url = link.get("url")
        params = {}  # params are already encoded in the next URL


def get_user_profile(login):
    """Fetch a user's public profile. Returns dict or None on error."""
    url = f"{BASE_URL}/users/{login}"
    for attempt in range(3):
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 403:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 1)
            print(f"  Rate limited on user lookup. Sleeping {wait:.0f}s ...", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    return None


def collect_issue_and_pr_authors(since_iso):
    """Return set of logins who opened issues or PRs since the cutoff."""
    logins = set()
    # The issues endpoint includes PRs when is:issue or is:pr; using type filter via state
    # GitHub issues API returns both issues and PRs; PRs have a 'pull_request' key.
    url = f"{BASE_URL}/repos/{REPO}/issues"
    params = {
        "state": "all",
        "since": since_iso,
        "per_page": 100,
    }
    print("  Fetching issues and PRs ...", file=sys.stderr)
    count = 0
    for item in paginate(url, params):
        login = item.get("user", {}).get("login")
        if login and login != "ghost":
            logins.add(login)
            count += 1
    print(f"  Found {count} issue/PR events -> {len(logins)} unique authors", file=sys.stderr)
    return logins


def collect_stargazers(since_dt):
    """Return set of logins who starred the repo since the cutoff."""
    logins = set()
    # Use the stargazers endpoint with timestamps (requires Accept header tweak)
    url = f"{BASE_URL}/repos/{REPO}/stargazers"
    headers_with_stars = {**HEADERS, "Accept": "application/vnd.github.star+json"}

    print("  Fetching stargazers (this may take a while for popular repos) ...", file=sys.stderr)
    page = 1
    recent_found = False
    while url:
        params = {"per_page": 100, "page": page}
        resp = requests.get(url, headers=headers_with_stars, params=params)
        if resp.status_code == 403:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 1)
            print(f"  Rate limited. Sleeping {wait:.0f}s ...", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        items = resp.json()
        if not items:
            break

        # Stars are returned oldest-first by default; newest stars are on last pages.
        # We iterate from the last page backward to stop early once we pass the cutoff.
        # Simpler: just collect all and filter — reth has ~O(10k) stars, manageable.
        for item in items:
            starred_at_str = item.get("starred_at", "")
            if not starred_at_str:
                continue
            starred_at = datetime.fromisoformat(starred_at_str.replace("Z", "+00:00"))
            if starred_at >= since_dt:
                login = item.get("user", {}).get("login")
                if login and login != "ghost":
                    logins.add(login)
                    recent_found = True

        link = resp.links.get("next", {})
        next_url = link.get("url")
        if not next_url:
            break
        url = next_url
        page += 1  # not actually used after first page when following Link header

    print(f"  Found {len(logins)} unique stargazers in the window", file=sys.stderr)
    return logins


def main():
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=DAYS)
    since_iso = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Collecting contributors to {REPO} since {since_iso} ({DAYS} days)", file=sys.stderr)

    print("\n[1/3] Issues & PR authors", file=sys.stderr)
    issue_pr_authors = collect_issue_and_pr_authors(since_iso)

    print("\n[2/3] Stargazers", file=sys.stderr)
    stargazers = collect_stargazers(cutoff_dt)

    all_logins = issue_pr_authors | stargazers
    print(f"\n[3/3] Fetching profiles for {len(all_logins)} unique users ...", file=sys.stderr)

    rows = []
    for i, login in enumerate(sorted(all_logins), 1):
        print(f"  [{i}/{len(all_logins)}] {login}", file=sys.stderr)
        profile = get_user_profile(login)
        if profile is None:
            continue

        # Determine which activities this user performed
        activities = []
        if login in issue_pr_authors:
            activities.append("issue/pr")
        if login in stargazers:
            activities.append("starred")

        rows.append(
            {
                "github_handle": login,
                "bio": (profile.get("bio") or "").strip().replace("\n", " "),
                "location": (profile.get("location") or "").strip(),
                "profile_url": profile.get("html_url", f"https://github.com/{login}"),
                "name": (profile.get("name") or "").strip(),
                "company": (profile.get("company") or "").strip(),
                "twitter": (profile.get("twitter_username") or "").strip(),
                "followers": profile.get("followers", 0),
                "public_repos": profile.get("public_repos", 0),
                "activities": ", ".join(activities),
            }
        )
        # Be polite to the API
        time.sleep(0.05)

    # Write CSV
    fieldnames = [
        "github_handle",
        "name",
        "bio",
        "location",
        "company",
        "twitter",
        "profile_url",
        "followers",
        "public_repos",
        "activities",
    ]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. {len(rows)} users written to {OUTPUT_FILE}", file=sys.stderr)
    print(f"  Issue/PR authors: {len(issue_pr_authors)}", file=sys.stderr)
    print(f"  Stargazers:       {len(stargazers)}", file=sys.stderr)


if __name__ == "__main__":
    main()
