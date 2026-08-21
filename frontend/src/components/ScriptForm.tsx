import { useState, type FormEvent } from "react";
import type { AspectRatio, CreateWorkflowPayload, VideoDuration } from "../types";

interface ScriptFormProps {
  disabled: boolean;
  locked: boolean;
  onSubmit: (payload: CreateWorkflowPayload) => Promise<void>;
}

const durations: VideoDuration[] = [6, 12, 18];
const aspectRatios: Array<{ value: AspectRatio; label: string }> = [
  { value: "9:16", label: "Vertical" },
  { value: "16:9", label: "Landscape" },
  { value: "1:1", label: "Square" },
];

export function ScriptForm({ disabled, locked, onSubmit }: ScriptFormProps) {
  const [script, setScript] = useState("");
  const [duration, setDuration] = useState<VideoDuration>(12);
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>("16:9");
  const trimmedScript = script.trim();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmedScript || disabled || locked) return;
    await onSubmit({ script: trimmedScript, duration, aspect_ratio: aspectRatio });
  }

  return (
    <section className="panel creation-panel" aria-labelledby="creation-heading">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Create</span>
          <h2 id="creation-heading">Plan your video</h2>
        </div>
        <span className="step-chip">Step 01</span>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="field-heading">
          <label htmlFor="video-script">Video script</label>
          <span>{script.length.toLocaleString()} characters</span>
        </div>
        <textarea
          id="video-script"
          value={script}
          onChange={(event) => setScript(event.target.value)}
          placeholder="Write the message, story, or product narrative you want to turn into video…"
          rows={10}
          disabled={disabled || locked}
          required
        />

        <fieldset disabled={disabled || locked}>
          <legend>Duration</legend>
          <div className="segmented-control three-up">
            {durations.map((option) => (
              <label key={option} className={duration === option ? "selected" : ""}>
                <input
                  type="radio"
                  name="duration"
                  value={option}
                  checked={duration === option}
                  onChange={() => setDuration(option)}
                />
                <strong>{option}</strong>
                <span>seconds</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset disabled={disabled || locked}>
          <legend>Aspect ratio</legend>
          <div className="ratio-grid">
            {aspectRatios.map((option) => (
              <label
                key={option.value}
                className={aspectRatio === option.value ? "selected" : ""}
              >
                <input
                  type="radio"
                  name="aspect-ratio"
                  value={option.value}
                  checked={aspectRatio === option.value}
                  onChange={() => setAspectRatio(option.value)}
                />
                <span className={`ratio-icon ratio-${option.value.replace(":", "-")}`} />
                <span>
                  <strong>{option.value}</strong>
                  <small>{option.label}</small>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <button
          className="button primary full-width"
          type="submit"
          disabled={disabled || locked || !trimmedScript}
        >
          {disabled ? <span className="spinner" aria-hidden="true" /> : null}
          {disabled ? "Planning video…" : locked ? "Video plan created" : "Plan AI Video"}
        </button>
        <p className="form-footnote">
          Planning does not start paid video generation. You’ll confirm that separately.
        </p>
      </form>
    </section>
  );
}
