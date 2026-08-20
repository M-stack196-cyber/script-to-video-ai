import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.schemas.scene import ScenePlan  # noqa: E402
from app.services.video_generator import (  # noqa: E402
    format_status_for_display,
    get_video_generation_status,
    start_video_generation,
)


def test_video_generator() -> None:
    scenes_path = BACKEND_ROOT / "output" / "scenes.json"
    scene_plan = ScenePlan.model_validate_json(
        scenes_path.read_text(encoding="utf-8")
    )
    prompt = scene_plan.scenes[0].video_prompt
    prompt_preview = " ".join(prompt.split())[:120]

    print(f"Configured video model: {settings.bedrock_video_model_id}")
    print(f"Prompt preview: {prompt_preview}")

    if not settings.s3_bucket_name.strip():
        print("S3 bucket required for real Nova Reel generation")
        return

    invocation_arn = start_video_generation(prompt)
    print(f"Invocation ARN: {invocation_arn}")

    status = get_video_generation_status(invocation_arn)
    print("Status:")
    print(format_status_for_display(status))


if __name__ == "__main__":
    test_video_generator()
