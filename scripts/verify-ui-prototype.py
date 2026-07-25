#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import re
import sys
from pathlib import Path

ATTRS = {"onclick", "onsubmit", "oninput", "onkeyup", "onchange"}


class Collector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.handlers: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs):
        values = dict(attrs)
        element_id = values.get("id")
        if element_id is not None:
            self.ids.append(element_id)
        for name, value in attrs:
            if name in ATTRS:
                self.handlers.append({"attribute": name, "value": value or "", "tag": tag, "id": element_id})


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the exact Letterblack UI prototype artifact before bridge work.")
    parser.add_argument("html", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path("contracts/ui-prototype-dom.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    raw = args.html.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    expected_sha = manifest["sourceSha256"]
    if actual_sha != expected_sha:
        print(f"FAIL sha256 expected={expected_sha} actual={actual_sha}", file=sys.stderr)
        return 1

    text = raw.decode("utf-8")
    collector = Collector()
    collector.feed(text)
    functions = re.findall(r"\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", text)

    failures: list[str] = []
    if collector.ids != manifest["dom"]["ids"]:
        failures.append("DOM id sequence differs from manifest")
    if collector.handlers != manifest["dom"]["inlineHandlers"]:
        failures.append("inline handler sequence differs from manifest")
    if functions != manifest["script"]["functions"]:
        failures.append("script function sequence differs from manifest")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1

    print(
        "PASS exact UI prototype verified "
        f"sha256={actual_sha} ids={len(collector.ids)} "
        f"handlers={len(collector.handlers)} functions={len(functions)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
