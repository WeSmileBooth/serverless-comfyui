NODES = [
    "https://github.com/Gourieff/comfyui-reactor-node",
    "https://github.com/Fannovel16/comfyui_controlnet_aux",
    "https://github.com/jags111/efficiency-nodes-comfyui",
    "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes",
    "https://github.com/cubiq/ComfyUI_IPAdapter_plus",
    "https://github.com/ltdrdata/ComfyUI-Manager",
    "https://github.com/ltdrdata/ComfyUI-Impact-Pack",
    "https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet",
    "https://github.com/Acly/comfyui-tooling-nodes",
    "https://github.com/Gourieff/ComfyUI-ReActor",
]


def download_nodes():
    import subprocess
    import os

    for url in NODES:
        name = url.split("/")[-1]
        print(name)
        token = "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"  # github token
        url_with_token = url.replace(
            "https://github.com/", f"https://{token}@github.com/"
        )
        command = f"cd /root/custom_nodes && git clone {url_with_token}"
        try:
            subprocess.run(command, shell=True, check=True)
            print(f"Repository {url} cloned successfully")
        except subprocess.CalledProcessError as e:
            print(f"Error cloning repository: {e.stderr}")
            continue  # Skip to next repository if clone fails

        # Only try to install requirements if we successfully cloned the repo
        if os.path.isfile(f"/root/custom_nodes/{name}/requirements.txt"):
            print("Installing custom node requirements...")
            try:
                subprocess.run(
                    f"pip install -r /root/custom_nodes/{name}/requirements.txt",
                    shell=True,
                    check=True,
                )

                if os.path.isfile(f"/root/custom_nodes/{name}/install.py"):
                    process = subprocess.Popen(
                        ["python", f"./custom_nodes/{name}/install.py"]
                    )
                    process.wait()
                    retcode = process.returncode
                    if retcode != 0:
                        raise RuntimeError(
                            f"{name} install.py exited unexpectedly with code {retcode}"
                        )
                print(f"Requirements for {url} installed successfully")
            except (subprocess.CalledProcessError, RuntimeError) as e:
                print(f"Error installing requirements: {str(e)}")
