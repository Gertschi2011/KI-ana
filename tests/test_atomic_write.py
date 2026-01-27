from __future__ import annotations

import os
from pathlib import Path

import pytest

from netapi.utils.fs import atomic_write_json, atomic_write_text


def test_atomic_write_text_creates_file_and_removes_tmp(tmp_path: Path) -> None:
    p = tmp_path / "hello.txt"
    atomic_write_text(p, "hello")

    assert p.exists()
    assert p.read_text(encoding="utf-8") == "hello"
    assert not (tmp_path / "hello.txt.tmp").exists()


def test_atomic_write_json_quarantines_on_post_write_size_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "blk.json"

    # Force the post-write size check to fail (simulating a crash or fs issue)
    orig_stat = Path.stat

    def fake_stat(self: Path, *args, **kwargs):  # type: ignore[override]
        st = orig_stat(self, *args, **kwargs)
        if self == p:
            return os.stat_result(
                (
                    st.st_mode,
                    st.st_ino,
                    st.st_dev,
                    st.st_nlink,
                    st.st_uid,
                    st.st_gid,
                    0,  # st_size
                    st.st_atime,
                    st.st_mtime,
                    st.st_ctime,
                )
            )
        return st

    monkeypatch.setattr(Path, "stat", fake_stat)

    with pytest.raises(ValueError):
        atomic_write_json(p, {"id": "BLK_test", "title": "x", "content": "y"}, kind="block", min_bytes=32)

    qdir = tmp_path / "_quarantine"
    assert qdir.exists(), "quarantine dir should be created"
    assert (qdir / "README.txt").exists(), "README should be dropped for forensics"
    assert any(child.name.startswith("blk.json.quarantine") for child in qdir.iterdir()), "quarantined file should exist"
