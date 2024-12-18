import pathlib
import json
import subprocess
import time
import modal
import random
import os

from .container import image, gpu

app = modal.App("comfy-api")

from pydantic import BaseModel


class InferModel(BaseModel):
    session_id: str
    prompt: str


with image.imports():
    from firebase_admin import credentials, initialize_app, storage, firestore


@app.cls(
    gpu=gpu,
    image=image,
    container_idle_timeout=60 * 15,  # 15 minutes
    timeout=60 * 60,  # 1 hour
    secrets=[modal.Secret.from_name("googlecloud-secret-2")],
    mounts=[
        modal.Mount.from_local_file(
            local_path=(pathlib.Path(__file__).parent / "workflow_api.json"),
            remote_path="/root/workflow_api.json",
        ),
    ],
)
class ComfyUI:
    def __init__(self):
        service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])
        cred = credentials.Certificate(service_account_info)
        firebase = initialize_app(
            cred,
            options={"storageBucket": "photobooth-robot.appspot.com"},
        )
        self.bucket = storage.bucket(app=firebase)
        self.db = firestore.client(app=firebase)

        self.workflow_json = json.loads(
            (pathlib.Path(__file__).parent / "workflow_api.json").read_text()
        )

    def _run_comfyui_server(self, port=8188):
        cmd = f"python main.py --listen 0.0.0.0 --port {port}"
        subprocess.Popen(cmd, shell=True)

    @modal.enter()
    def prepare(self):
        self._run_comfyui_server(port=8189)

    @modal.method()
    def infer(self, input: InferModel):
        import urllib
        import base64
        import websocket
        import requests
        import copy

        while True:
            try:
                requests.get("http://0.0.0.0:8189/prompt")
                break
            except (requests.ConnectionError, requests.Timeout) as e:
                continue
            except:
                pass

        bytes = self.bucket.blob(f"{input.session_id}/before").download_as_bytes()

        pathlib.Path(f"/root/input/{input.session_id}").write_bytes(bytes)

        workflow = copy.deepcopy(self.workflow_json)
        workflow["11"]["inputs"]["seed"] = random.randint(1, 2**64)
        workflow["1"]["inputs"]["image"] = input.session_id
        workflow["9"]["inputs"]["text"] += input.prompt

        data = json.dumps({"prompt": workflow, "client_id": input.session_id}).encode(
            "utf-8"
        )

        response = urllib.request.Request(f"http://0.0.0.0:8189/prompt", data=data)
        result = json.loads(urllib.request.urlopen(response).read())

        prompt_id = result["prompt_id"]

        doc_ref = self.db.collection("records").document(input.session_id)
        # TODO: This is changed to update to update the document
        doc_ref.update(
            {
                "created_at": firestore.SERVER_TIMESTAMP,
                "prompt_id": prompt_id,
                "prompt": input.prompt,
                "status": "started",
                "progress": 0,
            }
        )

        ws = websocket.WebSocket()
        while True:
            try:
                ws.connect(f"ws://0.0.0.0:8189/ws?clientId={input.session_id}")
                break
            except ConnectionRefusedError:
                time.sleep(1)

        images_output = None
        current_node = ""
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)

                if message["type"] == "executing":
                    data = message["data"]

                    if data.get("prompt_id") and data.get("prompt_id") == prompt_id:
                        if data["node"] is None:
                            doc_ref.update({"status": "executed"})
                            break
                        else:
                            current_node = data["node"]

                elif message["type"] == "progress":
                    data = message["data"]

                    if (
                        data.get("prompt_id")
                        and data.get("prompt_id") == prompt_id
                        and data["node"] == "11"
                    ):
                        doc_ref.update({"progress": data["value"], "status": "pending"})
            else:
                if (
                    workflow[current_node]
                    and workflow[current_node]["class_type"] == "SaveImageWebsocket"
                ):
                    images_output = out[8:]

        self.bucket.blob(f"{input.session_id}/after").upload_from_string(
            images_output, content_type="image/png"
        )
        doc_ref.update({"status": "completed"})
        result = base64.b64encode(images_output).decode()

        return f"data:image/png;base64,{result}"


@app.function(
    gpu=False,
    image=image,
    allow_concurrent_inputs=100,
    timeout=60 * 15,
    container_idle_timeout=60 * 15,  # 15 minutes
    secrets=[modal.Secret.from_name("googlecloud-secret-2")],
)
@modal.asgi_app()
def api():
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware

    fastapi = FastAPI()
    fastapi.add_middleware(
        CORSMiddleware,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        allow_origins=["*"],
    )

    service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])
    cred = credentials.Certificate(service_account_info)
    firebase = initialize_app(
        cred,
        options={"storageBucket": "photobooth-robot.appspot.com"},
    )
    bucket = storage.bucket(app=firebase)

    ComfyUI = modal.Cls.lookup("comfy-api", "ComfyUI")
    comfyui = ComfyUI()

    @fastapi.get("/blob/{blob_name:path}")
    def get_presigned_url(blob_name: str):
        import datetime

        return bucket.blob(blob_name).generate_signed_url(
            expiration=datetime.timedelta(minutes=30), method="GET"
        )

    @fastapi.post("/job")
    def on_job_post(input: InferModel):
        job = comfyui.infer.spawn(input)
        return job.object_id

    @fastapi.get("/job/{job_id}")
    def on_get_job(job_id: str):
        function_call = modal.functions.FunctionCall.from_id(job_id)
        try:
            result = function_call.get(timeout=60)
            return result
        except TimeoutError:
            return HTTPException(status_code=425, detail="Job is still processing")

    return fastapi
