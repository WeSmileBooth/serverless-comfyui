import pathlib
import json
import subprocess
import time
import modal
import random
import os
import datetime

from .container import image, gpu
from pydantic import BaseModel

app = modal.App("comfy-api")


class InferModel(BaseModel):
    session_id: str
    prompt: str


class JobResult(BaseModel):
    base64_image: str
    signed_url: str


with image.imports():
    from firebase_admin import credentials, initialize_app, storage, firestore


@app.cls(
    gpu=gpu,
    image=image,
    container_idle_timeout=60 * 10,  # 10 minutes
    timeout=60 * 2,  # 2 minutes
    secrets=[modal.Secret.from_name("googlecloud-secret")],
)
class ComfyUI:
    def __init__(self):
        service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])
        cred = credentials.Certificate(service_account_info)
        firebase = initialize_app(
            cred,
            options={"storageBucket": "wesmile-photobooth.appspot.com"},
        )
        self.bucket = storage.bucket(app=firebase)
        self.db = firestore.client(app=firebase)

        self.workflow_json = json.loads(
            pathlib.Path("/root/workflow_api.json").read_text()
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

        # Create a client-side timestamp as a dictionary
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        start_time = {
            'timestamp': now_utc.timestamp(),
            'iso': now_utc.isoformat()
        }

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

        # Get the document
        doc = doc_ref.get()
        doc_data = doc.to_dict() if doc.exists else {}

        # Initialize arrays and count if they don't exist
        generation_count = doc_data.get('generation_count', 0)

        # Update the document with new generation info
        doc_ref.update({
            "prompt_id": prompt_id,
            "prompt": input.prompt,
            "status": "started",
            "progress": 0,
            "generation_count": generation_count + 1,  # Increment by 1
            "generation_start_times": firestore.ArrayUnion([start_time])  # Add new start time
        }) 

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

        # Create end timestamp in the same format
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        end_time = {
            'timestamp': now_utc.timestamp(),
            'iso': now_utc.isoformat()
        }
        
        doc_ref.update({
            "status": "completed",
            "generation_end_times": firestore.ArrayUnion([end_time])  # Add new end time
        })
        result = base64.b64encode(images_output).decode()

        return f"data:image/png;base64,{result}"


@app.function(
    gpu=False,
    image=image,
    allow_concurrent_inputs=100,
    timeout=60 * 15,
    container_idle_timeout=60 * 15,  # 15 minutes
    secrets=[modal.Secret.from_name("googlecloud-secret")],
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
        options={"storageBucket": "wesmile-photobooth.appspot.com"},
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

    @fastapi.get("/job/{job_id}/{session_id}")
    def on_get_job(job_id: str, session_id: str):
        function_call = modal.functions.FunctionCall.from_id(job_id)
        try:
            # Get the base64 result
            base64_result = function_call.get(timeout=60)

            # Generate signed URL using the provided session_id
            signed_url = bucket.blob(f"{session_id}/after").generate_signed_url(
                expiration=datetime.timedelta(minutes=30), method="GET"
            )

            # Return both results
            return JobResult(base64_image=base64_result, signed_url=signed_url)

        except TimeoutError:
            raise HTTPException(status_code=425, detail="Job is still processing")
        except Exception as e:
            print(f"Error processing job {job_id}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error processing job: {str(e)}"
            )

    return fastapi