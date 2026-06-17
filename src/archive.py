import io
import tarfile
from collections.abc import Iterator
from datetime import date

import httpx

from parser import Record, parse_row

ARCHIVE_URL = "https://tisvcloud.freeway.gov.tw/history/TDCS/M05A/M05A_{ymd}.tar.gz"


class ArchiveUnavailable(Exception):
    pass


def fetch_day_bytes(d: date) -> bytes:
    url = ARCHIVE_URL.format(ymd=d.strftime("%Y%m%d"))
    try:
        resp = httpx.get(url, timeout=90.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ArchiveUnavailable(f"cannot fetch {url}: {exc}") from exc
    return resp.content


def iter_csv_lines(tar_bytes: bytes) -> Iterator[str]:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.name.endswith(".csv"):
                continue
            f = tf.extractfile(member)
            if f is None:
                continue
            for line in f.read().decode("utf-8", "replace").splitlines():
                if line.strip():
                    yield line


def fetch_day_records(d: date, wanted_pairs: set[tuple[str, str]]) -> list[Record]:
    records: list[Record] = []
    for line in iter_csv_lines(fetch_day_bytes(d)):
        rec = parse_row(line, wanted_pairs)
        if rec is not None:
            records.append(rec)
    return records
