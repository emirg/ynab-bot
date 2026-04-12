#!/usr/bin/env python3
"""Send a synthetic message to the local development HTTP harness."""

import argparse
import json
import os
import sys
from urllib import request


def main():
    parser = argparse.ArgumentParser(description="Send a synthetic local dev message")
    parser.add_argument("text", help="Message text or command such as '/start' or 'Gaste 25k en Carulla'")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--dev-api-key")
    parser.add_argument("--telegram-user-id", type=int, default=1)
    parser.add_argument("--force-commit", action="store_true")
    args = parser.parse_args()
    dev_api_key = args.dev_api_key or os.getenv("DEV_API_KEY")
    if not dev_api_key:
        print("DEV_API_KEY is required. Pass --dev-api-key or export DEV_API_KEY.", file=sys.stderr)
        sys.exit(2)

    payload = json.dumps({
        "telegram_user_id": args.telegram_user_id,
        "text": args.text,
        "force_commit": args.force_commit,
    }).encode("utf-8")

    req = request.Request(
        f"{args.base_url.rstrip('/')}/dev/messages/text",
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
