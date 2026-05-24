export default function Toast({ message, type = "success", onClose }) {
  if (!message) return null;

  const colors =
    type === "error"
      ? "bg-red-600"
      : type === "info"
        ? "bg-blue-600"
        : "bg-green-600";

  return (
    <div
      className={`fixed bottom-24 left-1/2 z-[90] -translate-x-1/2 rounded-2xl px-6 py-3 text-sm font-semibold text-white shadow-lg md:bottom-8 ${colors}`}
    >
      <button type="button" onClick={onClose} className="w-full text-left">
        {message}
      </button>
    </div>
  );
}
