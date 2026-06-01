export const PERMISSION_MODULES = [
  { id: "orders", label: "Zakazlar" },
  { id: "production", label: "Ishlab chiqarish" },
  { id: "warehouse", label: "Ombor" },
  { id: "tasks", label: "Vazifalar" },
  { id: "finance", label: "Moliya" },
  { id: "chat", label: "Chat" },
  { id: "settings", label: "Sozlamalar" },
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
