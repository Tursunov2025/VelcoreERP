import { useLocale } from "../../context/LocaleContext";

function formatMinutes(value) {
  const n = Number(value);
  return Number.isNaN(n) ? "0" : String(n);
}

function formatTs(value) {
  if (!value) return null;
  try {
    return new Date(value).toLocaleString();
  } catch {
    return null;
  }
}

export default function MesRouteTimeline({ route, compact = false }) {
  const { t } = useLocale();
  const steps = route?.steps || [];

  if (!route) {
    return (
      <p className="py-6 text-center text-sm text-[var(--brand-muted)]">{t("mes.emptyRoutes")}</p>
    );
  }

  return (
    <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-bold">{t("mes.routeTimeline")}</h3>
          <p className="text-sm text-[var(--brand-muted)]">
            {route.name} · v{route.version}
            {route.is_default ? ` · ${t("mes.defaultRoute")}` : ""}
          </p>
        </div>
        <div className="text-sm">
          <span className="text-[var(--brand-muted)]">{t("mes.estimatedTotal")}: </span>
          <strong>{formatMinutes(route.estimated_total_minutes)} min</strong>
        </div>
      </div>

      {steps.length === 0 ? (
        <p className="py-6 text-center text-[var(--brand-muted)]">{t("mes.emptyRouteSteps")}</p>
      ) : (
        <ol className="relative space-y-0 border-l-2 border-gray-200 pl-6">
          {steps.map((step, index) => {
            const started = formatTs(step.started_at);
            const accepted = formatTs(step.accepted_at);
            const completed = formatTs(step.completed_at);
            return (
              <li key={step.id} className="relative pb-6 last:pb-0">
                <span
                  className="absolute -left-[1.35rem] top-1 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white text-[10px] font-bold text-white"
                  style={{ backgroundColor: step.stage_color || "var(--brand-button)" }}
                >
                  {index + 1}
                </span>
                <div className="rounded-xl border bg-white/50 p-3 dark:bg-black/10">
                  <p className="font-bold">{step.stage_name}</p>
                  <p className="text-sm text-[var(--brand-muted)]">
                    {step.department || "—"}
                    {step.responsible_role ? ` · ${step.responsible_role}` : ""}
                  </p>
                  {!compact && (
                    <dl className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                      <div>
                        <dt className="text-[var(--brand-muted)]">{t("mes.estimatedMinutes")}</dt>
                        <dd className="font-semibold">{formatMinutes(step.estimated_minutes)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--brand-muted)]">{t("mes.requiredParts")}</dt>
                        <dd>{step.required_parts_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--brand-muted)]">{t("mes.completedParts")}</dt>
                        <dd>{step.completed_parts_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--brand-muted)]">{t("mes.stepRequired")}</dt>
                        <dd>{step.is_required ? t("common.yes") : t("common.no")}</dd>
                      </div>
                    </dl>
                  )}
                  {(started || accepted || completed) && (
                    <div className="mt-2 space-y-0.5 text-xs text-[var(--brand-muted)]">
                      {started && (
                        <p>
                          {t("mes.startedAt")}: {started}
                        </p>
                      )}
                      {accepted && (
                        <p>
                          {t("mes.acceptedAt")}: {accepted}
                        </p>
                      )}
                      {completed && (
                        <p>
                          {t("mes.completedAt")}: {completed}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
