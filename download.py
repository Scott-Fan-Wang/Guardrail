import os
from modelscope.hub.snapshot_download import snapshot_download

def download_llama_prompt_guard2(target_dir):
    model_id = "LLM-Research/Llama-Prompt-Guard-2-86M"
    # Download the model to the specified directory
    model_path = snapshot_download(
        repo_id=model_id,
        local_dir=target_dir,
    )
    print(f"Model downloaded to: {model_path}")
    return model_path

# Example usage:
if __name__ == "__main__":
    target_directory = "models"
    os.makedirs(target_directory, exist_ok=True)
    download_llama_prompt_guard2(target_directory)
