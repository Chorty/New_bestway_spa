#!/usr/bin/env python3
"""Parse captured proxy traffic and extract Bestway identifiers.

The script understands HAR files exported from mitmproxy/Charles as well as
Charles JSON (`.chlsj`) session exports. It scans every request/response for the
fields referenced in the project README and prints a consolidated summary that
can be copied into the Home Assistant config flow.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping

TARGET_KEYS = {
    "visitor_id",
    "registration_id",
    "device_id",
    "product_id",
    "client_id",
    "push_type",
}

ENDPOINT_HINTS = {
    "/enduser/visitor",
    "/api/enduser/visitor",
    "/api/enduser/home/room/devices",
    "/api/device/thing_shadow",
    "/command",
}


class ExtractionResult:
    """Helper that keeps field values and provenance metadata."""

    def __init__(self) -> None:
        self.values: MutableMapping[str, List[str]] = defaultdict(list)
        self.sources: MutableMapping[str, List[str]] = defaultdict(list)

    def add(self, key: str, value: Any, source: str) -> None:
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        if value not in self.values[key]:
            self.values[key].append(value)
            self.sources[key].append(source)

    def to_dict(self) -> Dict[str, Any]:
        summary = {}
        for key, values in self.values.items():
            if len(values) == 1:
                summary[key] = {
                    "value": values[0],
                    "sources": self.sources[key],
                }
            else:
                summary[key] = {
                    "value": values,
                    "sources": self.sources[key],
                }
        return summary


def iter_entries(data: Any) -> Iterable[Dict[str, Any]]:
    """Yield request/response style dicts from a HAR or Charles export."""

    if isinstance(data, dict):
        # HAR structure
        log = data.get("log")
        if isinstance(log, dict):
            entries = log.get("entries")
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        yield entry
                return

        # Charles session JSON
        sessions = data.get("sessions")
        if isinstance(sessions, list):
            for session in sessions:
                if not isinstance(session, dict):
                    continue
                entries = session.get("entries") or session.get("requests")
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if isinstance(entry, dict):
                        yield entry
            return

        # Some exports place entries directly at the root
        entries = data.get("entries")
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    yield entry
            return

    raise ValueError("Unsupported capture format. Provide a HAR or .chlsj export.")


def decode_body(content: Dict[str, Any]) -> str:
    text = content.get("text")
    if text is None:
        return ""
    encoding = content.get("encoding")
    if encoding == "base64":
        try:
            return base64.b64decode(text).decode("utf-8", errors="ignore")
        except Exception:  # pragma: no cover - defensive
            return ""
    return text


def parse_json_payload(raw: str) -> Any:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def collect_from_payload(result: ExtractionResult, payload: Any, source: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in TARGET_KEYS and value not in (None, ""):
                result.add(key, value, source)
            collect_from_payload(result, value, source)
    elif isinstance(payload, list):
        for item in payload:
            collect_from_payload(result, item, source)


def extract_from_entry(result: ExtractionResult, entry: Dict[str, Any]) -> None:
    request = entry.get("request", {})
    response = entry.get("response", {})
    url = request.get("url") or request.get("requestURL") or "unknown"

    matched_hint = next((hint for hint in ENDPOINT_HINTS if hint in url), None)
    source_label = matched_hint or url

    # Request body
    if body := request.get("body") or request.get("postData"):
        if isinstance(body, dict):
            if "text" in body:
                payload = parse_json_payload(body["text"])
                collect_from_payload(result, payload, f"request:{source_label}")
            elif "params" in body:
                for param in body["params"]:
                    if not isinstance(param, dict):
                        continue
                    name = param.get("name")
                    value = param.get("value")
                    if name in TARGET_KEYS and value:
                        result.add(name, value, f"request:{source_label}")
        elif isinstance(body, str):
            payload = parse_json_payload(body)
            collect_from_payload(result, payload, f"request:{source_label}")

    # Response body
    content = response.get("content") or {}
    payload = parse_json_payload(decode_body(content))
    collect_from_payload(result, payload, f"response:{source_label}")


def load_capture(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:  # pragma: no cover - early validation
        raise SystemExit(f"Failed to parse JSON from {path}: {exc}") from exc


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="HAR or .chlsj file exported from the proxy")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Optional path to save the extracted credentials as JSON",
    )
    args = parser.parse_args(argv)

    capture = load_capture(args.capture)
    result = ExtractionResult()

    for entry in iter_entries(capture):
        extract_from_entry(result, entry)

    summary = result.to_dict()
    if not summary:
        print("No Bestway identifiers were found. Ensure the capture covers the login/pairing flow.")
        return 1

    formatted = json.dumps(summary, indent=2, ensure_ascii=False)
    print(formatted)

    if args.output:
        args.output.write_text(formatted + "\n", encoding="utf-8")
        print(f"Saved results to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
