# reth-scraping

## Overview

The best Rust engineers in the world are not on job boards. They are building in
open source. Reth — the Rust-based Ethereum execution client maintained by Paradigm —
is one of the highest-signal repositories in the entire blockchain ecosystem. The
engineers contributing to it, filing issues, submitting PRs, and tracking its
development are exactly the kind of systems-level builders that are nearly impossible
to find through traditional sourcing.

This script is a sourcing tool. It scrapes GitHub for users who have recently
interacted with the reth repository — opened issues, submitted PRs, or starred the
project — and exports their public profile data to a CSV. The goal is to identify
active contributors in the EVM ecosystem before they are on anyone's radar, and reach
them through the communities they actually live in.

---

A Python script that scrapes GitHub for users who have recently interacted with the
[paradigmxyz/reth](https://github.com/paradigmxyz/reth) repository. Built for sourcing
active contributors in the Ethereum/EVM ecosystem.

## What it does

Collects GitHub users who have opened issues, submitted PRs, or starred the reth repo
in the last 90 days, then fetches their public profiles and exports everything to a CSV.

**Output fields:** `github_handle`, `name`, `bio`, `location`, `company`, `twitter`,
`profile_url`, `followers`, `public_repos`, `activities`

## Setup
```bash
pip install requests
export GITHUB_TOKEN=your_token_here
```

A GitHub token is optional but recommended. Without one you are rate-limited to
60 requests per hour, which will be slow on a large repo like reth.

## Usage
```bash
python scrape_reth_contributors.py
```

Output is written to `reth_contributors.csv` in the current directory.

## Configuration

Edit the constants at the top of the script to adjust behavior:

| Variable | Default | Description |
|---|---|---|
| `REPO` | `paradigmxyz/reth` | Target repository |
| `DAYS` | `90` | Lookback window in days |
| `OUTPUT_FILE` | `reth_contributors.csv` | Output file name |

## Notes

- Stargazer collection can be slow on popular repos since the API paginates
  through all historical stars to find recent ones.
- The script handles rate limiting automatically and will sleep and retry if
  it hits the GitHub API limit.
