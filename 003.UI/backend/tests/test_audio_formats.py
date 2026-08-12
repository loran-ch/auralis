from types import SimpleNamespace

from routers import lecture
from routers.lecture import _detect_audio_extension


def test_detects_mp3_with_id3_header():
    assert _detect_audio_extension(b"ID3\x04\x00\x00\x00\x00") == ".mp3"


def test_detects_mp3_with_frame_sync_header():
    assert _detect_audio_extension(b"\xff\xfb\x90\x64") == ".mp3"


def test_rejects_unknown_audio_header():
    assert _detect_audio_extension(b"not-an-audio-file") is None


def test_audio_segments_are_appended_and_can_be_rolled_back(tmp_path, monkeypatch):
    monkeypatch.setattr(lecture, "AUDIO_DIR", tmp_path)
    row = SimpleNamespace(id=8, audio_url=None)

    first = lecture._write_audio_segment(row, 3, b"ID3-first", ".mp3", False)
    row.audio_url = f"/uploads/audio/{first['filename']}"
    second = lecture._write_audio_segment(row, 3, b"ID3-second", ".mp3", True)

    assert first["filepath"] == second["filepath"]
    assert second["filepath"].read_bytes() == b"ID3-firstID3-second"

    lecture._rollback_audio_segment(second)
    assert first["filepath"].read_bytes() == b"ID3-first"
