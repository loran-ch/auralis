from services.asr_segment import (
    distribute_offsets,
    join_segment_parts,
    looks_incomplete,
    preview_translate_tail,
    should_force_finalize,
    split_transcript_segments,
    uncommitted_suffix,
)


def test_split_keeps_short_text():
    assert split_transcript_segments("今天学习概率论。", 120) == ["今天学习概率论。"]


def test_split_prefers_strong_punctuation():
    text = "他也是一门非常重要的课程。今天我们首先来看第一讲随机事件与概率。这一讲包含九个知识点。"
    parts = split_transcript_segments(text, 30)
    assert all(len(part) <= 30 for part in parts)
    assert "".join(parts).replace(" ", "") == text.replace(" ", "")
    assert any("今天我们首先" in part for part in parts)


def test_split_hard_cuts_when_no_punctuation():
    text = "甲" * 250
    parts = split_transcript_segments(text, 120)
    assert len(parts) >= 2
    assert all(len(part) <= 120 for part in parts)
    assert "".join(parts) == text


def test_preview_translate_tail():
    assert preview_translate_tail("abcdefghij", 4) == "ghij"
    assert preview_translate_tail("短", 60) == "短"


def test_uncommitted_suffix_tracks_prefix():
    active, prefix = uncommitted_suffix("今天学习概率论与数理统计", "今天学习")
    assert active.startswith("概率论")
    assert prefix == "今天学习"
    active2, prefix2 = uncommitted_suffix("全新的一句", "今天学习")
    assert active2 == "全新的一句"
    assert prefix2 == ""


def test_should_force_finalize_by_length_and_time():
    assert should_force_finalize("x" * 120, max_chars=120, open_since=0, now=1, force_ms=10000)
    assert should_force_finalize(
        "这是一句足够长的内容",
        max_chars=120,
        open_since=0,
        now=11,
        force_ms=10000,
        min_chars=5,
    )
    assert not should_force_finalize(
        "短",
        max_chars=120,
        open_since=0,
        now=11,
        force_ms=10000,
    )


def test_distribute_offsets():
    ranges = distribute_offsets(0, 900, 3)
    assert ranges == [(0, 300), (300, 600), (600, 900)]


def test_looks_incomplete_for_mid_clause_fragments():
    assert looks_incomplete("他也是我们大学数学，甚至是考研数学当中。", 40)
    assert looks_incomplete("非常重要的一个。", 40)
    assert looks_incomplete("这一讲当中将包括。", 40)
    assert looks_incomplete("占有，非常重要的。", 40)
    # 语义已收束、且达到长度阈值时不应再等下一段。
    complete = "今天我们学习随机事件与概率。这是数据统计中非常重要的基础内容，后面还会继续展开。"
    assert not looks_incomplete(complete, 40)


def test_join_segment_parts_merges_chinese_fragments():
    assert (
        join_segment_parts(["他也是我们大学数学，甚至是考研数学当中。", "非常重要的一个。"])
        == "他也是我们大学数学，甚至是考研数学当中。非常重要的一个。"
    )
    assert join_segment_parts(["Hello", "world"]) == "Hello world"
