export default function Card({ children, className = "" }) {
  return (
    <section
      className={`brand-surface rounded-[var(--brand-radius)] bg-[var(--brand-card)] p-5 text-[var(--brand-text)] shadow-[var(--brand-shadow)] md:p-6 ${className}`}
    >
      {children}
    </section>
  );
}
