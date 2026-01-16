# Worker that exposes audiocraft inputs to CLI for calling from another env
import warnings
warnings.filterwarnings("ignore")
from audiocraft.models import MusicGen # type: ignore
from audiocraft.models import MultiBandDiffusion # type: ignore
import argparse
# Add arguments for prompt and output file and duration

parser = argparse.ArgumentParser(description='Generate background music using MusicGen.')
parser.add_argument('--prompt', type=str, required=True, help='Text prompt for music generation')
parser.add_argument('--output', type=str, required=True, help='Output file path for the generated music')
parser.add_argument('--duration', type=int, default=30, help='Duration of the generated music in seconds')
args = parser.parse_args()
print(f"[bgm_gen_worker] Generating music with prompt: {args.prompt}, duration: {args.duration}s, output: {args.output}")
USE_DIFFUSION_DECODER = True
# Using small model, better results would be obtained with `medium` or `large`.
model = MusicGen.get_pretrained('facebook/musicgen-small')
if USE_DIFFUSION_DECODER:
    mbd = MultiBandDiffusion.get_mbd_musicgen()
    

model.set_generation_params(
    use_sampling=True,
    top_k=250,
    duration=args.duration
)

from audiocraft.utils.notebook import display_audio # type: ignore

output = model.generate(
    descriptions=[
        args.prompt
    ],
    progress=False, return_tokens=True
)
# display_audio(output[0], sample_rate=32000)
finOut = output[0]
if USE_DIFFUSION_DECODER:
    out_diffusion = mbd.tokens_to_wav(output[1])
    finOut = out_diffusion
    # display_audio(out_diffusion, sample_rate=32000)


import soundfile as sf
sf.write(args.output, finOut.detach().numpy().squeeze(0).squeeze(0), 32000)
print(f"[bgm_gen_worker] Generated music saved to {args.output}")