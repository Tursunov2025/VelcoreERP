import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import TaskCard from "../components/tasks/TaskCard";
import TaskFormModal from "../components/tasks/TaskFormModal";
import TaskDetailModal from "../components/tasks/TaskDetailModal";
import { PRIORITIES, PRIORITY_LABELS } from "../constants/tasks";
import { useAuth } from "../context/AuthContext";
import { useLocale } from "../context/LocaleContext";

export default function TasksPage() {
  const { isAdmin } = useAuth();
  const { t } = useLocale();

  const TABS = isAdmin
    ? [
        { id: "all", label: "Barcha vazifalar" },
        { id: "completed", label: "Bajarilgan" },
        { id: "overdue", label: "Muddati o'tgan" },
        { id: "archived", label: "Arxiv" },
      ]
    : [
        { id: "mine", label: "Mening vazifalarim" },
        { id: "completed", label: "Bajarilgan" },
        { id: "overdue", label: "Muddati o'tgan" },
      ];

  const [tab, setTab] = useState(isAdmin ? "all" : "mine");
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [priority, setPriority] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editTask, setEditTask] = useState(null);
  const [detailId, setDetailId] = useState(null);

  const buildParams = useCallback(() => {
    const params = { q: search, priority };
    if (tab === "mine") params.scope = "mine";
    if (tab === "all") params.scope = "all";
    if (tab === "completed") {
      params.scope = isAdmin ? "all" : "mine";
      params.status = "completed";
    }
    if (tab === "overdue") {
      params.scope = isAdmin ? "all" : "mine";
      params.overdue = true;
    }
    if (tab === "archived") params.archived = true;
    return params;
  }, [tab, search, priority, isAdmin]);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await api.getTasks(buildParams());
      setTasks(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  useEffect(() => {
    setLoading(true);
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  const handleSaved = () => {
    setShowForm(false);
    setEditTask(null);
    load();
  };

  const openEdit = (task) => {
    setDetailId(null);
    setEditTask(task);
    setShowForm(true);
  };

  const removeTask = async (task) => {
    if (!window.confirm(`"${task.title}" vazifasini o'chirasizmi?`)) return;
    try {
      await api.deleteTask(task.id);
      setDetailId(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const archiveTask = async (task) => {
    try {
      await api.archiveTask(task.id);
      setDetailId(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <PageHeader
        title={t("tasks.title")}
        subtitle={t("tasks.subtitle")}
        actions={
          isAdmin && (
            <button
              type="button"
              onClick={() => {
                setEditTask(null);
                setShowForm(true);
              }}
              className="rounded-2xl bg-black px-5 py-3 font-bold text-white"
            >
              + Yangi vazifa
            </button>
          )
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`rounded-2xl px-4 py-2 text-sm font-bold ${
              tab === t.id ? "bg-black text-white" : "bg-gray-200 text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Qidiruv..."
          className="flex-1 rounded-2xl border px-4 py-2 text-sm"
        />
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          className="rounded-2xl border px-4 py-2 text-sm"
        >
          <option value="">Barcha muhimlik</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABELS[p]}
            </option>
          ))}
        </select>
      </div>

      <ErrorAlert message={error} onRetry={load} />

      {loading && !tasks.length ? (
        <LoadingSpinner />
      ) : tasks.length === 0 ? (
        <p className="py-12 text-center text-gray-400">Vazifa topilmadi</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              isAdmin={isAdmin}
              onOpen={() => setDetailId(task.id)}
            />
          ))}
        </div>
      )}

      {showForm && (
        <TaskFormModal
          task={editTask}
          onClose={() => {
            setShowForm(false);
            setEditTask(null);
          }}
          onSaved={handleSaved}
        />
      )}

      {detailId && (
        <TaskDetailModal
          taskId={detailId}
          onClose={() => setDetailId(null)}
          onChanged={load}
        />
      )}

      {/* Admin quick actions inside detail are handled here via toolbar when needed */}
      {isAdmin && detailId && (
        <AdminTaskToolbar
          task={tasks.find((t) => t.id === detailId)}
          onEdit={openEdit}
          onDelete={removeTask}
          onArchive={archiveTask}
        />
      )}
    </div>
  );
}

function AdminTaskToolbar({ task, onEdit, onDelete, onArchive }) {
  if (!task) return null;
  return (
    <div className="fixed bottom-4 left-1/2 z-[60] flex -translate-x-1/2 gap-2 rounded-2xl bg-black/90 px-3 py-2 shadow-xl">
      <button
        type="button"
        onClick={() => onEdit(task)}
        className="rounded-xl bg-white/15 px-3 py-2 text-xs font-bold text-white"
      >
        Tahrirlash
      </button>
      <button
        type="button"
        onClick={() => onArchive(task)}
        className="rounded-xl bg-white/15 px-3 py-2 text-xs font-bold text-white"
      >
        {task.archived_at ? "Arxivdan chiqarish" : "Arxivlash"}
      </button>
      <button
        type="button"
        onClick={() => onDelete(task)}
        className="rounded-xl bg-red-500 px-3 py-2 text-xs font-bold text-white"
      >
        O&apos;chirish
      </button>
    </div>
  );
}
