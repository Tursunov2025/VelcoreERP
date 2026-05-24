import { WORKFLOW_STAGES } from "../../constants/workflow";

export default function OrderTimeline({ history = [] }) {
  const completedStages = new Set(
    history.filter((h) => h.action === "completed" || h.action === "verified").map((h) => h.stage)
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      {WORKFLOW_STAGES.map((stage, index) => {
        const done = completedStages.has(stage);
        return (
          <div key={stage} className="flex items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-xs font-bold transition ${
                done ? "bg-green-500 text-white" : "bg-gray-200 text-gray-600"
              }`}
            >
              {stage}
            </span>
            {index < WORKFLOW_STAGES.length - 1 && (
              <span className="text-gray-400">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
