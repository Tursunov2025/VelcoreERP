import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import Toast from "../ui/Toast";

const EMPTY = {
  version_name: "1.0.0",
  version_code: 1,
  apk_url: "",
  release_notes: "",
  force_update: false,
};

export default function MobileAppSettingsTab() {
  const { t } = useLocale();
  const [form, setForm] = useState(EMPTY);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [toast, setToast] = useState("");
  const fileRef = useRef(null);

  const load = () => {
    setLoading(true);
    Promise.all([api.adminGetLatestMobileVersion(), api.adminGetMobileVersions()])
      .then(([latest, list]) => {
        if (latest) {
          setForm({
            version_name: latest.version_name || "1.0.0",
            version_code: latest.version_code || 1,
            apk_url: latest.apk_url || "",
            release_notes: latest.release_notes || "",
            force_update: Boolean(latest.force_update),
          });
        }
        setHistory(list?.items || []);
      })
      .catch((e) => setToast(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const publish = async () => {
    setSaving(true);
    try {
      await api.adminPublishMobileVersion({
        version_name: form.version_name.trim(),
        version_code: Number(form.version_code),
        apk_url: form.apk_url.trim(),
        release_notes: form.release_notes || "",
        force_update: Boolean(form.force_update),
      });
      setToast(t("controlCenter.saved"));
      load();
    } catch (e) {
      setToast(e.message);
    } finally {
      setSaving(false);
    }
  };

  const onApkSelected = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const data = await api.adminUploadMobileApk(file);
      setForm((f) => ({ ...f, apk_url: data.apk_url || data.path || "" }));
      setToast(t("mobileUpdate.apkUploaded"));
    } catch (err) {
      setToast(err.message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  if (loading) return <p>{t("common.loading")}</p>;

  return (
    <div>
      <h2 className="mb-2 text-xl font-black">{t("controlCenter.mobileTitle")}</h2>
      <p className="mb-4 text-sm text-[var(--brand-muted)]">{t("controlCenter.mobileSubtitle")}</p>

      <label className="mb-4 flex items-center gap-3 rounded-xl border bg-white px-4 py-3">
        <input
          type="checkbox"
          checked={Boolean(form.force_update)}
          onChange={(e) => setForm({ ...form, force_update: e.target.checked })}
        />
        <span className="text-sm">{t("controlCenter.forceUpdate")}</span>
      </label>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-bold text-gray-500">
            {t("mobileUpdate.currentVersion")}
          </label>
          <input
            value={form.version_name}
            onChange={(e) => setForm({ ...form, version_name: e.target.value })}
            placeholder="1.0.1"
            className="min-h-[44px] w-full rounded-xl border px-3"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-bold text-gray-500">
            {t("mobileUpdate.versionCode")}
          </label>
          <input
            type="number"
            min={1}
            value={form.version_code}
            onChange={(e) => setForm({ ...form, version_code: e.target.value })}
            className="min-h-[44px] w-full rounded-xl border px-3"
          />
          <p className="mt-1 text-xs text-gray-500">{t("mobileUpdate.versionCodeHint")}</p>
        </div>
        <div className="sm:col-span-2">
          <label className="mb-1 block text-xs font-bold text-gray-500">
            {t("mobileUpdate.apkUrl")}
          </label>
          <input
            value={form.apk_url}
            onChange={(e) => setForm({ ...form, apk_url: e.target.value })}
            className="min-h-[44px] w-full rounded-xl border px-3 font-mono text-sm"
          />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input
              ref={fileRef}
              type="file"
              accept=".apk,application/vnd.android.package-archive"
              className="hidden"
              onChange={onApkSelected}
            />
            <button
              type="button"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
              className="rounded-xl border px-4 py-2 text-sm font-bold"
            >
              {uploading ? t("common.saving") : t("mobileUpdate.uploadApk")}
            </button>
          </div>
        </div>
        <div className="sm:col-span-2">
          <label className="mb-1 block text-xs font-bold text-gray-500">
            {t("mobileUpdate.releaseNotes")}
          </label>
          <textarea
            value={form.release_notes}
            onChange={(e) => setForm({ ...form, release_notes: e.target.value })}
            rows={4}
            className="w-full rounded-xl border px-3 py-2"
          />
        </div>
      </div>

      <button
        type="button"
        disabled={saving}
        onClick={publish}
        className="brand-btn mt-6 rounded-xl px-6 py-3 font-bold text-white"
        style={{ backgroundColor: "var(--brand-button)" }}
      >
        {saving ? t("common.saving") : t("mobileUpdate.publish")}
      </button>

      {history.length > 0 ? (
        <div className="mt-8">
          <h3 className="mb-2 text-sm font-black text-gray-700">{t("mobileUpdate.history")}</h3>
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-3 py-2">Version</th>
                  <th className="px-3 py-2">Code</th>
                  <th className="px-3 py-2">Force</th>
                  <th className="px-3 py-2">Date</th>
                </tr>
              </thead>
              <tbody>
                {history.map((row) => (
                  <tr key={row.id} className="border-t">
                    <td className="px-3 py-2 font-mono">{row.version_name}</td>
                    <td className="px-3 py-2">{row.version_code}</td>
                    <td className="px-3 py-2">{row.force_update ? "Yes" : "—"}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {row.created_at ? row.created_at.slice(0, 16).replace("T", " ") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
