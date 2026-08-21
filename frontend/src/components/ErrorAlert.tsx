interface ErrorAlertProps {
  message: string;
  onDismiss?: () => void;
}

export function ErrorAlert({ message, onDismiss }: ErrorAlertProps) {
  return (
    <div className="error-alert" role="alert" aria-live="assertive">
      <span aria-hidden="true">!</span>
      <p>{message}</p>
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label="Dismiss error">×</button>
      )}
    </div>
  );
}
