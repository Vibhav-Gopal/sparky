# run bgm gen audiocraft commands in 3.9 conda
# conda activate bgmgen39
import subprocess
import os

#command to run bgm_gen_worker.py with args
# conda run -n audiocraftenv python bgm_gen_worker.py --prompt "A calm and soothing background music with gentle piano and soft strings, perfect for relaxation and meditation." --output "output_music.wav" --duration 30
def generate_bgm(prompt: str, output_file: str, duration: float =30) -> None:
    command = [
        "conda", "run", "--no-capture-output", "-n", "audiocraftenv",
        "python", "bgm_gen_worker.py",
        "--prompt", prompt,
        "--output", output_file,
        "--duration", str(int(duration)+1)
    ]
    print(f"[bgm_gen] Running command: {' '.join(command)}")
    result = subprocess.run(command, check=True,stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    print(f"[bgm_gen] Generated music saved to {output_file}")

if __name__ == "__main__":
    print("Testing bgm generation...")
    test_prompt = "\"A calm and soothing background music with gentle piano and soft strings, perfect for relaxation and meditation.\""
    test_output = "test_output_music.wav"
    generate_bgm(test_prompt, test_output, duration=5)
    print("BGM generation test completed.")