import Card from "../ui/Card";
import {
  PRIORITY_BADGE,
  PRIORITY_LABELS,
  STATUS_BADGE,
  STATUS_LABELS,
} from "../../constants/tasks";

function formatDate(value) {
  if (!value) return "";
  const d = new Date(value);
  return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function TaskCard({ task, isAdmin, onOpen }) {
  const myStatus = task.my_status;

  return (
    <Card
      className={`cursor-pointer transition hover:shadow-xl ${
        task.is_overdue ? "ring-2 ring-red-300" : ""
      }`}
    >
      <button
        type="button"
        onClick={() => onOpen(task)}
        className="w-full text-left"
      >
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
              PRIORITY_BADGE[task.priority] || PRIORITY_BADGE.normal
            }`}
          >
            {PRIORITY_LABELS[task.priority] || task.priority}
          </span>
          {myStatus && (
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                STATUS_BADGE[myStatus]
              }`}
            >
              {STATUS_LABELS[myStatus]}
            </span>
          )}
          {task.is_overdue && (
            <span className="rounded-full bg-red-500 px-2.5 py-0.5 text-xs font-bold text-white">
              Muddati o&apos;tgan
            </span>
          )}
          {task.archived_at && (
            <span className="rounded-full bg-gray-200 px-2.5 py-0.5 text-xs font-bold text-gray-600">
              Arxiv
            </span>
          )}
        </div>

        <h3 className="text-lg font-black leading-tight">{task.title}</h3>
        {task.description && (
          <p className="mt-1 line-clamp-2 text-sm text-gray-500">
            {task.description}
          </p>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
          {task.deadline && (
            <span>
              ⏰ {formatDate(task.deadline)}
            </span>
          )}
          <span>👥 {task.assignee_count} operator</span>
          {isAdmin && (
            <span>
              ✅ {task.completed_count}/{task.assignee_count}
            </span>
          )}
        </div>

        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-100">
          <div
            className="h-full rounded-full bg-green-500 transition-all"
            style={{ width: `${task.completion_percentage}%` }}
          />
        </div>
        <p className="mt-1 text-right text-xs font-semibold text-gray-500">
          {task.completion_percentage}%
        </p>
      </button>
    </Card>
  );
}
