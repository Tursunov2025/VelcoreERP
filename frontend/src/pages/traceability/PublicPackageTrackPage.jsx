import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api/client";
import Card from "../../components/ui/Card";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";

function fmtDate(v) {
  if (!v) return "—";
  try {
    return new Date(v).toLocaleDateString();
  } catch {
    return String(v);
  }
}

export default function PublicPackageTrackPage() {
  const { labelCode } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!labelCode) return;
    setLoading(true);
    api
      .publicPackageTrack(labelCode)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [labelCode]);

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center p-6"
      style={{ backgroundColor: "var(--brand-background, #f5f5f5)" }}
    >
      <div className="w-full max-w-md">
        <p className="mb-6 text-center text-2xl font-black tracking-wide">AZMUS FURNITURE</p>
        {loading ? (
          <LoadingSpinner />
        ) : error || !data ? (
          <ErrorAlert message={error || "Package not found"} />
        ) : (
          <Card>
            <p className="text-sm text-[var(--brand-muted)]">Tracking</p>
            <p className="mt-1 text-xl font-bold">{data.label_code}</p>
            <dl className="mt-6 space-y-3 text-sm">
              <div>
                <dt className="text-[var(--brand-muted)]">Product</dt>
                <dd className="font-semibold">{data.product || "—"}</dd>
              </div>
              <div>
                <dt className="text-[var(--brand-muted)]">Status</dt>
                <dd className="font-semibold capitalize">{data.status || "—"}</dd>
              </div>
              <div>
                <dt className="text-[var(--brand-muted)]">Production completed</dt>
                <dd className="font-semibold">{fmtDate(data.production_completed_date)}</dd>
              </div>
              <div>
                <dt className="text-[var(--brand-muted)]">Dispatch date</dt>
                <dd className="font-semibold">{fmtDate(data.dispatch_date)}</dd>
              </div>
            </dl>
          </Card>
        )}
      </div>
    </div>
  );
}
