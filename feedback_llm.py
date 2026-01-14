import yaml
from pathlib import Path

# ---------- CONFIG ----------
LLM_MODEL = "llama3.1:8b"  # or anyother model name
PATCH_OUTPUT = Path("build/video_patch.yaml")

# ---------- LLM CALL FUNCTION ----------
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


# ---------- MAIN CODE ----------
def generate_patch(video_spec_path="build/video.yaml", feedback_path="feedback.txt", seed: int | None = None, temperature: float | None = None):
    video_spec = Path(video_spec_path).read_text()
    feedback = Path(feedback_path).read_text()
    system_prompt = """You are a YAML PATCH GENERATOR for a video pipeline.

You will receive:
1) A YAML video specification (video.yaml)
2) User feedback in natural language (feedback.txt)

Your job:
- Produce a SMALL YAML PATCH that edits the spec according to the feedback.
- Output YAML ONLY. No commentary, no markdown, no code fences.

HARD RULES (MUST FOLLOW):
- Output must be valid YAML.
- Top-level key must be exactly: scenes
- Only modify scenes that the feedback refers to.
- Use scene IDs exactly as provided (e.g., s1, s2, s3...).
- Do NOT invent new fields. Do NOT invent new scene IDs.
- Do NOT output null anywhere. If a field is unchanged, OMIT it completely.
- Prefer relative duration changes (e.g., +1.5 or -1.0). Do NOT output absolute durations.
- For visuals: NEVER output 'prompt'. Only output 'prompt_adjustment' when needed.
- For text edits: 'text' must be the final replacement subtitle line, not an instruction.

OUTPUT SCHEMA (EXACT):
scenes:
  <scene_id>:
    duration: <+float or -float>           # optional
    text: "<final rewritten subtitle text>" # optional
    visual:                                # optional
      prompt_adjustment: "<text to append>" # optional
      motion: "<slow_zoom|pan_left|pan_right|static>" # optional

If nothing needs to change, output exactly:
scenes: {}

EXAMPLES (CORRECT):

Example 1:
scenes:
  s2:
    duration: +1.5
    visual:
      prompt_adjustment: "less detail, softer lighting"

Example 2:
scenes:
  s3:
    text: "Your brain predicts first… then your eyes confirm it."
"""

    user_prompt = f"""
VIDEO SPEC:
{video_spec}

USER FEEDBACK:
{feedback}

OUTPUT:
(YAML PATCH ONLY)
"""

    response = call_llm(system_prompt, user_prompt,seed=seed,  temperature=temperature)

    # Basic sanity check
    try:
        yaml.safe_load(response)
    except Exception as e:
        raise RuntimeError("LLM output is not valid YAML") from e

    PATCH_OUTPUT.write_text(response)
    print("✓ video_patch.yaml written")


if __name__ == "__main__":
    generate_patch()
