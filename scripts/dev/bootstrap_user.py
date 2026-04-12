#!/usr/bin/env python3
"""Bootstrap a local development user through the dev HTTP API."""

import argparse
import json
import os
import sys
from urllib import request


def main():
    parser = argparse.ArgumentParser(description="Bootstrap a local dev user")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--dev-api-key")
    parser.add_argument("--telegram-user-id", type=int, default=1)
    parser.add_argument("--first-name", default="Dev")
    parser.add_argument("--username", default="devuser")
    parser.add_argument("--no-ynab", action="store_true")
    parser.add_argument("--not-configured", action="store_true")
    parser.add_argument("--confirmation-mode", action="store_true")
    args = parser.parse_args()
    dev_api_key = args.dev_api_key or os.getenv("DEV_API_KEY")
    if not dev_api_key:
        print("DEV_API_KEY is required. Pass --dev-api-key or export DEV_API_KEY.", file=sys.stderr)
        sys.exit(2)

    payload = json.dumps({
        "telegram_user_id": args.telegram_user_id,
        "first_name": args.first_name,
        "username": args.username,
        "ynab_connected": not args.no_ynab,
        "configured": not args.not_configured,
        "confirmation_mode": args.confirmation_mode,
    }).encode("utf-8")

    req = request.Request(
        f"{args.base_url.rstrip('/')}/dev/bootstrap",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {dev_api_key}",
        },
        method="POST",
    )
    with request.urlopen(req) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
