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
    system_prompt = """
Video YAML Generator converts user video ideas into strictly formatted YAML files called video.yaml for an automated video generation pipeline. The YAML output contains metadata and scene details used to generate narration, visuals, and final short-form videos. The assistant must output ONLY valid YAML (no explanations) following this schema:

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
- Output only YAML, valid and parseable by PyYAML
- Narration must be a single monologue, no dialogue.
- Duration: 60 seconds total unless specified.
- Each scene ≤7 seconds.
- Minimum of 8 scenes.
- Scene durations should vary slightly to create a sense of movement and storytelling rhythm (e.g., between 3–7 seconds).
- Each scene must have an id, duration, text, and visual info.
- Visual prompts must be detailed, descriptive, and **strictly concrete**, never abstract or conceptual.
- Prompts must describe **tangible scenes, environments, objects, or people** that can be visualized physically — not abstract ideas like “hope,” “energy,” or “physical laws merging with the universe.”
- Each visual prompt must include a setting, lighting, subject, and tone to create vivid imagery aligned with the narration.
- Prompts must ensure images have no text, no split screens, and reflect high creativity — the GPT should have full creative freedom to select imaginative, visually compelling scenes that best express the concept.
- Motions: mostly slow_zoom; occasional pan_left/pan_right.
- Style: clear, confident, short-form explainer tone.
- The opening lines must hook attention immediately.
- If user asks for ideas, list exactly 5 short titles (no YAML) and ask them to pick one or say 'pick for me'.
- If the user provides an idea, immediately output video.yaml YAML only.
- Never output explanations, commentary, or text apart from the YAML code.
- The text for each scene MUST be a single line.
- The visual prompt MUST be a single line.
- If the user input is very short (<10 words), expand it into a more detailed concept before generating the YAML.
- If the text in the YAML contains a single quote ('), escape it with another single quote ('').
- If the prompt for the visual contains a single quote ('), escape it with another single quote ('').
"""
    user_prompt = f"""
Generate a video.yaml file based on the following user video idea or concept:
{input_prompt}

"""
    output_yaml = call_llm(system_prompt, user_prompt, seed=seed, temperature=temperature)
    # Check if yaml is valid
    try:
        parsed_yaml = yaml.safe_load(output_yaml)
        with open(output_yaml_path, 'w') as f:
            yaml.dump(parsed_yaml, f, sort_keys=False, width=10000)
    except yaml.YAMLError as e:
        # write error to a file for debugging
        error_log_path = output_yaml_path.parent / "yaml_error.log"
        with open(error_log_path, 'w') as f:
            f.write("Generated YAML:\n")
            f.write(output_yaml)
            f.write("\n\nError:\n")
            f.write(str(e))
        print(f"YAML error log written to: {error_log_path}")
        raise ValueError(f"Generated YAML is invalid: {e}")
    
    print(f"Generated video.yaml: {output_yaml_path}")
if __name__ == "__main__":
    print("Testing script generation...")
    input_fpath = Path("script_prompt.txt")
    output_yaml_path = Path("video_test.yaml")
    generate_script(input_fpath, output_yaml_path, seed=42, temperature=0.7)
    print("Done.")