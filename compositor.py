# compositor.py
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, Any, List

ALLOWED_MOTIONS = {"slow_zoom", "pan_left", "pan_right", "static"}


def _run(cmd: List[str]) -> None:
    subprocess.run(cmd, check=True)


def _scene_motion_vf(
    motion: str,
    duration: float,
    *,
    out_w: int,
    out_h: int,
    fps: int,
) -> str:
    """
    FFmpeg -vf filter string that creates a moving clip from a still image.
    Output is guaranteed CFR and correct resolution.
    """
    motion = (motion or "slow_zoom").strip()
    if motion not in ALLOWED_MOTIONS:
        motion = "slow_zoom"

    frames = max(1, int(round(duration * fps)))

    # upscale slightly for pan/zoom headroom
    scale_w = int(out_w * 1.15)
    scale_h = int(out_h * 1.15)

    base = (
        f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
        f"crop={scale_w}:{scale_h},"
    )

    if motion == "static":
        vf = (
            f"{base}"
            f"scale={out_w}:{out_h},"
            f"fps={fps},format=yuv420p"
        )
        return vf

    if motion == "slow_zoom":
        vf = (
            f"{base}"
            f"zoompan="
            f"z='min(1.08,1.0+0.08*on/{frames})':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={frames}:"
            f"s={out_w}x{out_h}:"
            f"fps={fps},"
            f"fps={fps},format=yuv420p"
        )
        return vf

    if motion == "pan_left":
        vf = (
            f"{base}"
            f"zoompan="
            f"z='1.03':"
            f"x='max(0,(iw-iw/zoom)*(1-on/{frames}))':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={frames}:"
            f"s={out_w}x{out_h}:"
            f"fps={fps},"
            f"fps={fps},format=yuv420p"
        )
        return vf

    if motion == "pan_right":
        vf = (
            f"{base}"
            f"zoompan="
            f"z='1.03':"
            f"x='max(0,(iw-iw/zoom)*(on/{frames}))':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={frames}:"
            f"s={out_w}x{out_h}:"
            f"fps={fps},"
            f"fps={fps},format=yuv420p"
        )
        return vf

    # fallback
    return f"{base}scale={out_w}:{out_h},fps={fps},format=yuv420p"


def _render_scene_clip(
    img_path: Path,
    out_clip: Path,
    *,
    duration: float,
    motion: str,
    width: int,
    height: int,
    fps: int,
) -> None:
    out_clip.parent.mkdir(parents=True, exist_ok=True)

    vf = _scene_motion_vf(
        motion=motion,
        duration=duration,
        out_w=width,
        out_h=height,
        fps=fps,
    )

    # output CFR clip, exact duration
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(img_path),
        "-t", str(duration),
        "-vf", vf,
        "-r", str(fps),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(out_clip),
    ]
    _run(cmd)


