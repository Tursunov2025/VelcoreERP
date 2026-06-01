export const TASK_STATUSES = [
  "new",
  "accepted",
  "in_progress",
  "completed",
  "cancelled",
];

export const STATUS_LABELS = {
  new: "Yangi",
  accepted: "Qabul qilindi",
  in_progress: "Bajarilmoqda",
  completed: "Bajarildi",
  cancelled: "Bekor qilindi",
};

export const STATUS_BADGE = {
  new: "bg-gray-100 text-gray-700",
  accepted: "bg-blue-100 text-blue-700",
  in_progress: "bg-amber-100 text-amber-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

export const PRIORITIES = ["normal", "important", "urgent"];

export const PRIORITY_LABELS = {
  normal: "Oddiy",
  important: "Muhim",
  urgent: "Shoshilinch",
};

export const PRIORITY_BADGE = {
  normal: "bg-gray-100 text-gray-700",
  important: "bg-orange-100 text-orange-700",
  urgent: "bg-red-100 text-red-700",
};

// Allowed next statuses an operator can pick from the current one.
export const OPERATOR_NEXT = {
  new: ["accepted", "cancelled"],
  accepted: ["in_progress", "cancelled"],
  in_progress: ["completed", "cancelled"],
  completed: [],
  cancelled: ["accepted"],
};
