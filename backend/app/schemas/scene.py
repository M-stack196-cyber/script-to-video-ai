import math
from typing import Literal

from pydantic import BaseModel, model_validator


class Scene(BaseModel):
    scene_number: int
    start_time: float
    end_time: float
    duration: float
    narration: str
    visual_description: str
    video_prompt: str
    camera_movement: str
    overlay_text: str

    @model_validator(mode="after")
    def validate_timing(self) -> "Scene":
        expected_duration = self.end_time - self.start_time
        if self.start_time < 0:
            raise ValueError("start_time cannot be negative")
        if expected_duration <= 0:
            raise ValueError("end_time must be greater than start_time")
        if not math.isclose(self.duration, expected_duration, abs_tol=1e-6):
            raise ValueError("duration must equal end_time - start_time")
        return self


class ScenePlan(BaseModel):
    total_duration: int
    aspect_ratio: Literal["9:16", "16:9", "1:1"]
    scenes: list[Scene]

    @model_validator(mode="after")
    def validate_scenes(self) -> "ScenePlan":
        if not self.scenes:
            raise ValueError("scenes cannot be empty")

        for expected_number, scene in enumerate(self.scenes, start=1):
            if scene.scene_number != expected_number:
                raise ValueError("scene numbers must start at 1 and be sequential")

        for previous, current in zip(self.scenes, self.scenes[1:]):
            if current.start_time < previous.end_time:
                raise ValueError("scenes must be chronological and cannot overlap")

        duration_sum = sum(scene.duration for scene in self.scenes)
        if not math.isclose(duration_sum, self.total_duration, abs_tol=1e-6):
            raise ValueError("total of scene durations must equal total_duration")
        return self
