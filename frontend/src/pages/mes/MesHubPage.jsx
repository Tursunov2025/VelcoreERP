import { Link } from "react-router-dom";
import PageHeader from "../../components/ui/PageHeader";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

export default function MesHubPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = hasPermission("mes_view");
  const canLazer = isAdmin || hasPermission("mes_terminal_lazer");
  const canSvarshik = isAdmin || hasPermission("mes_terminal_svarshik");
  const canKraska = isAdmin || hasPermission("mes_terminal_kraska");
  const canQc = isAdmin || hasPermission("mes_terminal_qc");
  const canPackaging = isAdmin || hasPermission("mes_terminal_packaging");
  const canWarehouse = isAdmin || hasPermission("mes_terminal_warehouse");
  const canDispatch = isAdmin || hasPermission("mes_terminal_dispatch");

  if (!canView && !canLazer && !canSvarshik && !canKraska && !canQc && !canPackaging && !canWarehouse && !canDispatch) {
    return (
      <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>
    );
  }

  const cards = [
    ...(canLazer
      ? [
          {
            to: "/mes/terminal/lazer",
            title: t("mes.hubLazerTerminal"),
            desc: t("mes.hubLazerTerminalDesc"),
            emoji: "⚡",
          },
        ]
      : []),
    ...(canSvarshik
      ? [
          {
            to: "/mes/terminal/svarshik",
            title: t("mes.hubSvarshikTerminal"),
            desc: t("mes.hubSvarshikTerminalDesc"),
            emoji: "🔥",
          },
        ]
      : []),
    ...(canKraska
      ? [
          {
            to: "/mes/terminal/kraska",
            title: t("mes.hubKraskaTerminal"),
            desc: t("mes.hubKraskaTerminalDesc"),
            emoji: "🎨",
          },
        ]
      : []),
    ...(canQc
      ? [
          {
            to: "/mes/terminal/qc",
            title: t("mes.hubQcTerminal"),
            desc: t("mes.hubQcTerminalDesc"),
            emoji: "🔍",
          },
        ]
      : []),
    ...(canPackaging
      ? [
          {
            to: "/mes/terminal/packaging",
            title: t("mes.hubPackagingTerminal"),
            desc: t("mes.hubPackagingTerminalDesc"),
            emoji: "📦",
          },
        ]
      : []),
    ...(canWarehouse
      ? [
          {
            to: "/mes/terminal/warehouse",
            title: t("mes.hubWarehouseTerminal"),
            desc: t("mes.hubWarehouseTerminalDesc"),
            emoji: "🏢",
          },
        ]
      : []),
    ...(canDispatch
      ? [
          {
            to: "/mes/terminal/dispatch",
            title: t("mes.hubDispatchTerminal"),
            desc: t("mes.hubDispatchTerminalDesc"),
            emoji: "🚚",
          },
        ]
      : []),
    ...(canView
      ? [
          {
            to: "/mes/monitor",
            title: t("mes.hubProductionMonitor"),
            desc: t("mes.hubProductionMonitorDesc"),
            emoji: "📊",
          },
          {
            to: "/mes/jobs",
            title: t("mes.hubJobs"),
            desc: t("mes.hubJobsDesc"),
            emoji: "🏭",
          },
          {
            to: "/mes/templates",
            title: t("mes.hubTemplates"),
            desc: t("mes.hubTemplatesDesc"),
            emoji: "📦",
          },
          {
            to: "/mes/categories",
            title: t("mes.hubCategories"),
            desc: t("mes.hubCategoriesDesc"),
            emoji: "🗂️",
          },
          {
            to: "/mes/parts",
            title: t("mes.hubParts"),
            desc: t("mes.hubPartsDesc"),
            emoji: "🔩",
          },
        ]
      : []),
  ];

  return (
    <div>
      <PageHeader title={t("mes.title")} subtitle={t("mes.subtitle")} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="rounded-2xl border bg-[var(--brand-card)] p-6 shadow-sm transition hover:border-[var(--brand-primary)]"
          >
            <span className="text-3xl">{card.emoji}</span>
            <h3 className="mt-3 text-lg font-bold">{card.title}</h3>
            <p className="mt-1 text-sm text-[var(--brand-muted)]">{card.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
