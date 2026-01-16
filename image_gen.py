# image_gen.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any

import torch
from diffusers import StableDiffusionPipeline, EulerAncestralDiscreteScheduler, ZImagePipeline


# DEFAULT_MODEL = "stable-diffusion-v1-5/stable-diffusion-v1-5" # CAN TRY ANY OTHER MODEL FROM HUGGINGFACE
DEFAULT_MODEL = "Tongyi-MAI/Z-Image-Turbo"


def pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class ImageGenerator:
    """
    Keeps the pipeline loaded in memory
    so you don't reload it for every scene.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL,
        device: Optional[str] = None,
        dtype: Optional[torch.dtype] = None,
    ):
        self.device = device or pick_device()

        # if dtype is None:
        #     if self.device in ("cuda", "mps"):
        #         dtype = torch.float16
        #     else:
        #         dtype = torch.float32
        if dtype is None:
            dtype = torch.float32

        # self.pipe = StableDiffusionPipeline.from_pretrained(
        #     model_id,
        #     torch_dtype=dtype,
        #     # safety_checker=None,  # optional; faster # lets keep safety on, or else we dont know what god awful pics it might generate
        #     # requires_safety_checker=False,
        # )

        # self.pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(self.pipe.scheduler.config)
        self.pipe = ZImagePipeline.from_pretrained(
            model_id,
            torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=False,
        )

        self.pipe = self.pipe.to(self.device)

        # Memory optimizations
        self.pipe.enable_attention_slicing()
        if self.device == "cuda":
            try:
                self.pipe.enable_xformers_memory_efficient_attention()
            except Exception:
                pass

    def generate(
        self,
        prompt: str,
        out_path: str | Path,
        *,
        negative_prompt: str = "",
        width: int = 720,
        height: int = 1280,
        steps: int = 9,
        guidance: float = 0.0,
        seed: Optional[int] = None,
    ) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)

        image = self.pipe(
            prompt=prompt,
            negative_prompt=negative_prompt if negative_prompt else None,
            num_inference_steps=steps,
            guidance_scale=guidance,
            width=width,
            height=height,
            generator=generator,
        ).images[0]

        image.save(out_path)
        return out_path
if __name__ == "__main__":
    print("Testing ImageGenerator...")
    gen = ImageGenerator()
    out_path = gen.generate(
        prompt="A futuristic underground research facility with large server racks, glowing indicator lights, cables neatly arranged, cool blue lighting, a clean high-tech atmosphere, realistic machines and hardware only, cinematic",
        out_path="build/images/test.png",
        width=720,
        height=1280,
        steps=9,
        guidance=0.0,
        seed=69,
    )
    print(f"Image saved to: {out_path}")