# align_mfa.py
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any

import re

def normalize_transcript(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s']", " ", text)  # keep words + apostrophes
    text = re.sub(r"\s+", " ", text).strip()
    return text

def build_transcript_from_yaml(spec: Dict[str, Any]) -> str:
    # any abbreviations or special words will break, need to add fix #TODO
    return " ".join(scene["text"].strip() for scene in spec["scenes"] if scene.get("text"))


def prepare_mfa_input(audio_wav: str | Path, transcript_text: str, out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    wav_path = out_dir / "audio.wav"
    txt_path = out_dir / "audio.txt"

    shutil.copy(audio_wav, wav_path)
    txt_path.write_text(transcript_text, encoding="utf-8")

    return out_dir


def run_mfa_align(
    mfa_input_dir: str | Path,
    mfa_output_dir: str | Path,
    *,
    dictionary: str = "english_us_arpa",
    acoustic_model: str = "english_mfa",
    use_json: bool = True,
):
    mfa_input_dir = Path(mfa_input_dir)
    mfa_output_dir = Path(mfa_output_dir)
    mfa_output_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["mfa", "align", str(mfa_input_dir), dictionary, acoustic_model, str(mfa_output_dir)]

    if use_json:
        cmd += ["--output_format", "json"]
    cmd += [" --single_speaker"]
    subprocess.run(cmd, check=True)

    # Expected output
    json_path = mfa_output_dir / "audio.json"
    textgrid_path = mfa_output_dir / "audio.TextGrid"

    if use_json and json_path.exists():
        return json_path
    if textgrid_path.exists():
        return textgrid_path

    raise RuntimeError("MFA did not produce expected output (audio.json or audio.TextGrid).")

if __name__ == "__main__":
    print("Testing MFA alignment...")
    # Example usage
    spec={
        "scenes": [
            {"id": "s1", "text": "Hello, this is a test."},
            {"id": "s2", "text": "This is the second scene."},
        ]
    }

    transcript = normalize_transcript(build_transcript_from_yaml(spec))
    mfa_input_dir = prepare_mfa_input("build/audio/test_narration.wav", transcript, "build/mfa_input")
    mfa_output = run_mfa_align(mfa_input_dir, "build/mfa_output", use_json=True)
    print("MFA output saved to:", mfa_output)