# pipeline.py
from __future__ import annotations
import warnings
warnings.filterwarnings("ignore") # Because I like to live dangerously

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
import time

from script_gen import generate_script
from feedback_llm import generate_patch, call_llm
from prompt_enhance import enhance
from schemas import merge_video_spec_with_patch
from image_gen import ImageGenerator
from audio_gen import CoquiVoiceover, wav_duration_seconds
from subtitles_gen import generate_subtitles_from_mfa_json
from compositor import compose_final_video

#TODO control audio gen settinfgs from here too
#TODO control image gen settinfgs for model from here
# =============================================================================
# CONFIG (top-level knobs)
# =============================================================================

BASE_SEED = 1337
RANDOMIZE_SEED = False  # if True -> BASE_SEED + unix time

# Image generation
SD_WIDTH = 720
SD_HEIGHT = 1280
SD_STEPS = 9
SD_GUIDANCE = 0.0

# Video
OUT_W = 1080
OUT_H = 1920
FPS = 30
CROSSFADE_DUR = 0.45

# Subtitle style forced in compositor
OVERRIDE_SUBTITLE_STYLE = False
FORCE_FONTNAME = "Montserrat"
FORCE_FONTSIZE = 32
SUB_FONTNAME = FORCE_FONTNAME
SUB_FONTSIZE = FORCE_FONTSIZE
SUB_MARGIN_V = 360
SUB_OUTLINE = 4
SUB_SHADOW = 0

# =============================================================================
# PATHS AND FLAGS
# =============================================================================
REGEN_ROOT_YAML = False
SCRIPT_YAML_ONLY = False
INTERACTIVE_MODE = False # For starting interactive chat with LLM to get ideas, doesn't run full pipeline

ROOT = Path(".")
BUILD = ROOT / "build"
VERSIONS = ROOT / "versions"

SCRIPT_PROMPT = ROOT / "script_prompt.txt"
SCRIPT_OUTPUT = ROOT / "video.yaml"
ROOT_VIDEO_YAML = ROOT / "video.yaml"
ROOT_FEEDBACK_TXT = ROOT / "feedback.txt"

BUILD_VIDEO_YAML = BUILD / "video.yaml"
BUILD_PATCH_YAML = BUILD / "video_patch.yaml"

IMAGES_DIR = BUILD / "images"
SUB_DIR = BUILD / "subtitles"
MFA_IN = BUILD / "mfa_input"
MFA_OUT = BUILD / "mfa_output"
AUDIO_SCENES_DIR = BUILD / "audio" / "scenes"

AUDIO_WAV = BUILD / "audio" / "audio.wav"
SUB_ASS = BUILD / "subtitles" / "subtitles.ass"
FINAL_MP4 = BUILD / "final.mp4"


# =============================================================================
# Utils
# =============================================================================

def now_seed(base_seed: int, randomize: bool) -> int:
    if not randomize:
        return int(base_seed)
    return int(base_seed + int(time.time()))


def load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def save_yaml(obj: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            obj,
            f,
            sort_keys=False,
            allow_unicode=True,
            width=100000,
        )


