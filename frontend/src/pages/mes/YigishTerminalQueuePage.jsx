import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";

const STEP_LABELS = {
  pending: "Kutilmoqda",
  accepted: "Qabul qilingan",
  in_progress: "Jarayonda",
  completed: "Yakunlangan",
};

function getStepState(job) {
  return (
    job?.yigish_step?.state ||
    job?.step_state ||
    job?.status ||
    "pending"
  );
}

function getProgress(job) {
  const value =
    job?.yigish_progress_pct ??
    job?.progress_pct ??
    job?.progress ??
    0;

  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, Math.round(n)));
}

function getPartsCount(job) {
  return Number(
    job?.yigish_part_count ??
      job?.yigish_parts?.length ??
      job?.parts_count ??
      job?.part_count ??
      0
  );
}

function getPlannedQty(job) {
  return Number(
    job?.planned_qty ??
      job?.quantity ??
      job?.qty ??
      job?.plan_qty ??
      job?.yigish_step?.planned_qty ??
      0
  );
}

function getCompletedQty(job) {
  return Number(
    job?.completed_qty ??
      job?.yigish_completed_qty ??
      job?.yigish_step?.completed_qty ??
      job?.completed ??
      0
  );
}

function getRemainingQty(job) {
  const planned = getPlannedQty(job);
  const completed = getCompletedQty(job);

  if (planned > 0) {
    return Math.max(0, planned - completed);
  }

  return Number(
    job?.remaining_qty ??
      job?.yigish_remaining_qty ??
      job?.remaining ??
      0
  );
}

function getCustomer(job) {
  return (
    job?.customer_name ||
    job?.customer ||
    job?.client_name ||
    job?.order_customer ||
    "Mijoz ko‘rsatilmagan"
  );
}

function getProduct(job) {
  return (
    job?.template_name ||
    job?.template_code ||
    job?.product_name ||
    job?.product ||
    "Yig‘ish topshirig‘i"
  );
}

function getProject(job) {
  const project = job?.project;

  if (project && typeof project === "object") {
    const code =
      project.code ??
      project.project_code ??
      "";
    const name =
      project.name ??
      project.project_name ??
      "";

    const label = [code, name]
      .filter(Boolean)
      .join(" · ");

    return label || "—";
  }

  return (
    job?.project_code ||
    job?.project_name ||
    job?.order_number ||
    (typeof project === "string" ? project : "—")
  );
}

