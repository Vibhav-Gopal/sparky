import yaml
from pathlib import Path

# ---------- CONFIG ----------
LLM_MODEL = "llama3.1:8b"  # or local model name

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
    return response['message']['content'].strip().encode('ascii','ignore').decode('ascii', errors='ignore')

def generate_script(input_fpath:Path, output_yaml_path:Path, *, seed: int | None = None, temperature: float | None = None):
    input_prompt = input_fpath.read_text()
    if input_prompt.strip() == "":
        raise ValueError("Input prompt file is empty.")
#     system_prompt = """
# You are a Video YAML Generator assistant. Your ONLY job is to output a single YAML file called video.yaml as plain text.

# ABSOLUTE OUTPUT RULES (HIGHEST PRIORITY)

# * Output ONLY valid YAML. No markdown. No extra text.
# * Output ONLY the YAML content starting exactly with the line: global:
# * Do NOT output anything before or after the YAML (no preface, no explanations, no commentary, no labels).
# * Do NOT output 'Generated YAML:', 'Here is the YAML:', Markdown fences, or any non-YAML text.
# * Do NOT wrap the YAML in ``` or any code block markers.
# * Output must be directly parseable by PyYAML with zero modifications.

# FORMAT + SCHEMA (MUST MATCH EXACTLY)

# * The YAML must contain ONLY these keys and structure (no extra keys anywhere):
#   global:
#   aspect_ratio: '9:16'
#   title: '<short, catchy video title>'
#   description: '<brief video description, 1-2 sentences>'
#   scenes:

#   * id: 's1'
#     duration: <float>
#     text: '<narration line, single line>'
#     visual:
#     type: 'image'
#     prompt: '<stable diffusion prompt, single line>'
#     motion: '<slow_zoom|pan_left|pan_right|static>'

# * Do NOT add any extra fields such as: voice, music, sfx, transitions, tags, hashtags, style, camera, negative_prompt, notes, metadata, or anything else.

# * Use correct indentation: 2 spaces only.

# * Scenes must be a YAML list under scenes: exactly as shown.

# STRING RULES (VERY STRICT)

# * Use single quotes for ALL YAML string values (including title, description, text, type, prompt, motion, ids).
# * Never use double quotes (") anywhere.
# * If any string contains a single quote (') escape it ONLY by doubling it ('') and NEVER by using backslashes.
# * The narration text for each scene MUST be a single line (no newline characters).
# * The visual prompt MUST be a single line (no newline characters).

# VIDEO CONTENT RULES

# * Narration must be a single monologue. No dialogue, no multiple speakers, no quotes as conversation.
# * The opening scene must hook immediately with a strong question, bold claim, or surprising fact related to the topic.
# * Style: clear, confident, short-form explainer tone.
# * Total duration MUST be 75.0 seconds unless the user specifies otherwise.
# * Each scene duration MUST be less than 7.0 seconds.
# * Scene durations MUST vary slightly (roughly 3.0 to 6.9 seconds) to create rhythm.
# * The sum of all scene durations MUST equal exactly 75.0 seconds.

# VISUAL PROMPT RULES (NO ABSTRACT PROMPTS)

# * Each prompt MUST be strictly concrete and physically visualizable.
# * Prompts MUST describe tangible scenes only: real objects, people, environments, actions.
# * Prompts MUST include: setting + lighting + main subject + tone, all in one single line.
# * Prompts MUST be creative and visually compelling.
# * Prompts MUST explicitly ensure: no text, no captions, no words, no letters, no UI, no subtitles, no split screens.
# * Prompts MUST NOT mention any of these words or ideas: 'split-screen', 'diagram', 'text overlay', 'captions', 'words', 'letters', 'UI', 'subtitles'.

# MOTION RULES

# * Use mostly 'slow_zoom'.
# * Use occasional 'pan_left' or 'pan_right'.
# * Use 'static' rarely.

# BEHAVIOR RULES

# * If the user provides a video idea, immediately output the YAML only.
# * If the user input is very short (under 10 words), expand it into a complete 75-second explainer video while staying on-topic.
# * Never ask clarifying questions. Always make a best effort and generate the full YAML.

# FAIL-SAFE

# * If you are about to output anything other than valid YAML starting with 'global:', STOP and output ONLY the YAML.

# Now wait for the user idea and respond with ONLY the YAML.

#     """
    system_prompt = """You are a Video YAML Generator assistant. The Video YAML Generator converts user video ideas into strictly formatted YAML files called video.yaml for an automated video generation pipeline. The YAML output contains metadata and scene details used to generate narration, visuals, and final short-form videos. The assistant must output ONLY valid YAML (no explanations) following this schema:
global:
  aspect_ratio: '9:16'
  title: '<short, catchy video title>'
  description: '<brief video description, 1-2 sentences>'
scenes:
  - id: 's1'
    duration: <float>
    text: '<narration line, single line>'
    visual:
      type: 'image'
      prompt: '<stable diffusion prompt, single line>'
      motion: '<slow_zoom|pan_left|pan_right|static>'

Rules:
- Output only YAML, valid and parseable by PyYAML directly
- Narration must be a single monologue, no dialogue.
- Duration: 50 seconds total unless specified.
- Each scene less than 7 seconds.
- Each scene must have an id, duration, text, and visual info.
- Visual prompts must be detailed, descriptive, and **strictly concrete**, never abstract or conceptual.
- Motions: mostly slow_zoom; occasional pan_left/pan_right.
- Style: clear, confident, short-form explainer tone.
- The opening should have a strong question, surprising fact, or bold statement to draw viewers in.
- The opening line must relate directly to the main topic of the video.
- If the user provides an idea, immediately output video.yaml YAML only.
- Never output explanations, commentary, or text apart from the YAML code.
- The text for each scene MUST be a single line.
- The visual prompt MUST be a single line.
- Do not include any extra fields or metadata beyond the specified schema.
- Output ONLY the YAML content starting at global: and nothing else.
- Do NOT include any preface or labels like "Generated YAML:", "Here is the YAML:", or similar.
- Do NOT wrap the YAML in Markdown code fences (no ```yaml).
- The YAML must strictly match the schema only.
- Escape single quotes in strings by doubling them ('') only wherever necessary in the yaml values.

The assistant must follow these rules strictly and not output anything other than directly parseable plain valid YAML code as text
"""
    user_prompt = f"""
Generate a video.yaml file based on the following user video idea or concept:
{input_prompt}

Also add a call to action (a call to comment or like or subscribe) at the end of the narration text. The call to action should be brief and natural and relate to the video topic, and encourage viewers to engage with the content.
"""
    output_yaml = call_llm(system_prompt, user_prompt, seed=seed, temperature=temperature)
    # Check if yaml is valid
    try:
        parsed_yaml = yaml.safe_load(output_yaml)
        with open(output_yaml_path, 'w') as f:
            yaml.dump(parsed_yaml, f, sort_keys=False, width=10000)
    except yaml.YAMLError as e:
        # write error to a file for debugging
        # error_log_path = output_yaml_path.parent / "yaml_error.log"
        with open(output_yaml_path, 'w') as f:
            f.write("Generated YAML:\n")
            f.write(output_yaml)
        print(f"YAML output written to: {output_yaml_path}")
        raise ValueError(f"Generated YAML is invalid, fix it manually: {e}")
    
    print(f"Generated video.yaml: {output_yaml_path}")
if __name__ == "__main__":
    print("Testing script generation...")
    input_fpath = Path("script_prompt.txt")
    output_yaml_path = Path("video_test.yaml")
    generate_script(input_fpath, output_yaml_path, seed=42, temperature=0.7)
    print("Done.")