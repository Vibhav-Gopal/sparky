from __future__ import annotations
from typing import Optional
from typing import Union
from pathlib import Path
from typing import Dict, Any, Optional
import wave
import os
os.environ['KMP_DUPLICATE_LIB_OK']='True' # IDK why but adding this ignores a weird issue where libomp.dylib is loaded twice on MacOS, might cause issues
from TTS.api import TTS


def wav_duration_seconds(path: str) -> float:
    with wave.open(path, "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
    return frames / float(rate)


def build_narration_text(spec: Dict[str, Any]) -> str:
    """
    Combines all scene texts into one narration string.
    """
    parts = []
    for s in spec.get("scenes", []):
        t = (s.get("text") or "").strip()
        if not t:
            continue
        parts.append(t)

    return " ".join(parts)


class CoquiVoiceover:
    """
    Loads the Coqui TTS model once, then can generate voiceovers.
    This avoids re-loading the model for every run.
    """

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2", 
        device: Optional[str] = None,  # "cuda", "cpu"
    ):
        # device selection:
        # - if device is None, Coqui chooses automatically
        self.model_name = model_name
        self.tts = TTS(model_name=model_name, progress_bar=True, gpu=(device == "cuda"))

    def generate(
        self,
        spec: Dict[str, Any],
        out_wav_path: str | Path,
        *,
        speaker: Optional[str] = "Craig Gutsy",
        language: Optional[str] = "en",
    ) -> Path:
        """
        Generates narration.wav from the YAML spec.

        speaker/language are optional and only work if the model supports them, the default for this class supports it.
        """

        out_wav_path = Path(out_wav_path)
        out_wav_path.parent.mkdir(parents=True, exist_ok=True)

        text = build_narration_text(spec)
        if not text.strip():
            raise ValueError("No narration text found in spec scenes.")

        self.tts.tts_to_file(text=text, speaker=speaker, language=language, file_path=out_wav_path)

        return out_wav_path
    def generate_one(
        self,
        text: str,
        out_wav_path: str | Path,
        *,
        speaker: Optional[str] = "Craig Gutsy",
        language: Optional[str] = "en",
    ) -> Path:
        """
        Clone of above function but takes raw text instead of spec.
        """

        out_wav_path = Path(out_wav_path)
        out_wav_path.parent.mkdir(parents=True, exist_ok=True)

        if not text.strip():
            raise ValueError("No narration text found.")

        self.tts.tts_to_file(text=text, speaker=speaker, language=language, file_path=out_wav_path)

        return out_wav_path

if __name__ == "__main__":
    print("Testing TTS model...")
    testmodel = CoquiVoiceover()
    print(testmodel.tts.speakers)
    for spk in testmodel.tts.speakers:
        print("Speaker:", spk)

        out_wav = testmodel.generate(
            spec={
                "scenes": [
                    {"id": "s1", "text": "Hello, this is a test."},
                    {"id": "s2", "text": "This is the second scene."},
                ]
            },
            out_wav_path=f"build/audio/test_narration_{spk}.wav",
            speaker=spk,
            # language=None,
        )
    print("Done")