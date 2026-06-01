export default function Modal({ children, onClose }) {
  return (
    <div
      className="brand-modal-backdrop fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="brand-modal-panel brand-surface w-full max-w-lg bg-white p-6 md:p-8"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {children}
      </div>
    </div>
  );
}
