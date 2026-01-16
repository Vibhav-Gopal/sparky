# Sparky

An end-to-end **local** content pipeline that converts a single idea prompt into a short-form video:

**Idea prompt (script_prompt.txt) → YAML Director's script → AI images → TTS voiceover → word-level karaoke subtitles → final video**

Designed for repeatable YouTube Shorts / Reels style generation with a modular architecture.

Refer to `samples/` directory for sample inputs and outputs

---

## Features

- ✅ **Script → YAML generator** (`script_gen.py`)
- ✅ **Scene-based video spec** (`video.yaml`)
- ✅ **AI image generation** (Stable Diffusion 1.5 via `diffusers`)
- ✅ **Optional prompt enhancement** using local LLM (`prompt_enhance.py`)
- ✅ **Voiceover narration** via Coqui TTS (`audio_gen.py`)
- ✅ **Word-level alignment** via Montreal Forced Aligner (MFA)
- ✅ **Karaoke subtitles** (`.ass`) generated from MFA timestamps (`subtitles_gen.py`)
- ✅ **Video compositor**
  - per-scene clip rendering 
  - crossfade slideshow
  - audio mux
  - subtitle burn-in (`compositor.py`)
- ✅ Versioning system: `versions/video_vX.yaml`

---

## Project Structure
```bash

.
├── align_mfa.py
├── audio_gen.py
├── compositor.py
├── environment.yml
├── feedback_llm.py
├── feedback.txt
├── image_gen.py
├── pipeline.py
├── prompt_enhance.py
├── README.md
├── requirements.txt
├── sample_output
│   ├── feedback.txt
│   ├── final.mp4
│   ├── video_patch.yaml
│   └── video.yaml
├── schemas.py
├── script_gen.py
├── script_prompt.txt
└── subtitles_gen.py
```

---

## Pipeline Flow (Stages)

### Stage 0 — Script generation
- Input: `script_prompt.txt`
- Runs: `script_gen.py`
- Output: `video.yaml`

### Stage 1 — Spec versioning + build spec
- Copies root `video.yaml` → `versions/video_vX.yaml`
- Copies latest version → `build/video.yaml`

### Stage 2 — Feedback patching (optional)
- Input: `feedback.txt`
- Runs: `feedback_llm.py` → produces `build/video_patch.yaml`
- `schemas.py` merges patch → overwrites `build/video.yaml`

### Stage 3 — Image generation
- Reads: `build/video.yaml`
- Generates: `build/images/sX.png` (Stable Diffusion)

### Stage 4 — Audio generation
- Generates per-scene wav files:
  - `build/audio/scenes/sX.wav`
- Concatenates to:
  - `build/audio.wav`

### Stage 5 — Forced alignment
- MFA aligns:
  - `build/mfa_input/audio.wav` + `build/mfa_input/audio.txt`
- Outputs:
  - `build/mfa_output/audio.json`

### Stage 6 — Subtitles
- Converts MFA JSON → `.ass` karaoke subtitles:
  - `build/subtitles.ass`

### Stage 7 — Compositing
- Creates per-scene motion clips → `build/clips/sX.mp4`
- Crossfades into slideshow → `build/slideshow.mp4`
- Adds audio → `build/slideshow_with_audio.mp4`
- If BGM enabled → `build/before_bgm.mp4`
- Final output → `build/final.mp4`

---

## Requirements

### Python
- Python 3.11

### External tools
- **FFmpeg**
- **Montreal Forced Aligner (MFA)**
- **Ollama** 

### Hardware notes
- Tested on **Mac Apple Silicon** (MPS)
- SD 1.5 is chosen.

---

## Setup
There are two environemts to be setup, one for the BGM generation and one for the rest of the pipeline, if `BGM_ENABLED` is set to `False`, the second environment need not be setup.

- Be on Python 3.11
- Create a `conda` environment following `environment.yml`
- Install `pip` dependencies given in `requirements.txt`
- Install `ollama` and download model(s)
- Install `ffmpeg`
- Activate `conda` env

The above setup is necessary, below is an optional setup to enable BGM generation.

- Create a `conda` environment with `python3.9` named `audiocraftenv`, the environment name should not be changed (`conda create -n audiocraftenv python=3.9 -y`)
- Clone and install [Audiocraft](https://github.com/facebookresearch/audiocraft.git) module. (Create an issue if you come across any hiccups with installation and I'll release a forked version with a few fixes)


---

## Quickstart

- Follow `Setup` section
- Give input idea in `script_prompt.txt`
- Run `pipeline.py`
- Check output in `build/` directory
- If feedback needs to be given, add natural language feedback in `feedback.txt` and rerun `pipeline.txt`

---
## What is left?
Frankly this is nowhere near a fully finished commercial grade project, I picked this up as a side project, here are a few improvements that I have in mind, you are free to suggest more if you have any.
- Visual updates to font (location, size, style, color, etc)
- Better Image generation models
- Better LLM models
- Ability to do partial re-runs (eg: skipping image gen)
- Adding variables to set TTS voices and models in the top file
- The `aspect_ratio` parameter in the `.yaml` file is useless as of now, need to add ability to scale directly from `.yaml` file
- Many hacky redundant variables and forces, need to refractor and prune (Eg: why force font at render time when you can give the font directly at generation time? because i forgot about that until the end)

Incase of any issues with running or weird bugs, open an issue and I'll get to it as soon as I can :)

---
# Disclaimer
This project generates synthetic media, and I am not responsible for what you create with this and also do not take any responsibility to the outcomes/consequences of your actions. The onus is on you to use this project responsibly.

---

If you made it till here, thanks :)