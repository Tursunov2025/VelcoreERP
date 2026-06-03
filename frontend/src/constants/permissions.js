export const PERMISSION_MODULES = [
  { id: "orders", label: "Zakazlar" },
  { id: "production", label: "Ishlab chiqarish" },
  { id: "warehouse", label: "Ombor" },
  { id: "tasks", label: "Vazifalar" },
  { id: "finance", label: "Moliya" },
  { id: "chat", label: "Chat" },
  { id: "settings", label: "Sozlamalar" },
];

export const MATERIALS_PERMISSIONS = [
  { id: "materials_view", label: "Xom ashyo — Ko'rish" },
  { id: "materials_edit", label: "Xom ashyo — Tahrirlash" },
];

export const MES_PERMISSIONS = [
  { id: "mes_view", label: "MES — Ko'rish" },
  { id: "mes_edit", label: "MES — Tahrirlash" },
  { id: "mes_delete", label: "MES — O'chirish" },
  { id: "mes_routes_design", label: "MES — Marshrut dizayner" },
  { id: "mes_drawings_upload", label: "MES — Chizma yuklash" },
  { id: "mes_jobs_view", label: "MES — Ishlar ko'rish" },
  { id: "mes_jobs_manage", label: "MES — Ishlar boshqaruv" },
  { id: "mes_terminal_lazer", label: "MES — Lazer terminal" },
  { id: "mes_terminal_svarshik", label: "MES — Svarshik terminal" },
  { id: "mes_terminal_kraska", label: "MES — Kraska terminal" },
  { id: "mes_terminal_qc", label: "MES — Nazorat (QC) terminal" },
  { id: "mes_terminal_packaging", label: "MES — Upakovka terminal" },
  { id: "mes_terminal_warehouse", label: "MES — Tayyor mahsulot ombori" },
  { id: "mes_terminal_dispatch", label: "MES — Yuklash terminal" },
];

export const LLP_PERMISSIONS = [
  { id: "llp_view", label: "LLP — Ko'rish" },
  { id: "llp_download", label: "LLP — Yuklab olish" },
  { id: "llp_upload", label: "LLP — Yuklash" },
  { id: "llp_edit", label: "LLP — Tahrirlash" },
  { id: "llp_delete", label: "LLP — O'chirish" },
  { id: "llp_read_confirm", label: "LLP — O'qildi" },
];

export const NOTIFICATION_EVENTS = [
  { id: "new_order", label: "Yangi zakaz" },
  { id: "order_completed", label: "Zakaz tayyor" },
  { id: "new_task", label: "Yangi vazifa" },
  { id: "task_accepted", label: "Vazifa qabul qilindi" },
  { id: "task_completed", label: "Vazifa bajarildi" },
  { id: "task_overdue", label: "Vazifa muddati o'tgan" },
  { id: "shipment_dispatched", label: "Yuk chiqarildi" },
  { id: "warehouse_events", label: "Ombor hodisalari" },
  { id: "chat_messages", label: "Chat xabarlari" },
  { id: "llp_important", label: "LLP muhim hujjat" },
];

export function isTruthySetting(value) {
  return String(value ?? "true").toLowerCase() in { true: 1, "1": 1, yes: 1 };
}
