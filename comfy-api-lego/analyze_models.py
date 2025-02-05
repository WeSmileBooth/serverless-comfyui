import json


def find_model_paths(workflow):
    """Analyzes a ComfyUI workflow to find all required model paths."""
    model_paths = {
        "checkpoints": [],
        "loras": [],
        "controlnet": [],
        "ipadapter": [],
        "clip_vision": [],
        "other": [],
    }

    for node_id, node in workflow.items():
        class_type = node.get("class_type", "")
        inputs = node.get("inputs", {})

        # Check different node types
        if "CheckpointLoader" in class_type:
            if "ckpt_name" in inputs:
                model_paths["checkpoints"].append(inputs["ckpt_name"])
        elif "LoraLoader" in class_type:
            if "lora_name" in inputs:
                model_paths["loras"].append(inputs["lora_name"])
        elif "IPAdapter" in class_type:
            if "ipadapter_file" in inputs:
                model_paths["ipadapter"].append(inputs["ipadapter_file"])
        elif "CLIPVision" in class_type:
            if "clip_name" in inputs:
                model_paths["clip_vision"].append(inputs["clip_name"])

        # Check for ControlNet in any node
        for key, value in inputs.items():
            if (
                "controlnet" in key.lower()
                and isinstance(value, str)
                and value != "None"
            ):
                model_paths["controlnet"].append(value)

    return model_paths


# Load your workflow
with open("workflow_api.json", "r") as f:
    workflow = json.load(f)

# Find all model paths
model_paths = find_model_paths(workflow)

# Print results in an organized way
print("Required models by category:")
print("\nCheckpoints (in /root/models/checkpoints/):")
for path in model_paths["checkpoints"]:
    print(f"  - {path}")

print("\nLoRAs (in /root/models/loras/):")
for path in model_paths["loras"]:
    print(f"  - {path}")

print("\nControlNet models (in /root/models/controlnet/):")
for path in model_paths["controlnet"]:
    print(f"  - {path}")

print("\nIP-Adapter models (in /root/models/ipadapter/):")
for path in model_paths["ipadapter"]:
    print(f"  - {path}")

print("\nCLIP Vision models (in /root/models/clip_vision/):")
for path in model_paths["clip_vision"]:
    print(f"  - {path}")
