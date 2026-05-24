export default function Card({ children, className = "" }) {
  return (
    <section
      className={`rounded-[28px] bg-white p-5 shadow-lg md:rounded-[32px] md:p-6 ${className}`}
    >
      {children}
    </section>
  );
}
