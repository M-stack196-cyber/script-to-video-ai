import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.scene_generator import generate_scene_plan  # noqa: E402


def test_scene_generator() -> None:
    script_path = PROJECT_ROOT / "samples" / "example_script.txt"
    script = script_path.read_text(encoding="utf-8")

    scene_plan = generate_scene_plan(script, 12, "9:16")
    validated_json = scene_plan.model_dump_json(indent=2)

    print("Scene generation: SUCCESS")
    print(validated_json)

    output_directory = PROJECT_ROOT / "backend" / "output"
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "scenes.json").write_text(
        validated_json + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    test_scene_generator()
