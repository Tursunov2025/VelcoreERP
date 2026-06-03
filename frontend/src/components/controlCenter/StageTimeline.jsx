export default function StageTimeline({ timeline = [], compact = false }) {
  if (!timeline?.length) {
    return <p className="text-xs text-gray-400">—</p>;
  }

  return (
    <div className={`flex flex-wrap gap-1 ${compact ? "" : "mt-2"}`}>
      {timeline.map((step, i) => {
        const status = step.status || "waiting";
        const colors = {
          completed: "bg-green-100 text-green-800 border-green-300",
          active: "bg-amber-100 text-amber-900 border-amber-400",
          waiting: "bg-gray-100 text-gray-600 border-gray-200",
        };
        return (
          <span
            key={`${step.stage}-${i}`}
            className={`rounded-lg border px-2 py-0.5 text-[10px] font-semibold sm:text-xs ${colors[status] || colors.waiting}`}
            title={step.stage}
          >
            {step.stage}
          </span>
        );
      })}
    </div>
  );
}
