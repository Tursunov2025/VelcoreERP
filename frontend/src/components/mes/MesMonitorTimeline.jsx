const STATUS_CLASS = {
  waiting: "bg-gray-200 text-gray-700",
  active: "bg-amber-400 text-amber-950 ring-2 ring-amber-500",
  completed: "bg-green-500 text-white",
};

export default function MesMonitorTimeline({ timeline = [], compact = false }) {
  if (!timeline.length) {
    return null;
  }

  return (
    <div className={`overflow-x-auto ${compact ? "" : "pb-1"}`}>
      <div className="flex min-w-[560px] items-center gap-1 sm:gap-2">
        {timeline.map((item, index) => (
          <div key={item.stage} className="flex flex-1 flex-col items-center">
            <div className="flex w-full items-center">
              {index > 0 ? (
                <div
                  className={`h-0.5 flex-1 ${
                    item.status === "waiting" ? "bg-gray-200" : "bg-green-400"
                  }`}
                />
              ) : (
                <div className="flex-1" />
              )}
              <span
                title={item.stage}
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold sm:h-8 sm:w-8 sm:text-xs ${
                  STATUS_CLASS[item.status] || STATUS_CLASS.waiting
                }`}
              >
                {index + 1}
              </span>
              {index < timeline.length - 1 ? (
                <div
                  className={`h-0.5 flex-1 ${
                    timeline[index + 1]?.status === "waiting" ? "bg-gray-200" : "bg-green-400"
                  }`}
                />
              ) : (
                <div className="flex-1" />
              )}
            </div>
            <span
              className={`mt-1 max-w-[52px] truncate text-center text-[9px] font-semibold sm:max-w-none sm:text-[10px] ${
                item.status === "active" ? "text-amber-700" : "text-[var(--brand-muted)]"
              }`}
            >
              {item.stage}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
