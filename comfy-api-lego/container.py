from modal import Image

from .models import download_checkpoints
from .nodes import download_nodes

commit_sha = "2a02546e2085487d34920e5b5c9b367918531f32"
gpu = "h100"

image = (
    Image.from_registry("nvidia/cuda:12.1.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install(
        "git", "git-lfs", "libgl1-mesa-glx", "libglib2.0-0", "unzip", "clang", "wget"
    )
    .run_commands(
        "cd /root && git init .",
        "cd /root && git remote add --fetch origin https://github.com/comfyanonymous/ComfyUI",
        f"cd /root && git checkout {commit_sha}",
    )
    .run_commands(
        "cd /root && pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121",
        "cd /root && pip install -r requirements.txt",
        gpu=gpu,
    )
    .pip_install(
        "httpx",
        "requests",
        "tqdm",
        "gdown",
        "websocket-client",
        "firebase_admin",
    )
    .run_function(download_nodes, gpu=gpu)
    .run_function(download_checkpoints)
    .run_commands("pip install --upgrade fastapi")
    # Using wget instead of gdown for more reliable downloads
    .run_commands(
        "mkdir -p /root/models/insightface",
        # Using a direct download link or mirror
        "cd /root/models/insightface && wget https://huggingface.co/deepinsight/insightface/resolve/main/buffalo_l.zip",
        "cd /root/models/insightface && unzip buffalo_l.zip -d models",
    )
)