def _xfade_clips(
    clip_paths: List[Path],
    durations: List[float],
    out_path: Path,
    *,
    fps: int,
    crossfade_dur: float,
) -> None:
    """
    Crossfade N mp4 clips using xfade.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    inputs: List[str] = []
    for p in clip_paths:
        inputs += ["-i", str(p)]

    n = len(clip_paths)
    if n == 1:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip_paths[0]),
            "-c:v", "copy",
            str(out_path),
        ]
        _run(cmd)
        return

    # Build filtergraph: [0:v][1:v]xfade... and then chain
    # Offsets based on timeline
    parts = []
    offset = max(0.0, durations[0] - crossfade_dur)
    parts.append(f"[0:v][1:v]xfade=transition=fade:duration={crossfade_dur}:offset={offset}[v1]")

    timeline = durations[0]
    cur = "v1"

    for i in range(2, n):
        timeline = timeline + durations[i - 1] - crossfade_dur
        offset = max(0.0, timeline - crossfade_dur)
        nxt = f"v{i}"
        parts.append(f"[{cur}][{i}:v]xfade=transition=fade:duration={crossfade_dur}:offset={offset}[{nxt}]")
        cur = nxt

    parts.append(f"[{cur}]fps={fps},format=yuv420p[vout]")
    filter_complex = ";".join(parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-r", str(fps),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    _run(cmd)

def override_ass_style(
    in_ass: Path,
    out_ass: Path,
    *,
    fontname: str = "Montserrat",
    fontsize: int = 72,
    margin_v: int = 220,
    outline: int = 4,
    shadow: int = 0,
    bold: int = 1,
):
    """
    Modifies the 'Style: Default,...' line in the ASS file.
    """
    txt = in_ass.read_text(encoding="utf-8")

    def repl_style_line(line: str) -> str:
        # ASS style format used:
        # Style: Default,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
        if not line.startswith("Style: Default,"):
            return line

        parts = line.split(",")
        # parts[0] = "Style: Default"
        # parts[1] = Fontname
        # parts[2] = Fontsize
        # parts[7] = Bold
        # parts[17] = Outline
        # parts[18] = Shadow
        # parts[21] = MarginV

        if len(parts) < 23:
            return line  # unexpected format, keep it unchanged

        parts[1] = fontname
        parts[2] = str(fontsize)
        parts[7] = str(bold)
        parts[17] = str(outline)
        parts[18] = str(shadow)
        parts[21] = str(margin_v)

        return ",".join(parts)

    out_lines = []
    for line in txt.splitlines():
        out_lines.append(repl_style_line(line))

    out_ass.parent.mkdir(parents=True, exist_ok=True)
    out_ass.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def compose_final_video(
    spec: Dict[str, Any],
    *,
    images_dir: str | Path = "build/images",
    audio_wav: str | Path = "build/audio.wav",
    subtitles_ass: str | Path = "build/subtitles.ass",
    out_path: str | Path = "build/final.mp4",
    work_dir: str | Path = "build",
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    crossfade_dur: float = 0.45,
    fontname: str | None = None,
    fontsize: int | None = None,
    margin_v: int | None = None,
    outline: int | None = None,
    shadow: int | None = None,
    bgm_enabled: bool = False,
    bgm_output: Path | None = None
) -> Path:
    scenes = spec.get("scenes", [])
    if not scenes:
        raise ValueError("Spec has no scenes.")

    images_dir = Path(images_dir)
    audio_wav = Path(audio_wav)
    subtitles_ass = Path(subtitles_ass)
    out_path = Path(out_path)
    work_dir = Path(work_dir)

    clips_dir = work_dir / "clips"
    slideshow_mp4 = work_dir / "slideshow.mp4"
    av_mp4 = work_dir / "slideshow_with_audio.mp4"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not audio_wav.exists():
        raise FileNotFoundError(f"Missing audio file: {audio_wav}")
    if not subtitles_ass.exists():
        raise FileNotFoundError(f"Missing subtitles file: {subtitles_ass}")

    # 1) Render each scene as its own CFR mp4
    clip_paths: List[Path] = []
    durations: List[float] = []

    for s in scenes:
        sid = s["id"]
        dur = float(s["duration"])
        durations.append(dur)

        img_path = images_dir / f"{sid}.png"
        if not img_path.exists():
            raise FileNotFoundError(f"Missing scene image: {img_path}")

        motion = (s.get("visual") or {}).get("motion") or "slow_zoom"
        clip_path = clips_dir / f"{sid}.mp4"

        _render_scene_clip(
            img_path=img_path,
            out_clip=clip_path,
            duration=dur,
            motion=motion,
            width=width,
            height=height,
            fps=fps,
        )

        clip_paths.append(clip_path)

    # 2) Crossfade clips into slideshow.mp4
    _xfade_clips(
        clip_paths=clip_paths,
        durations=durations,
        out_path=slideshow_mp4,
        fps=fps,
        crossfade_dur=crossfade_dur,
    )

    # 3) Add narration audio
    cmd_audio = [
        "ffmpeg", "-y",
        "-i", str(slideshow_mp4),
        "-i", str(audio_wav),
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(av_mp4),
    ]
    _run(cmd_audio)

    # # 4) Burn subtitles with forced font

    subtitles_for_burn = subtitles_ass

    # Only override ASS styling if requested (pipeline passed overrides)
    if (
        fontname is not None
        or fontsize is not None
        or margin_v is not None
        or outline is not None
        or shadow is not None
    ):
        subtitles_for_burn = work_dir / "subtitles_for_burn.ass"

        override_ass_style(
            in_ass=subtitles_ass,
            out_ass=subtitles_for_burn,
            fontname=fontname or "Arial",
            fontsize=fontsize or 64,
            margin_v=margin_v or 300,
            outline=outline or 3,
            shadow=shadow or 0,
            bold=1,
        )

    vf_subs = f"ass={subtitles_for_burn}"

    if bgm_enabled: bgm_before_fin = work_dir / "before_bgm.mp4"
    cmd_subs = [
        "ffmpeg", "-y",
        "-i", str(av_mp4),
        "-vf", vf_subs,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(out_path) if not bgm_enabled else str(bgm_before_fin),
    ]
    _run(cmd_subs)

    if bgm_enabled:
        if not bgm_output:
            raise ValueError("BGM output path must be specified when BGM is enabled.")
        cmd_add_bgm = [
            "ffmpeg", "-i", str(bgm_before_fin), "-i", str(bgm_output), "-filter_complex", "[0:a]volume=1[fg]; [1:a]volume=0.2[bg]; [fg][bg]amix=inputs=2:duration=longest","-c:v", "copy", str(out_path)
        ]
        _run(cmd_add_bgm)

    return out_path
