import pathlib

MODELS = [
    {
        "url": "https://huggingface.co/Yabo/SDXL_LoRA/resolve/main/dreamshaperXL_alpha2Xl10.safetensors",
        "directory": "/root/models/checkpoints",
    },
    {
        "url": "https://huggingface.co/datasets/Gourieff/ReActor/resolve/main/models/inswapper_128.onnx",
        "directory": "/root/models/insightface",
    },
    {
        "url": "https://huggingface.co/datasets/Gourieff/ReActor/resolve/main/models/facerestore_models/codeformer-v0.1.0.pth",
        "directory": "/root/models/facerestore_models",
    },
    {
        "url": "https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/parsing_parsenet.pth",
        "directory": "/root/models/facedetection",
    },
    {
        "url": "https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/yolov5l-face.pth",
        "directory": "/root/models/facedetection",
    },
    {
        "url": "https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank256/control-lora-depth-rank256.safetensors",
        "directory": "/root/models/controlnet",
    },
    {
        "url": "https://huggingface.co/thibaud/controlnet-openpose-sdxl-1.0/resolve/main/control-lora-openposeXL2-rank256.safetensors",
        "directory": "/root/models/controlnet",
    },
    {
        "url": "https://huggingface.co/lllyasviel/Annotators/resolve/main/dpt_hybrid-midas-501f0c75.pt",
        "directory": "/root/custom_nodes/comfyui_controlnet_aux/ckpts/lllyasviel/Annotators",
    },
    {
        "url": "https://huggingface.co/lllyasviel/Annotators/resolve/main/body_pose_model.pth",
        "directory": "/root/custom_nodes/comfyui_controlnet_aux/ckpts/lllyasviel/Annotators",
    },
    {
        "url": "https://huggingface.co/lllyasviel/Annotators/resolve/main/hand_pose_model.pth",
        "directory": "/root/custom_nodes/comfyui_controlnet_aux/ckpts/lllyasviel/Annotators",
    },
    {
        "url": "https://huggingface.co/lllyasviel/Annotators/resolve/main/facenet.pth",
        "directory": "/root/custom_nodes/comfyui_controlnet_aux/ckpts/lllyasviel/Annotators",
    },
    # ipadapter
    {
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors",
        "directory": "/root/models/clip_vision",
    },
    {
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors",
        "directory": "/root/models/ipadapter",
    },
]


def download_checkpoints():
    import httpx
    from tqdm import tqdm

    for model in MODELS:
        url = model["url"]
        local_filename = url.split("/")[-1]

        # for the clip vision of ipadapter
        if local_filename == "model.safetensors":
            local_filename = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"

        local_filepath = pathlib.Path(model["directory"], local_filename)
        local_filepath.parent.mkdir(parents=True, exist_ok=True)

        print(f"downloading {url} ...")
        with httpx.stream("GET", url, follow_redirects=True) as stream:
            total = int(stream.headers["Content-Length"])
            with open(local_filepath, "wb") as f, tqdm(
                total=total, unit_scale=True, unit_divisor=1024, unit="B"
            ) as progress:
                num_bytes_downloaded = stream.num_bytes_downloaded
                for data in stream.iter_bytes():
                    f.write(data)
                    progress.update(stream.num_bytes_downloaded - num_bytes_downloaded)
                    num_bytes_downloaded = stream.num_bytes_downloaded


def download_upscaler():
    import httpx
    from tqdm import tqdm

    url = "https://huggingface.co/datasets/Kizi-Art/Upscale/resolve/main/4x-UltraSharp.pth"
    local_filename = url.split("/")[-1]
    local_filepath = pathlib.Path("/root/models/upscale_models", local_filename)
    local_filepath.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url} ...")
    with httpx.stream("GET", url, follow_redirects=True) as stream:
        total = int(stream.headers["Content-Length"])
        with open(local_filepath, "wb") as f, tqdm(
            total=total, unit_scale=True, unit_divisor=1024, unit="B"
        ) as progress:
            num_bytes_downloaded = stream.num_bytes_downloaded
            for data in stream.iter_bytes():
                f.write(data)
                progress.update(stream.num_bytes_downloaded - num_bytes_downloaded)
                num_bytes_downloaded = stream.num_bytes_downloaded
