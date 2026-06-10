import { useNavigate } from "react-router-dom";

export default function BackButton({ fallback = "/", label = "Back", className = "" }) {
  const navigate = useNavigate();

  const goBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate(fallback);
  };

  return (
    <button
      type="button"
      onClick={goBack}
      className={`inline-flex min-h-[40px] items-center gap-2 rounded-xl border bg-[var(--brand-card)] px-4 py-2 text-sm font-semibold text-[var(--brand-primary)] shadow-sm transition hover:bg-gray-50 ${className}`}
    >
      <span aria-hidden="true">←</span>
      <span>{label}</span>
    </button>
  );
}

