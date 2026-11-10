"""
Prepare the LLM — LiquidAI/LFM2.5-1.2B-Instruct (Colab CUDA / Mac MPS / CPU).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from threading import Thread
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

DEFAULT_MODEL_ID = "LiquidAI/LFM2.5-1.2B-Instruct"


@dataclass
class LocalLLM:
    model_id: str
    tokenizer: AutoTokenizer
    model: AutoModelForCausalLM
    device: str

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def generate(
        self,
        messages: list[dict],
        *,
        max_new_tokens: int = 256,
        do_sample: bool = False,
    ) -> str:
        inputs = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
            "repetition_penalty": 1.05,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if do_sample:
            gen_kwargs["temperature"] = 0.1
            gen_kwargs["top_k"] = 50
        with torch.inference_mode():
            output_ids = self.model.generate(**inputs, **gen_kwargs)
        prompt_len = inputs["input_ids"].shape[1]
        return self.tokenizer.decode(
            output_ids[0][prompt_len:],
            skip_special_tokens=False,
        )

    def stream_generate(
        self,
        messages: list[dict],
        *,
        max_new_tokens: int = 120,
    ) -> dict[str, Any]:
        """Lab 2 streaming demo with TTFT using TextIteratorStreamer."""
        inputs = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        streamer = TextIteratorStreamer(
            self.tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        start = time.time()
        first = None
        chunks: list[str] = []

        thread = Thread(
            target=self.model.generate,
            kwargs={
                **inputs,
                "streamer": streamer,
                "max_new_tokens": max_new_tokens,
                "do_sample": False,
                "pad_token_id": self.tokenizer.eos_token_id,
            },
        )
        thread.start()
        for text in streamer:
            if first is None and text:
                first = time.time()
            chunks.append(text)
        thread.join()
        end = time.time()
        return {
            "text": "".join(chunks).strip(),
            "ttft_ms": (first - start) * 1000 if first else None,
            "total_s": end - start,
        }


def choose_device_and_dtype() -> tuple[str, torch.dtype]:
    """Prefer CUDA (Colab), then MPS (Mac), else CPU."""
    if torch.cuda.is_available():
        return "cuda", torch.bfloat16
    if torch.backends.mps.is_available():
        return "mps", torch.float16
    return "cpu", torch.float32


def load_llm(model_id: str | None = None) -> LocalLLM:
    resolved_id = model_id or os.getenv("LLM_MODEL_ID", DEFAULT_MODEL_ID)
    device, dtype = choose_device_and_dtype()
    print(f"Loading LLM: {resolved_id}")
    print(f"Device: {device} | dtype: {dtype}")

    tokenizer = AutoTokenizer.from_pretrained(resolved_id)
    model = AutoModelForCausalLM.from_pretrained(resolved_id, dtype=dtype)
    model.to(device)
    model.eval()
    return LocalLLM(
        model_id=resolved_id,
        tokenizer=tokenizer,
        model=model,
        device=device,
    )
