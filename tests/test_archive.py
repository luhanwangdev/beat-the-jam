import io
import tarfile
from datetime import date
import pytest
from archive import iter_csv_lines, fetch_day_records


def _make_tar(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_iter_csv_lines_reads_all_csv_members():
    tb = _make_tar({
        "20250529/22/a.csv": "line1\nline2\n",
        "20250529/22/b.csv": "line3\n",
        "20250529/notes.txt": "ignore me",
    })
    lines = sorted(iter_csv_lines(tb))
    assert lines == ["line1", "line2", "line3"]


def test_fetch_day_records_filters_to_wanted_pairs(monkeypatch):
    tb = _make_tar({"20250529/22/a.csv":
        "2025/05/29 22:00,05F0055S,05F0287S,31,52,168\n"
        "2025/05/29 22:00,05F0055S,05F0287S,41,52,168\n"
        "2025/05/29 22:00,01F0017N,01F0005N,31,86,66\n"})
    monkeypatch.setattr("archive.fetch_day_bytes", lambda d: tb)
    recs = fetch_day_records(date(2025, 5, 29), {("05F0055S", "05F0287S")})
    assert len(recs) == 1
    assert recs[0].speed == 52.0
