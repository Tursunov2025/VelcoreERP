import { useCallback, useEffect, useRef, useState } from "react";
import Modal from "../modals/Modal";
import ErrorAlert from "../ui/ErrorAlert";
import { api, uploadUrl } from "../../api/client";
import {
  OPERATOR_NEXT,
  PRIORITY_BADGE,
  PRIORITY_LABELS,
  STATUS_BADGE,
  STATUS_LABELS,
} from "../../constants/tasks";
import { useAuth } from "../../context/AuthContext";

function fmt(value) {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

export default function TaskDetailModal({ taskId, onClose, onChanged }) {
  const { username, isAdmin } = useAuth();
  const [task, setTask] = useState(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const data = await api.getTask(taskId);
      setTask(data);
    } catch (err) {
      setError(err.message);
    }
  }, [taskId]);

  useEffect(() => {
    load();
  }, [load]);

  if (!task) {
    return (
      <Modal onClose={onClose}>
        <p className="py-8 text-center text-gray-500">Yuklanmoqda...</p>
      </Modal>
    );
  }

  const myAssignment = task.assignments?.find(
    (a) => a.operator_username === username
  );

  const setStatus = async (status) => {
    if (!myAssignment) return;
    setBusy(true);
    setError("");
    try {
      await api.changeTaskStatus(myAssignment.id, { status, comment: "" });
      await load();
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const sendComment = async () => {
    if (!comment.trim()) return;
    setBusy(true);
    try {
      await api.addTaskComment({
        task_id: task.id,
        content: comment.trim(),
        assignment_id: myAssignment?.id || null,
      });
      setComment("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const uploadResult = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const up = await api.uploadAnyFile(file);
      await api.addTaskAttachment({
        task_id: task.id,
        url: up.url,
        filename: up.filename,
        content_type: up.content_type,
        kind: isAdmin ? "task" : "result",
      });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const nextStatuses = myAssignment ? OPERATOR_NEXT[myAssignment.status] || [] : [];

  return (
    <Modal onClose={onClose}>
      <div className="max-h-[82vh] overflow-y-auto">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
              PRIORITY_BADGE[task.priority]
            }`}
          >
            {PRIORITY_LABELS[task.priority]}
          </span>
          {task.is_overdue && (
            <span className="rounded-full bg-red-500 px-2.5 py-0.5 text-xs font-bold text-white">
              Muddati o&apos;tgan
            </span>
          )}
        </div>

        <h2 className="text-xl font-black">{task.title}</h2>
        {task.deadline && (
          <p className="mt-1 text-sm text-gray-500">⏰ Muddat: {fmt(task.deadline)}</p>
        )}
        {task.description && (
          <p className="mt-3 whitespace-pre-wrap text-sm text-gray-700">
            {task.description}
          </p>
        )}

        <ErrorAlert message={error} />

        {/* Operator status controls */}
        {myAssignment && (
          <div className="mt-4 rounded-2xl border p-4">
            <p className="mb-2 text-sm font-bold">
              Mening holatim:{" "}
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  STATUS_BADGE[myAssignment.status]
                }`}
              >
                {STATUS_LABELS[myAssignment.status]}
              </span>
            </p>
            <div className="flex flex-wrap gap-2">
              {nextStatuses.map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={busy}
                  onClick={() => setStatus(s)}
                  className={`rounded-xl px-4 py-2 text-sm font-bold text-white disabled:opacity-50 ${
                    s === "completed"
                      ? "bg-green-600"
                      : s === "cancelled"
                      ? "bg-red-500"
                      : "bg-black"
                  }`}
                >
                  {STATUS_LABELS[s]}
                </button>
              ))}
              {nextStatuses.length === 0 && (
                <p className="text-sm text-gray-400">
                  Vazifa yakunlangan
                </p>
              )}
            </div>
            <div className="mt-3">
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.doc,.docx,.xls,.xlsx,image/*"
                onChange={uploadResult}
                className="text-sm"
              />
              <p className="mt-1 text-xs text-gray-400">
                Natija faylini yuklash
              </p>
            </div>
          </div>
        )}

        {/* Admin assignment overview */}
        {isAdmin && (
          <div className="mt-4">
            <h3 className="mb-2 text-sm font-bold">
              Operatorlar holati ({task.completed_count}/{task.assignee_count})
            </h3>
            <div className="space-y-1">
              {task.assignments.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between rounded-xl bg-gray-50 px-3 py-2 text-sm"
                >
                  <span className="font-medium">{a.operator_username}</span>
                  <div className="flex items-center gap-2">
                    {a.completed_at && (
                      <span className="text-xs text-gray-400">
                        {fmt(a.completed_at)}
                      </span>
                    )}
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                        STATUS_BADGE[a.status]
                      }`}
                    >
                      {STATUS_LABELS[a.status]}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Attachments */}
        {task.attachments?.length > 0 && (
          <div className="mt-4">
            <h3 className="mb-2 text-sm font-bold">Fayllar</h3>
            <div className="space-y-1">
              {task.attachments.map((a) => (
                <a
                  key={a.id}
                  href={uploadUrl(a.url)}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between rounded-xl bg-gray-50 px-3 py-2 text-sm hover:bg-gray-100"
                >
                  <span className="truncate underline">📎 {a.filename}</span>
                  <span className="ml-2 shrink-0 text-xs text-gray-400">
                    {a.kind === "result" ? "natija" : "vazifa"} · {a.uploaded_by}
                  </span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* History + comments */}
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-bold">Izoh va tarix</h3>
          <div className="space-y-2">
            {task.comments?.map((c) => (
              <div
                key={c.id}
                className={`rounded-xl px-3 py-2 text-sm ${
                  c.kind === "status" ? "bg-blue-50" : "bg-gray-50"
                }`}
              >
                <div className="flex justify-between gap-2">
                  <span className="font-semibold">{c.username}</span>
                  <span className="text-xs text-gray-400">{fmt(c.created_at)}</span>
                </div>
                {c.kind === "status" ? (
                  <p className="text-gray-600">
                    holatni <b>{STATUS_LABELS[c.status_value] || c.status_value}</b> ga
                    o&apos;zgartirdi
                    {c.content ? ` — ${c.content}` : ""}
                  </p>
                ) : (
                  <p className="text-gray-700">{c.content}</p>
                )}
              </div>
            ))}
            {(!task.comments || task.comments.length === 0) && (
              <p className="text-sm text-gray-400">Hozircha izoh yo&apos;q</p>
            )}
          </div>

          <div className="mt-3 flex gap-2">
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendComment()}
              placeholder="Izoh yozing..."
              className="flex-1 rounded-2xl border px-4 py-2 text-sm"
            />
            <button
              type="button"
              onClick={sendComment}
              disabled={busy}
              className="rounded-2xl bg-black px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
            >
              Yuborish
            </button>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="mt-5 w-full rounded-2xl bg-gray-100 py-3 font-bold"
        >
          Yopish
        </button>
      </div>
    </Modal>
  );
}
