# prompt_enhance.py
from __future__ import annotations

import json
from typing import Optional


LLM_MODEL = "llama3.1:8b"  # or local model name


SYSTEM_PROMPT = """You are a visual specification engine for Stable Diffusion.

Your job is NOT to rewrite text lightly.
Your job is to expand a short BASE_PROMPT into a highly visual, shot-specific, generation-friendly prompt.

CRITICAL HARD LIMIT:
- Output must be ONE single line
- Output must be UNDER 55 WORDS total
- If you exceed 55 words, you failed

Hard requirement:
- Your output must be a NON-TRIVIAL enhancement.
- It must add concrete visual detail that was not explicitly present.
- If your output is too similar to BASE_PROMPT, you failed.

You will receive:
- BASE_PROMPT: what the image should convey
- GLOBAL_STYLE: optional aesthetic direction
- ASPECT_RATIO: typically 9:16 vertical

You MUST preserve:
- the core subject(s)
- the core concept/metaphor/message
- the intent/mood

You MUST add explicit details (as applicable):
- Subject form + surface texture/materials
- Background environment + atmosphere
- Composition: close/medium/wide, foreground/midground/background separation
- Camera angle + lens feel (wide/tele)
- Lighting: key light direction, rim light, volumetric light, contrast, color temperature
- Color palette: 3–6 colors (dominant + accents)
- Mood via visuals (not abstract “mystical vibes”)
- Realism/stylization level

You MUST NOT:
- Add unrelated main subjects
- Add readable text/logos/watermarks/UI

OUTPUT RULES (STRICT):
- Output exactly ONE single-line prompt
- No lists, no markdown, no JSON, no quotes, no explanation
- Explicitly mention no duplicate objects and no splitscreen in the final output.
"""

"""
# FIXED QUALITY TAIL (always append at the end of the prompt):
# cinematic lighting, ultra-detailed, sharp focus, high dynamic range, volumetric lighting, soft shadows, depth of field, film grain, professional color grading, 8k, masterpiece, no text, no watermark, no logo
"""


# ---------- LLM CALL ----------
def call_llm(system_prompt: str, user_prompt: str, *, seed: int | None = None, temperature: float | None = None) -> str:
    from ollama import chat
    from ollama import ChatResponse
    options = {}
    if seed is not None:
        options["seed"] = int(seed)
    if temperature is not None:
        options["temperature"] = float(temperature)
    response: ChatResponse = chat(model=LLM_MODEL, messages=[
        {
            'role': 'system',
            'content': system_prompt,
        },
        {
            'role': 'user',
            'content': user_prompt,
        },

    ], options=options if options else None)
    return response['message']['content']



def enhance(
    prompt: str,
    *,
    style: str = "",
    aspect_ratio: str = "9:16",
    model: str = LLM_MODEL,
    temperature: float = 0.4,
    seed: Optional[int] = None,
    max_len: int = 380,
    debug: bool = False,
) -> str:
    """
    Enhance a basic prompt into an SD-friendly prompt.

    Returns a single-line enhanced prompt string.
    Falls back to original prompt on failure.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return ""

    style = (style or "").strip()
    aspect_ratio = (aspect_ratio or "9:16").strip()


    user_prompt = f"""
ASPECT_RATIO: {aspect_ratio}
GLOBAL_STYLE: {style if style else "(none)"}

BASE_PROMPT:
{prompt}

Return a significantly more detailed Stable Diffusion prompt.
You MUST add: camera framing, lens look, lighting direction, color palette, and composition depth.
Return ONE line under 55 words.
""".strip()
    try:
        out = call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=temperature,
            seed=seed,
        )

        # Clean + enforce one line
        out = " ".join(out.split())

        # Guardrails: if model outputs junk
        if not out or len(out) < 8:
            return prompt


        return out

    except Exception as e:
        print("⚠️ prompt enhancement failed, using original prompt")
        if debug:
            print(f"Error: {e}")
        # fallback: just use original
        return prompt
if __name__ == "__main__":
    print("Testing prompt enhancement...")
    prompt = "A vast view of outer space with swirling galaxies and glowing nebulae, stars scattered across deep darkness, subtle light flares illuminating cosmic dust, dramatic lighting emphasizing scale and mystery, no text or symbols, cinematic"
    enhanced_prompt = enhance(prompt,debug=True)
    print("Original prompt:", prompt)
    print("Enhanced prompt:", enhanced_prompt)