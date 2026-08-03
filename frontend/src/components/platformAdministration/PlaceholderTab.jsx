export default function PlaceholderTab({ icon, title, description }) {
  return (
    <article className="rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-6 shadow-sm sm:p-8">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--brand-secondary)] text-2xl">{icon}</div>
      <p className="mt-6 text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand-muted)]">Platform Administration</p>
      <h2 className="mt-2 text-2xl font-black text-[var(--brand-text)]">{title}</h2>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--brand-muted)]">{description}</p>
      <div className="mt-8 rounded-2xl border border-dashed border-[var(--brand-muted)]/30 px-5 py-6 text-sm text-[var(--brand-muted)]">This administration area is ready for its enterprise controls.</div>
    </article>
  );
}