function formatDate(value) {
  if (!value) return "—";

  try {
    return new Date(value).toLocaleString("uz-UZ", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function stateStyle(state) {
  switch (state) {
    case "completed":
      return {
        background: "#ecfdf3",
        color: "#087443",
        border: "#a7f3d0",
        dot: "#12b76a",
      };

    case "in_progress":
      return {
        background: "#eff8ff",
        color: "#175cd3",
        border: "#b2ddff",
        dot: "#2e90fa",
      };

    case "accepted":
      return {
        background: "#f4f3ff",
        color: "#5925dc",
        border: "#d9d6fe",
        dot: "#7a5af8",
      };

    default:
      return {
        background: "#fffaeb",
        color: "#b54708",
        border: "#fedf89",
        dot: "#f79009",
      };
  }
}

function StatIcon({ children, background }) {
  return (
    <div
      style={{
        width: 46,
        height: 46,
        minWidth: 46,
        borderRadius: 14,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background,
        fontSize: 22,
      }}
    >
      {children}
    </div>
  );
}

export default function YigishTerminalQueuePage() {
  const navigate = useNavigate();

  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState("");
  const [showFilter, setShowFilter] = useState(false);

  const loadQueue = useCallback(async (silent = false) => {
    try {
      if (silent) setRefreshing(true);
      else setLoading(true);

      setError("");

      const data = await api.mesYigishQueue();

      const list = Array.isArray(data)
        ? data
        : Array.isArray(data?.items)
          ? data.items
          : Array.isArray(data?.jobs)
            ? data.jobs
            : [];

      setJobs(list);
    } catch (err) {
      console.error("Yig‘ish queue error:", err);
      setError(err?.message || "Yig‘ish navbatini yuklashda xatolik");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();

    const timer = setInterval(() => {
      loadQueue(true);
    }, 15000);

    return () => clearInterval(timer);
  }, [loadQueue]);

  const counts = useMemo(() => {
    return {
      all: jobs.length,
      pending: jobs.filter((j) => getStepState(j) === "pending").length,
      accepted: jobs.filter((j) => getStepState(j) === "accepted").length,
      in_progress: jobs.filter(
        (j) => getStepState(j) === "in_progress"
      ).length,
      completed: jobs.filter(
        (j) => getStepState(j) === "completed"
      ).length,
    };
  }, [jobs]);

  const filteredJobs = useMemo(() => {
    const q = search.trim().toLowerCase();

    return jobs.filter((job) => {
      const state = getStepState(job);

      if (tab !== "all" && state !== tab) {
        return false;
      }

      if (!q) return true;

      const text = [
        job?.id,
        job?.job_number,
        job?.template_code,
        job?.template_name,
        job?.product_name,
        job?.project_code,
        job?.project_name,
        getCustomer(job),
        getProduct(job),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return text.includes(q);
    });
  }, [jobs, search, tab]);

  const openJob = (job) => {
    if (!job?.id) return;
    navigate(`/mes/terminal/yigish/jobs/${job.id}`);
  };

  const tabs = [
    { key: "all", label: "Barchasi", count: counts.all },
    { key: "pending", label: "Kutilmoqda", count: counts.pending },
    {
      key: "in_progress",
      label: "Jarayonda",
      count: counts.in_progress,
    },
    {
      key: "completed",
      label: "Yakunlangan",
      count: counts.completed,
    },
  ];

  return (
    <div
      style={{
        padding: "4px 2px 28px",
        color: "var(--brand-text, #101828)",
      }}
    >
      {/* HEADER */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 16,
          marginBottom: 22,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 13,
                background: "#eef4ff",
                color: "#175cd3",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 23,
              }}
            >
              🔧
            </div>

            <div>
              <h1
                style={{
                  margin: 0,
                  fontSize: 28,
                  lineHeight: 1.15,
                  fontWeight: 800,
                  letterSpacing: "-0.6px",
                }}
              >
                Yig‘ish Terminali
              </h1>

              <p
                style={{
                  margin: "5px 0 0",
                  color: "#667085",
                  fontSize: 14,
                }}
              >
                Yig‘ish ishlab chiqarish navbati va topshiriqlari
              </p>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => loadQueue(true)}
          disabled={refreshing}
          style={{
            minHeight: 42,
            padding: "0 16px",
            borderRadius: 10,
            border: "1px solid #d0d5dd",
            background: "#fff",
            color: "#344054",
            fontWeight: 700,
            cursor: refreshing ? "default" : "pointer",
            opacity: refreshing ? 0.65 : 1,
            boxShadow: "0 1px 2px rgba(16,24,40,.05)",
          }}
        >
          {refreshing ? "↻ Yangilanmoqda..." : "↻ Yangilash"}
        </button>
      </div>

      {/* STATS */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: 14,
          marginBottom: 18,
        }}
      >
        <div
          style={{
            background: "#fff",
            border: "1px solid #eaecf0",
            borderRadius: 16,
            padding: 18,
            boxShadow: "0 1px 3px rgba(16,24,40,.05)",
            display: "flex",
            alignItems: "center",
            gap: 14,
          }}
        >
          <StatIcon background="#eff8ff">📋</StatIcon>
          <div>
            <div style={{ fontSize: 13, color: "#667085", marginBottom: 4 }}>
              Jami navbat
            </div>
            <div style={{ fontSize: 26, fontWeight: 800 }}>
              {counts.all}
            </div>
            <div style={{ fontSize: 12, color: "#175cd3", marginTop: 2 }}>
              Barcha topshiriqlar
            </div>
          </div>
        </div>

        <div
          style={{
            background: "#fff",
            border: "1px solid #eaecf0",
            borderRadius: 16,
            padding: 18,
            boxShadow: "0 1px 3px rgba(16,24,40,.05)",
            display: "flex",
            alignItems: "center",
            gap: 14,
          }}
        >
          <StatIcon background="#fffaeb">⏱️</StatIcon>
          <div>
            <div style={{ fontSize: 13, color: "#667085", marginBottom: 4 }}>
              Kutilmoqda
            </div>
            <div style={{ fontSize: 26, fontWeight: 800 }}>
              {counts.pending}
            </div>
            <div style={{ fontSize: 12, color: "#b54708", marginTop: 2 }}>
              Qabul qilish kerak
            </div>
          </div>
        </div>

        <div
          style={{
            background: "#fff",
            border: "1px solid #eaecf0",
            borderRadius: 16,
            padding: 18,
            boxShadow: "0 1px 3px rgba(16,24,40,.05)",
            display: "flex",
            alignItems: "center",
            gap: 14,
          }}
        >
          <StatIcon background="#eff8ff">▶️</StatIcon>
          <div>
            <div style={{ fontSize: 13, color: "#667085", marginBottom: 4 }}>
              Jarayonda
            </div>
            <div style={{ fontSize: 26, fontWeight: 800 }}>
              {counts.in_progress}
            </div>
            <div style={{ fontSize: 12, color: "#175cd3", marginTop: 2 }}>
              Yig‘ish davom etmoqda
            </div>
          </div>
        </div>

        <div
          style={{
            background: "#fff",
            border: "1px solid #eaecf0",
            borderRadius: 16,
            padding: 18,
            boxShadow: "0 1px 3px rgba(16,24,40,.05)",
            display: "flex",
            alignItems: "center",
            gap: 14,
          }}
        >
          <StatIcon background="#ecfdf3">✓</StatIcon>
          <div>
            <div style={{ fontSize: 13, color: "#667085", marginBottom: 4 }}>
              Yakunlangan
            </div>
            <div style={{ fontSize: 26, fontWeight: 800 }}>
              {counts.completed}
            </div>
            <div style={{ fontSize: 12, color: "#087443", marginTop: 2 }}>
              Yig‘ish tugagan
            </div>
          </div>
        </div>
      </div>

      {/* ERROR */}
      {error && (
        <div
          style={{
            marginBottom: 16,
            padding: "12px 14px",
            borderRadius: 10,
            background: "#fef3f2",
            border: "1px solid #fecdca",
            color: "#b42318",
            fontSize: 14,
          }}
        >
          {error}
        </div>
      )}

      {/* CONTROLS */}
      <div
        style={{
          background: "#fff",
          border: "1px solid #eaecf0",
          borderRadius: 16,
          padding: 12,
          marginBottom: 14,
          boxShadow: "0 1px 3px rgba(16,24,40,.04)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            justifyContent: "space-between",
            flexWrap: "wrap",
          }}
        >
          <div
            style={{
              display: "flex",
              gap: 6,
              flexWrap: "wrap",
            }}
          >
            {tabs.map((item) => {
              const active = tab === item.key;

              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setTab(item.key)}
                  style={{
                    border: "1px solid",
                    borderColor: active ? "#2e90fa" : "#eaecf0",
                    background: active ? "#eff8ff" : "#fff",
                    color: active ? "#175cd3" : "#475467",
                    borderRadius: 9,
                    padding: "9px 13px",
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                  }}
                >
                  {item.label}
                  <span
                    style={{
                      marginLeft: 7,
                      display: "inline-flex",
                      minWidth: 21,
                      height: 21,
                      padding: "0 6px",
                      borderRadius: 99,
                      alignItems: "center",
                      justifyContent: "center",
                      background: active ? "#d1e9ff" : "#f2f4f7",
                      color: active ? "#175cd3" : "#667085",
                      fontSize: 11,
                    }}
                  >
                    {item.count}
                  </span>
                </button>
              );
            })}
          </div>

          <div
            style={{
              display: "flex",
              gap: 8,
              alignItems: "center",
              flex: "1 1 360px",
              justifyContent: "flex-end",
            }}
          >
            <div
              style={{
                position: "relative",
                width: "min(360px, 100%)",
              }}
            >
              <span
                style={{
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "#98a2b3",
                  fontSize: 16,
                }}
              >
                🔎
              </span>

              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Ish raqami, mahsulot, loyiha..."
                style={{
                  width: "100%",
                  height: 40,
                  boxSizing: "border-box",
                  border: "1px solid #d0d5dd",
                  borderRadius: 9,
                  padding: "0 12px 0 36px",
                  outline: "none",
                  fontSize: 13,
                  color: "#101828",
                  background: "#fff",
                }}
              />
            </div>

            <button
              type="button"
              onClick={() => setShowFilter((v) => !v)}
              style={{
                height: 40,
                padding: "0 13px",
                borderRadius: 9,
                border: "1px solid #d0d5dd",
                background: showFilter ? "#f2f4f7" : "#fff",
                color: "#344054",
                fontWeight: 700,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              ☷ Filter
            </button>
          </div>
        </div>

        {showFilter && (
          <div
            style={{
              marginTop: 12,
              paddingTop: 12,
              borderTop: "1px solid #eaecf0",
              color: "#667085",
              fontSize: 13,
            }}
          >
            Hozircha filter status va qidiruv orqali ishlaydi. Keyingi
            bosqichda ustoz, loyiha va prioritet bo‘yicha filterlarni qo‘shamiz.
          </div>
        )}
      </div>

      {/* TABLE */}
      <div
        style={{
          background: "#fff",
          border: "1px solid #eaecf0",
          borderRadius: 16,
          overflow: "hidden",
          boxShadow: "0 1px 3px rgba(16,24,40,.05)",
        }}
      >
        {loading ? (
          <div
            style={{
              minHeight: 300,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#667085",
              fontSize: 14,
            }}
          >
            Yig‘ish navbati yuklanmoqda...
          </div>
        ) : filteredJobs.length === 0 ? (
          <div
            style={{
              minHeight: 300,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              padding: 30,
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: 58,
                height: 58,
                borderRadius: 18,
                background: "#f2f4f7",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 28,
                marginBottom: 14,
              }}
            >
              🔧
            </div>

            <div
              style={{
                fontSize: 16,
                fontWeight: 800,
                marginBottom: 5,
              }}
            >
              {jobs.length === 0
                ? "Yig‘ish navbatida topshiriq yo‘q"
                : "Qidiruv bo‘yicha topshiriq topilmadi"}
            </div>

            <div
              style={{
                color: "#667085",
                fontSize: 13,
                maxWidth: 480,
              }}
            >
              {jobs.length === 0
                ? "Yig‘ish bosqichiga kelgan ishlab chiqarish topshiriqlari shu yerda ko‘rinadi."
                : "Qidiruv yoki status filtrini o‘zgartirib ko‘ring."}
            </div>
          </div>
        ) : (
          <>
            <div style={{ overflowX: "auto" }}>
              <table
                style={{
                  width: "100%",
                  minWidth: 1050,
                  borderCollapse: "collapse",
                  fontSize: 13,
                }}
              >
                <thead>
                  <tr
                    style={{
                      background: "#f9fafb",
                      borderBottom: "1px solid #eaecf0",
                    }}
                  >
                    {[
                      "#",
                      "Ish raqami",
                      "Mahsulot",
                      "Loyiha / Buyurtma",
                      "Reja miqdor",
                      "Yig‘ilgan",
                      "Qolgan",
                      "Holat",
                      "Jarayon",
                      "Amallar",
                    ].map((head) => (
                      <th
                        key={head}
                        style={{
                          textAlign: "left",
                          padding: "13px 14px",
                          color: "#667085",
                          fontWeight: 700,
                          fontSize: 12,
                          whiteSpace: "nowrap",
                        }}
                      >
                        {head}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {filteredJobs.map((job, index) => {
                    const state = getStepState(job);
                    const progress = getProgress(job);
                    const planned = getPlannedQty(job);
                    const completed = getCompletedQty(job);
                    const remaining = getRemainingQty(job);
                    const parts = getPartsCount(job);
                    const badge = stateStyle(state);

                    return (
                      <tr
                        key={job.id}
                        onDoubleClick={() => openJob(job)}
                        style={{
                          borderBottom: "1px solid #f0f2f5",
                          cursor: "pointer",
                        }}
                      >
                        <td
                          style={{
                            padding: "15px 14px",
                            color: "#98a2b3",
                            width: 45,
                          }}
                        >
                          {index + 1}
                        </td>

                        <td style={{ padding: "15px 14px" }}>
                          <div
                            style={{
                              fontWeight: 800,
                              color: "#344054",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {job.job_number || `JOB-${job.id}`}
                          </div>

                          <div
                            style={{
                              color: "#98a2b3",
                              fontSize: 11,
                              marginTop: 3,
                            }}
                          >
                            {formatDate(job.created_at)}
                          </div>
                        </td>

                        <td style={{ padding: "15px 14px" }}>
                          <div
                            style={{
                              fontWeight: 700,
                              color: "#101828",
                              maxWidth: 190,
                            }}
                          >
                            {getProduct(job)}
                          </div>

                          <div
                            style={{
                              color: "#667085",
                              fontSize: 11,
                              marginTop: 3,
                            }}
                          >
                            {parts > 0
                              ? `${parts} ta detal`
                              : getCustomer(job)}
                          </div>
                        </td>

                        <td style={{ padding: "15px 14px" }}>
                          <div
                            style={{
                              fontWeight: 600,
                              color: "#344054",
                            }}
                          >
                            {getProject(job)}
                          </div>

                          <div
                            style={{
                              color: "#98a2b3",
                              fontSize: 11,
                              marginTop: 3,
                            }}
                          >
                            {getCustomer(job)}
                          </div>
                        </td>

                        <td
                          style={{
                            padding: "15px 14px",
                            whiteSpace: "nowrap",
                            fontWeight: 700,
                          }}
                        >
                          {planned > 0 ? `${planned} dona` : "—"}
                        </td>

                        <td
                          style={{
                            padding: "15px 14px",
                            whiteSpace: "nowrap",
                            fontWeight: 700,
                            color: completed > 0 ? "#087443" : "#98a2b3",
                          }}
                        >
                          {completed > 0 ? completed : "0"}
                        </td>

                        <td
                          style={{
                            padding: "15px 14px",
                            whiteSpace: "nowrap",
                            fontWeight: 700,
                            color: remaining > 0 ? "#b54708" : "#087443",
                          }}
                        >
                          {planned > 0 || remaining > 0 ? remaining : "—"}
                        </td>

                        <td style={{ padding: "15px 14px" }}>
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 6,
                              padding: "6px 9px",
                              borderRadius: 999,
                              border: `1px solid ${badge.border}`,
                              background: badge.background,
                              color: badge.color,
                              fontWeight: 700,
                              fontSize: 11,
                              whiteSpace: "nowrap",
                            }}
                          >
                            <span
                              style={{
                                width: 6,
                                height: 6,
                                borderRadius: "50%",
                                background: badge.dot,
                              }}
                            />
                            {STEP_LABELS[state] || state}
                          </span>
                        </td>

                        <td style={{ padding: "15px 14px", minWidth: 140 }}>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                            }}
                          >
                            <div
                              style={{
                                width: 90,
                                height: 7,
                                borderRadius: 99,
                                background: "#eaecf0",
                                overflow: "hidden",
                              }}
                            >
                              <div
                                style={{
                                  width: `${progress}%`,
                                  height: "100%",
                                  borderRadius: 99,
                                  background:
                                    state === "completed"
                                      ? "#12b76a"
                                      : "#2e90fa",
                                  transition: "width .25s ease",
                                }}
                              />
                            </div>

                            <span
                              style={{
                                fontWeight: 700,
                                fontSize: 11,
                                color: "#475467",
                              }}
                            >
                              {progress}%
                            </span>
                          </div>
                        </td>

                        <td style={{ padding: "15px 14px" }}>
                          <button
                            type="button"
                            onClick={() => openJob(job)}
                            style={{
                              height: 34,
                              padding: "0 12px",
                              borderRadius: 8,
                              border: "1px solid",
                              borderColor:
                                state === "pending"
                                  ? "#1570ef"
                                  : "#d0d5dd",
                              background:
                                state === "pending" ? "#1570ef" : "#fff",
                              color:
                                state === "pending" ? "#fff" : "#344054",
                              fontWeight: 700,
                              fontSize: 12,
                              cursor: "pointer",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {state === "pending"
                              ? "▶ Qabul qilish"
                              : state === "in_progress"
                                ? "▶ Davom ettirish"
                                : state === "completed"
                                  ? "◉ Ko‘rish"
                                  : "▶ Ochish"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* FOOTER */}
            <div
              style={{
                minHeight: 58,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                padding: "0 16px",
                borderTop: "1px solid #eaecf0",
                color: "#667085",
                fontSize: 12,
              }}
            >
              <span>
                Jami <strong style={{ color: "#344054" }}>
                  {filteredJobs.length}
                </strong>{" "}
                ta ish
              </span>

              <span>
                {refreshing ? "Avtomatik yangilanmoqda..." : "Avto yangilash: 15 sek."}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
