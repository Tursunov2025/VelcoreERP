import { useEffect, useState } from "react";
import Modal from "../modals/Modal";
import ErrorAlert from "../ui/ErrorAlert";
import { api, uploadUrl } from "../../api/client";
import { PRIORITIES, PRIORITY_LABELS } from "../../constants/tasks";

function toLocalInput(value) {
  if (!value) return "";
  const d = new Date(value);
  const off = d.getTimezoneOffset();
  const local = new Date(d.getTime() - off * 60000);
  return local.toISOString().slice(0, 16);
}

export default function TaskFormModal({ task, onClose, onSaved }) {
  const editing = Boolean(task);
  const [title, setTitle] = useState(task?.title || "");
  const [description, setDescription] = useState(task?.description || "");
  const [priority, setPriority] = useState(task?.priority || "normal");
  const [deadline, setDeadline] = useState(toLocalInput(task?.deadline));
  const [assignAll, setAssignAll] = useState(task?.assign_all || false);
  const [selected, setSelected] = useState(
    task?.assignments?.map((a) => a.operator_username) || []
  );
  const [operators, setOperators] = useState([]);
  const [attachments, setAttachments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getUsers()
      .then((users) =>
        setOperators(users.filter((u) => u.role === "operator"))
      )
      .catch(() => setOperators([]));
  }, []);

  const toggleOperator = (username) => {
    setSelected((prev) =>
      prev.includes(username)
        ? prev.filter((u) => u !== username)
        : [...prev, username]
    );
  };

  const onFiles = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    setError("");
    const uploaded = [];
    const failures = [];
    try {
      for (const file of files) {
        try {
          const up = await api.uploadAnyFile(file);
          uploaded.push({ ...up, kind: "task" });
        } catch (err) {
          failures.push(`${file.name}: ${err.message}`);
        }
      }
      if (uploaded.length) {
        setAttachments((prev) => [...prev, ...uploaded]);
      }
      if (failures.length) {
        setError(failures.join("; "));
      }
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const submit = async () => {
    if (!title.trim()) {
      setError("Sarlavha kiriting");
      return;
    }
    if (!assignAll && selected.length === 0) {
      setError("Kamida bitta operator tanlang yoki 'Hammaga' ni belgilang");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload = {
        title: title.trim(),
        description,
        priority,
        deadline: deadline ? new Date(deadline).toISOString() : null,
        assign_all: assignAll,
        assignee_usernames: assignAll ? [] : selected,
      };
      if (editing) {
        await api.updateTask(task.id, payload);
      } else {
        await api.createTask({ ...payload, attachments });
      }
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal onClose={onClose}>
      <div className="max-h-[80vh] overflow-y-auto">
        <h2 className="mb-4 text-xl font-black">
          {editing ? "Vazifani tahrirlash" : "Yangi vazifa"}
        </h2>
        <ErrorAlert message={error} />

        <div className="space-y-3">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Sarlavha"
            className="w-full rounded-2xl border px-4 py-3"
          />
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Tavsif"
            className="min-h-[90px] w-full rounded-2xl border px-4 py-3"
          />

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold text-gray-500">
                Muhimlik
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full rounded-2xl border px-4 py-3"
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {PRIORITY_LABELS[p]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-gray-500">
                Muddat
              </label>
              <input
                type="datetime-local"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
                className="w-full rounded-2xl border px-4 py-3"
              />
            </div>
          </div>

          <label className="flex items-center gap-2 rounded-2xl border px-4 py-3">
            <input
              type="checkbox"
              checked={assignAll}
              onChange={(e) => setAssignAll(e.target.checked)}
            />
            <span className="text-sm font-semibold">
              Barcha operatorlarga yuborish
            </span>
          </label>

          {!assignAll && (
            <div>
              <p className="mb-1 text-xs font-semibold text-gray-500">
                Operatorlar ({selected.length})
              </p>
              <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto rounded-2xl border p-3">
                {operators.map((op) => (
                  <button
                    key={op.username}
                    type="button"
                    onClick={() => toggleOperator(op.username)}
                    className={`rounded-full px-3 py-1.5 text-sm font-semibold ${
                      selected.includes(op.username)
                        ? "bg-black text-white"
                        : "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {op.username}
                    <span className="ml-1 text-xs opacity-60">
                      {op.department}
                    </span>
                  </button>
                ))}
                {operators.length === 0 && (
                  <p className="text-sm text-gray-400">Operator topilmadi</p>
                )}
              </div>
            </div>
          )}

          {!editing && (
            <div>
              <p className="mb-1 text-xs font-semibold text-gray-500">
                Fayllar (PDF, Word, Excel, rasm)
              </p>
              <input
                type="file"
                multiple
                accept=".pdf,.doc,.docx,.xls,.xlsx,image/*"
                onChange={onFiles}
                className="w-full text-sm"
              />
              {uploading && (
                <p className="mt-1 text-xs text-gray-400">Yuklanmoqda...</p>
              )}
              <div className="mt-2 space-y-1">
                {attachments.map((a, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-xl bg-gray-50 px-3 py-2 text-sm"
                  >
                    <a
                      href={uploadUrl(a.url)}
                      target="_blank"
                      rel="noreferrer"
                      className="truncate underline"
                    >
                      📎 {a.filename}
                    </a>
                    <button
                      type="button"
                      onClick={() =>
                        setAttachments((prev) =>
                          prev.filter((_, idx) => idx !== i)
                        )
                      }
                      className="ml-2 text-red-500"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="mt-6 flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-2xl bg-gray-100 py-3 font-bold"
          >
            Bekor
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={saving || uploading}
            className="flex-1 rounded-2xl bg-black py-3 font-bold text-white disabled:opacity-50"
          >
            {saving ? "Saqlanmoqda..." : editing ? "Saqlash" : "Yaratish"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
