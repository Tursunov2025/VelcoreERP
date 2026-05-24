export default function ErrorAlert({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <p>{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 font-semibold underline"
        >
          Qayta urinish
        </button>
      )}
    </div>
  );
}
