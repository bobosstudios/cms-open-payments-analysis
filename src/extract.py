from __future__ import annotations
import csv
import io
import requests
import logging
import time
from typing import Iterator
from . import config

log = logging.getLogger(__name__)


def _get_with_retry(session: requests.Session, url: str, attempts: int = 3, **kwargs) -> requests.Response:
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            if attempt == attempts:
                raise
            wait = 2 ** attempt
            log.warning("Request failed (%s); retry %d/%d in %ds", exc, attempt, attempts, wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def resolve_csv_url(session: requests.Session) -> str:
    response = _get_with_retry(session, config.METASTORE_ITEM_URL, timeout=30)
    for distribution in response.json().get("distribution", []):
        data = distribution.get("data", distribution)
        if (data.get("format") or "").lower() == "csv" and data.get("downloadURL"):
            return data["downloadURL"]
    raise RuntimeError("No CSV distribution found for the CMS dataset")


def download_records(states: list[str], max_records: int) -> Iterator[dict]:
    wanted = {state.upper() for state in states}
    per_state = max(1, max_records // len(wanted))
    matched = {state: 0 for state in wanted}
    read = 0

    session = requests.Session()
    csv_url = resolve_csv_url(session)
    log.info("Streaming CSV: %s", csv_url)

    with _get_with_retry(session, csv_url, stream=True, timeout=(30, 300)) as response:
        response.raw.decode_content = True  # transparently handle gzip if present
        text_stream = io.TextIOWrapper(response.raw, encoding="utf-8", errors="replace", newline="")
        reader = csv.reader(text_stream)
        header = [column.lower() for column in next(reader)]

        for values in reader:
            read += 1
            row = dict(zip(header, values))
            state = (row.get("recipient_state") or "").upper()
            if state not in wanted or matched[state] >= per_state:
                continue
            matched[state] += 1
            yield row
            if all(matched[s] >= per_state for s in wanted):
                break
            if read % 100_000 == 0:
                log.info("Read %d rows, matched %s", read, dict(matched))

    log.info("Finished streaming. Read %d rows, matched %s", read, dict(matched))