def normalize_transcript(text: str) -> str:
    """
    MFA-friendly transcript:
    - lowercase
    - remove punctuation
    - keep apostrophes
    - collapse whitespace
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_transcript_from_spec(spec: Dict[str, Any]) -> str:
    parts = []
    for s in spec.get("scenes", []):
        t = (s.get("text") or "").strip()
        if t:
            parts.append(t)
    return " ".join(parts)


def ensure_dirs() -> None:
    BUILD.mkdir(exist_ok=True)
    shutil.rmtree(BUILD, ignore_errors=True)
    BUILD.mkdir(exist_ok=True)
    VERSIONS.mkdir(exist_ok=True)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    SUB_DIR.mkdir(parents=True, exist_ok=True)
    MFA_IN.mkdir(parents=True, exist_ok=True)
    MFA_OUT.mkdir(parents=True, exist_ok=True)


def _next_version_number() -> int:
    """
    versions/video_v1.yaml, video_v2.yaml, ...
    """
    existing = sorted(VERSIONS.glob("video_v*.yaml"))
    if not existing:
        return 1

    best = 0
    for p in existing:
        m = re.match(r"video_v(\d+)\.yaml$", p.name)
        if m:
            best = max(best, int(m.group(1)))
    return best + 1


def create_versioned_yaml_from_root() -> Path:
    """
    Reads ROOT/video.yaml and writes versions/video_vX.yaml
    Returns the path to the created version file.
    """
    if not ROOT_VIDEO_YAML.exists():
        raise FileNotFoundError(f"Missing: {ROOT_VIDEO_YAML}")

    spec = load_yaml(ROOT_VIDEO_YAML)
    vnum = _next_version_number()
    out_path = VERSIONS / f"video_v{vnum}.yaml"
    save_yaml(spec, out_path)

    print(f"[pipeline] versioned spec created: {out_path}")
    return out_path


def copy_latest_version_to_build(latest_version_path: Path) -> None:
    """
    Copies versions/video_vX.yaml -> build/video.yaml (canonical build spec)
    """
    BUILD.mkdir(exist_ok=True)
    shutil.copy(latest_version_path, BUILD_VIDEO_YAML)
    print(f"[pipeline] build spec updated: {BUILD_VIDEO_YAML}")

def start_interactive_chat():
    """
    Start an interactive chat session with the LLM for feedback.
    """
    print("Starting interactive chat session. Type 'exit' to quit.")
    system_prompt = "You are a helpful assistant for generating video scripts and video ideas for short form video content, science explainer style. Do not use any formatting in your responses, just plain text."
    print("Hi, what do you need help with today? I can give you ideas or anything else if you want.")
    while True:
        user_input = input("User: ")
        if user_input.lower() == 'exit':
            print("Exiting chat session.")
            exit()
        print("Thinking...")
        response = call_llm(system_prompt, user_input)
        print(f"LLM: {response}")
# =============================================================================
# Stage A: Generate patch from feedback (optional)
# =============================================================================

def run_feedback_llm_if_present(seed: int | None = None, temperature: float | None = None) -> None:
    """
    If feedback.txt exists, generate build/video_patch.yaml using feedback_llm.py
    """
    if not ROOT_FEEDBACK_TXT.exists():
        print("[pipeline] no feedback.txt found, skipping feedback patch generation")
        return

    feedback = ROOT_FEEDBACK_TXT.read_text(encoding="utf-8").strip()
    if not feedback:
        print("[pipeline] feedback.txt empty, skipping feedback patch generation")
        return



    print("[pipeline] running feedback_llm.py ...")
    generate_patch(seed=seed, temperature=temperature)

    if BUILD_PATCH_YAML.exists():
        print(f"[pipeline] patch generated: {BUILD_PATCH_YAML}")
        print(f"[pipeline] feedback used:\n{feedback}")
        print(f"[pipeline] Clearing feedback.txt ...")
        open(ROOT_FEEDBACK_TXT, "w").close()  # clear feedback after use
    else:
        print("[pipeline] WARNING: feedback_llm did not produce video_patch.yaml")


# =============================================================================
# Stage B: Merge build/video.yaml + build/video_patch.yaml -> build/video.yaml
# =============================================================================

def merge_patch_into_build_video() -> Dict[str, Any]:
    """
    Loads build/video.yaml, merges build/video_patch.yaml if present,
    and writes back into build/video.yaml (so build/video.yaml becomes final spec).
    """
    spec = load_yaml(BUILD_VIDEO_YAML)

    if BUILD_PATCH_YAML.exists():
        patch = load_yaml(BUILD_PATCH_YAML)
        new_spec, summary = merge_video_spec_with_patch(spec, patch, strict=False)
        print("[pipeline] patch merge summary:", summary)
        save_yaml(new_spec, BUILD_VIDEO_YAML)  # overwrite build spec
        return new_spec

    print("[pipeline] no build/video_patch.yaml found, using build/video.yaml as-is")
    return spec


# =============================================================================
# Stage 1: Images
# =============================================================================

def run_images(spec: Dict[str, Any], seed: int, debug: bool = False) -> None:
    print("[pipeline] generating images...")

    gen = ImageGenerator()

    for idx, s in enumerate(spec["scenes"]):
        sid = s["id"]
        prompt = s["visual"]["prompt"]
        out_path = IMAGES_DIR / f"{sid}.png"

        # Derive per-scene seed so each scene is stable but different
        scene_seed = seed + idx
        enhanced_prompt = enhance(prompt, seed=scene_seed, style="artstation", debug=debug)
        if debug : print(f"[pipeline] scene {sid}: seed={scene_seed}, prompt='{prompt}, revised_prompt='{enhanced_prompt}'")
        gen.generate(
            prompt=enhanced_prompt,
            out_path=out_path,
            width=SD_WIDTH,
            height=SD_HEIGHT,
            steps=SD_STEPS,
            guidance=SD_GUIDANCE,
            seed=scene_seed,  # if you want randomness -> set seed=None
        )

        print(f"[pipeline] image done: {out_path}")


# =============================================================================
# Stage 2: Audio (Coqui)
# =============================================================================

def pick_tts_device() -> str:
    """
    Prefer MPS on Mac, else CUDA, else CPU.
    (Your audio_gen.py should accept this string.)
    """
    try:
        import torch
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def run_tts(spec: Dict[str, Any]) -> None:
    print("[pipeline] generating voiceover...")

    vo = CoquiVoiceover()
    vo.generate(
        spec=spec,
        out_wav_path=AUDIO_WAV,
    )

    print("[pipeline] voiceover saved:", AUDIO_WAV)

def run_tts_per_scene(spec):
    AUDIO_SCENES_DIR.mkdir(parents=True, exist_ok=True)

    vo = CoquiVoiceover(model_name="tts_models/multilingual/multi-dataset/xtts_v2", device=pick_tts_device())

    durations = {}

    for scene in spec["scenes"]:
        sid = scene["id"]
        text = scene["text"]
        out_wav = AUDIO_SCENES_DIR / f"{sid}.wav"

        vo.generate_one(text=text, out_wav_path=out_wav)
        durations[sid] = wav_duration_seconds(str(out_wav))

    return durations

def concat_audio_wavs(scene_ids):
    list_file = Path("audio_list.txt")
    lines = []
    for sid in scene_ids:
        lines.append(f"file '{(AUDIO_SCENES_DIR / f'{sid}.wav').as_posix()}'")

    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    subprocess.run([
        "ffmpeg","-y",
        "-f","concat","-safe","0",
        "-i", str(list_file),
        "-c","copy",
        str(AUDIO_WAV)
    ], check=True)
# =============================================================================
# Stage 3: MFA prep + align
# =============================================================================

def prepare_mfa_input(spec: Dict[str, Any]) -> None:
    print("[pipeline] preparing MFA input...")

    MFA_IN.mkdir(parents=True, exist_ok=True)

    # Transcript
    transcript = normalize_transcript(build_transcript_from_spec(spec))
    (MFA_IN / "audio.txt").write_text(transcript + "\n", encoding="utf-8")
    print("[pipeline] MFA transcript:", transcript)

    # Resample audio to 16k mono PCM s16le
    out_audio = MFA_IN / "audio.wav"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(AUDIO_WAV),
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(out_audio),
    ]
    subprocess.run(cmd, check=True)
    print("[pipeline] MFA audio:", out_audio)


def run_mfa_align() -> Path:
    print("[pipeline] running MFA align...")

    # Make sure models exist
    subprocess.run(["mfa", "model", "download", "dictionary", "english_us_arpa"], check=True)
    subprocess.run(["mfa", "model", "download", "acoustic", "english_us_arpa"], check=True)

    # Fresh output
    if MFA_OUT.exists():
        shutil.rmtree(MFA_OUT)
    MFA_OUT.mkdir(parents=True, exist_ok=True)

    # mfa align <corpus> english_us_arpa english_us_arpa <out>
    cmd = [
        "mfa", "align",
        str(MFA_IN),
        "english_us_arpa",
        "english_us_arpa",
        str(MFA_OUT),
        "--clean",
        "--output_format", "json",
        "--single_speaker",
    ]
    subprocess.run(cmd, check=True)

    json_path = MFA_OUT / "audio.json"
    if not json_path.exists():
        raise FileNotFoundError(f"MFA did not produce expected output: {json_path}")

    print("[pipeline] MFA JSON:", json_path)
    return json_path


# =============================================================================
# Stage 4: Subtitles
# =============================================================================

def run_subtitles(mfa_json_path: Path) -> None:
    print("[pipeline] generating subtitles (.ass)...")

    generate_subtitles_from_mfa_json(
        mfa_json_path=str(mfa_json_path),
        out_ass_path=str(SUB_ASS),
        video_w=OUT_W,
        video_h=OUT_H,
    )

    print("[pipeline] subtitles saved:", SUB_ASS)


# =============================================================================
# Stage 5: Compose final video
# =============================================================================

def run_compositor(spec: Dict[str, Any]) -> None:
    print("[pipeline] composing final video...")

    kwargs = dict(
        spec=spec,
        images_dir=IMAGES_DIR,
        audio_wav=AUDIO_WAV,
        subtitles_ass=SUB_ASS,
        out_path=FINAL_MP4,
        width=OUT_W,
        height=OUT_H,
        fps=FPS,
        crossfade_dur=CROSSFADE_DUR,
    )

    if OVERRIDE_SUBTITLE_STYLE:
        kwargs.update(
            fontname=SUB_FONTNAME,
            fontsize=SUB_FONTSIZE,
            margin_v=SUB_MARGIN_V,
            outline=SUB_OUTLINE,
            shadow=SUB_SHADOW,
        )

    compose_final_video(**kwargs)

    print("[pipeline] final video saved:", FINAL_MP4)


# =============================================================================
# Main
# =============================================================================

def main():
    # Temporary workaround for OpenMP lib duplication issues (macOS conda)
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    seed = now_seed(BASE_SEED, RANDOMIZE_SEED)
    ensure_dirs()

    if INTERACTIVE_MODE: start_interactive_chat()
 
    # Generate Script yaml from prompt
    if REGEN_ROOT_YAML or (not ROOT_VIDEO_YAML.exists()) : print("[pipeline] regenerating script YAML...") ;generate_script(input_fpath=Path(SCRIPT_PROMPT), output_yaml_path=Path(SCRIPT_OUTPUT), seed=seed, temperature=0.7)
    if SCRIPT_YAML_ONLY:
        print("\n[pipeline] ✅ DONE (script YAML only)")
        return
    

    # 0) Versioning: create versions/video_vX.yaml from ROOT/video.yaml
    latest_version = create_versioned_yaml_from_root()

    # 1) Copy latest version into build/video.yaml
    copy_latest_version_to_build(latest_version)

    # 2) Generate patch from feedback (optional)
    run_feedback_llm_if_present(seed=BASE_SEED, temperature=1.0)

    # 3) Merge patch into build/video.yaml (final spec lives in build/video.yaml)
    spec = merge_patch_into_build_video()


    
    print(f"[pipeline] seed = {seed} (BASE_SEED={BASE_SEED}, RANDOMIZE_SEED={RANDOMIZE_SEED})")

    # 4) Generate images
    run_images(spec, seed=seed,debug=True)

    # # 5) Generate audio
    durations = run_tts_per_scene(spec)

    # overwrite YAML durations
    for s in spec["scenes"]:
        s["duration"] = round(durations[s["id"]] + 0.45, 2)  # compensating for crossfade
    scene_ids = [s["id"] for s in spec["scenes"]]
    concat_audio_wavs(scene_ids)

    # save_yaml(spec, Path(ROOT/"test.yaml"))  # save updated durations

    # 6) MFA alignment JSON
    prepare_mfa_input(spec)
    mfa_json = run_mfa_align()

    # 7) Karaoke subtitles
    run_subtitles(mfa_json)

    # 8) Compose final video
    run_compositor(spec)

    print("\n[pipeline] ✅ DONE")
    print("[pipeline] Final output:", FINAL_MP4)


if __name__ == "__main__":
    start_time = time.time()
    main()
    end_time = time.time()
    print(f"[pipeline] Total time taken: {end_time - start_time:.2f} seconds")
