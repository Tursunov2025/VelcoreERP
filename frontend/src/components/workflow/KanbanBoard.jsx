import { WORKFLOW_STAGES, STATUS_COLORS } from "../../constants/workflow";
import WorkflowOrderCard from "./WorkflowOrderCard";
import { CardSkeleton } from "../ui/Skeleton";

export default function KanbanBoard({
  board,
  loading,
  onComplete,
  onVerify,
  onRefresh,
}) {
  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
        {WORKFLOW_STAGES.map((s) => (
          <CardSkeleton key={s} />
        ))}
      </div>
    );
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {WORKFLOW_STAGES.map((stage) => (
        <div
          key={stage}
          className="min-w-[280px] shrink-0 rounded-[28px] bg-gray-100/80 p-3"
        >
          <div
            className={`mb-3 flex items-center justify-between rounded-2xl px-4 py-2 text-white ${STATUS_COLORS[stage]}`}
          >
            <span className="font-bold">{stage}</span>
            <span className="rounded-full bg-white/30 px-2 py-0.5 text-sm">
              {(board?.[stage] || []).length}
            </span>
          </div>
          <div className="space-y-3">
            {(board?.[stage] || []).map((order) => (
              <WorkflowOrderCard
                key={order.id}
                order={order}
                onComplete={onComplete}
                onVerify={onVerify}
                onRefresh={onRefresh}
              />
            ))}
            {(board?.[stage] || []).length === 0 && (
              <p className="py-8 text-center text-sm text-gray-400">Bo&apos;sh</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
