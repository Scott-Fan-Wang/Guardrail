"""
Host-side model downloader.

Run this script ONCE on the host machine before starting the Docker stack.
It downloads all required model weights into ./models/ using ModelScope,
so that the container can load them from the mounted volume without any
network access.

Usage:
    python download.py

Sub-directories created under ./models/:
    Llama-Prompt-Guard-2-86M/   – used by llama_prompt_guard provider
    Llama-Guard-4-12B/          – used by llama_guard_4_12b provider
"""

import os
import sys

try:
    from modelscope.hub.snapshot_download import snapshot_download
except ImportError:
    print(
        "ERROR: modelscope is not installed on the host.\n"
        "Install it with:  pip install modelscope",
        file=sys.stderr,
    )
    sys.exit(1)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

MODELS = [
    {
        "repo_id": "LLM-Research/Llama-Prompt-Guard-2-86M",
        "local_dir": os.path.join(MODELS_DIR, "Llama-Prompt-Guard-2-86M"),
        "description": "Llama Prompt Guard 2 (86M) – prompt injection / jailbreak classifier",
    },
    {
        "repo_id": "LLM-Research/Llama-Guard-4-12B",
        "local_dir": os.path.join(MODELS_DIR, "Llama-Guard-4-12B"),
        "description": "Llama Guard 4 (12B) – general content safety classifier",
    },
]


def download_model(repo_id: str, local_dir: str, description: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"Downloading: {description}")
    print(f"  repo  : {repo_id}")
    print(f"  target: {local_dir}")
    print(f"{'=' * 60}")
    os.makedirs(local_dir, exist_ok=True)
    path = snapshot_download(repo_id=repo_id, local_dir=local_dir)
    print(f"Done -> {path}")


if __name__ == "__main__":
    os.makedirs(MODELS_DIR, exist_ok=True)
    for model in MODELS:
        download_model(**model)
    print("\nAll models downloaded successfully.")
    print(f"Mount ./models into the container before running `docker compose up`.")
