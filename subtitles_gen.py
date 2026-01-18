# subtitles_gen.py
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any


# -----------------------------
# Time formatting helpers
# -----------------------------
def sec_to_ass_time(t: float) -> str:
    """
    ASS time format: H:MM:SS.cs  (centiseconds)
    Example: 0:00:01.23
    """
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def clean_word(w: str) -> str:
    return (w or "").strip()


# -----------------------------
# MFA JSON loader 
# -----------------------------
def load_words_from_mfa_json(json_path: str | Path) -> List[Dict[str, Any]]:
    """
    Loads word intervals from MFA JSON output.

    Expected MFA JSON structure:
    {
      "tiers": {
        "words": {
          "type": "interval",
          "entries": [
            [start, end, "word"],
            ...
          ]
        }
      }
    }

    Returns:
    [
      {"word": "hello", "start": 0.1, "end": 0.3},
      ...
    ]
    """
    import json

    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))

    try:
        entries = data["tiers"]["words"]["entries"]
    except Exception as e:
        raise ValueError(
            f"Could not extract words from MFA JSON file: {json_path}\n"
            f"Expected: data['tiers']['words']['entries']\n"
            f"Top-level keys found: {list(data.keys()) if isinstance(data, dict) else type(data)}"
        ) from e

    if not isinstance(entries, list):
        raise ValueError(f"MFA JSON words.entries is not a list in {json_path}")

    words: List[Dict[str, Any]] = []
    for item in entries:
        # Each item should be [start, end, label]
        if not isinstance(item, list) or len(item) != 3:
            continue

        start, end, label = item
        label = clean_word(str(label))

        # # Skip silence/unknown markers --> #TODO: this might break havent checked, im assuming it would cause timing desync hence commenting out for now
        # if not label or label.lower() in {"sp", "sil", "spn", "<unk>"}:
        #     continue

        words.append(
            {"word": label, "start": float(start), "end": float(end)}
        )

    if not words:
        raise RuntimeError(
            f"No usable word intervals found in MFA JSON: {json_path}\n"
            f"(All were filtered or missing. Check if the JSON still contains <unk>.)"
        )

    return words


# -----------------------------
# Word grouping into readable lines
# -----------------------------
def chunk_words_into_lines(
    words: List[Dict[str, Any]],
    *,
    max_words_per_line: int = 7,
    max_line_duration: float = 3.5,
    max_gap: float = 0.35,
) -> List[List[Dict[str, Any]]]:
    """
    Groups word intervals into readable subtitle lines.
    Each group becomes one ASS Dialogue event with karaoke timing.
    """
    if not words:
        return []

    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = [words[0]]

    for w in words[1:]:
        prev = current[-1]
        gap = w["start"] - prev["end"]
        duration_if_added = w["end"] - current[0]["start"]

        too_many_words = len(current) >= max_words_per_line
        too_long = duration_if_added > max_line_duration
        too_big_gap = gap > max_gap

        if too_many_words or too_long or too_big_gap:
            lines.append(current)
            current = [w]
        else:
            current.append(w)

    if current:
        lines.append(current)

    return lines


# -----------------------------
# Karaoke ASS text builder
# -----------------------------
def make_karaoke_ass_text(words_line: List[Dict[str, Any]]) -> str:
    """
    Builds ASS karaoke timing tags using \\k (centiseconds).
    Example: {\\k12}Hello {\\k25}world
    """
    parts = []
    for w in words_line:
        dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
        parts.append(f"{{\\k{dur_cs}}}{w['word']}")
    return " ".join(parts)


# -----------------------------
# ASS generator
# -----------------------------
def generate_ass_karaoke(
    words: List[Dict[str, Any]],
    out_ass_path: str | Path,
    *,
    video_w: int = 1080,
    video_h: int = 1920,
    font: str = "Arial",
    font_size: int = 64,
    bottom_margin: int = 220,
    primary_color: str = "&H00FFFFFF",     # white
    secondary_color: str = "&H00999999",   # grey for non-highlighted words
    outline_color: str = "&H00000000",     # black outline
    outline: int = 3,
    shadow: int = 0,
    align: int = 2,  # bottom-center
    max_words_per_line: int = 4,
    max_line_duration: float = 2.5,
) -> Path:
    out_ass_path = Path(out_ass_path)
    out_ass_path.parent.mkdir(parents=True, exist_ok=True)

    lines = chunk_words_into_lines(
        words,
        max_words_per_line=max_words_per_line,
        max_line_duration=max_line_duration,
    )

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},{primary_color},{secondary_color},{outline_color},&H00000000,0,0,0,0,100,100,0,0,1,{outline},{shadow},{align},120,120,{bottom_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for words_line in lines:
        start = words_line[0]["start"]
        end = words_line[-1]["end"] + 0.05  # small padding
        text = make_karaoke_ass_text(words_line)

        events.append(
            f"Dialogue: 0,{sec_to_ass_time(start)},{sec_to_ass_time(end)},Default,,0,0,0,,{text}"
        )

    out_ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_ass_path



def generate_subtitles_from_mfa_json(
    mfa_json_path: str | Path,
    out_ass_path: str | Path,
    *,
    video_w: int = 1080,
    video_h: int = 1920,
) -> Path:
    words = load_words_from_mfa_json(mfa_json_path)
    return generate_ass_karaoke(
        words=words,
        out_ass_path=out_ass_path,
        video_w=video_w,
        video_h=video_h,
        align=1
    )


# -----------------------------
# Test runner
# -----------------------------
if __name__ == "__main__":
    print("Testing subtitle generation...")
    mfa_json_path = "build/mfa_output/audio.json"
    out_ass_path = "build/subtitles/test_narration.ass"
    generate_subtitles_from_mfa_json(
        mfa_json_path,
        out_ass_path,
        video_w=1080,
        video_h=1920,
    )
    print("Done, saved to:", out_ass_path)
