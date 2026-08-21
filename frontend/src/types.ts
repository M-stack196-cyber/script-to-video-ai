export type VideoJobStatus =
  | "queued"
  | "planning"
  | "generating_video"
  | "video_ready"
  | "generating_audio"
  | "composing"
  | "completed"
  | "failed";

export type SceneJobStatus =
  | "queued"
  | "submitted"
  | "in_progress"
  | "completed"
  | "failed";

export type VideoJobNextAction =
  | "submit_video"
  | "refresh"
  | "download_video"
  | "compose"
  | "completed"
  | "none";

export type VideoWorkflowStage =
  | "planning"
  | "waiting_to_submit"
  | "generating_video"
  | "downloading"
  | "generating_audio"
  | "composing"
  | "completed"
  | "failed";

export type AspectRatio = "9:16" | "16:9" | "1:1";
export type VideoDuration = 6 | 12 | 18;

export interface SceneJob {
  scene_number: number;
  prompt: string;
  duration: number | null;
  narration: string | null;
  overlay_text: string | null;
  invocation_arn: string | null;
  status: SceneJobStatus;
  output_s3_uri: string | null;
  local_video_path: string | null;
  video_downloaded: boolean;
  error: string | null;
}

export interface VideoJob {
  job_id: string;
  status: VideoJobStatus;
  progress: number;
  message: string;
  mode: "ai" | "demo";
  script: string;
  duration: number;
  aspect_ratio: AspectRatio;
  scenes: SceneJob[];
  final_video_url: string | null;
  error: string | null;
  narration_provider: string | null;
  created_at: string;
  updated_at: string;
}

export interface VideoJobWorkflowState {
  job: VideoJob;
  next_action: VideoJobNextAction;
  stage: VideoWorkflowStage;
  can_submit_video: boolean;
  can_refresh: boolean;
  can_download_video: boolean;
  can_compose: boolean;
  is_terminal: boolean;
}

export interface ConfigStatus {
  app_env: string;
  job_store_provider: string;
  production_storage_ready: boolean;
  local_media_enabled: boolean;
  text_model_configured: boolean;
  video_model_configured: boolean;
  audio_model_configured: boolean;
  s3_configured: boolean;
  mock_scene_planner: boolean;
  narration_provider: string;
  nova_sonic_sdk_available: boolean;
  standard_aws_credentials_detected: boolean;
}

export interface DeploymentReadiness {
  ready: boolean;
  app_env: string;
  frontend_ready: boolean;
  scene_planner_ready: boolean;
  video_generation_ready: boolean;
  durable_job_storage_ready: boolean;
  media_storage_ready: boolean;
  narration_ready: boolean;
  local_demo_available: boolean;
  blockers: string[];
}

export interface CreateWorkflowPayload {
  script: string;
  duration: VideoDuration;
  aspect_ratio: AspectRatio;
}
