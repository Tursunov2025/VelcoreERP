export function normalizeApiErrorPayload(data, fallback = "Request failed") {
  const detail = data?.detail ?? data?.error ?? data;
  const fieldErrors = {};
  let code = typeof data?.code === "string" ? data.code : undefined;
  let message = "";

  const consume = (item) => {
    if (typeof item === "string") {
      if (!message) message = item;
      return;
    }
    if (!item || typeof item !== "object") return;
    if (!code && typeof item.code === "string") code = item.code;
    if (!message && typeof item.message === "string") message = item.message;
    if (!message && typeof item.msg === "string") message = item.msg;
    if (Array.isArray(item.loc) && typeof item.msg === "string") {
      const field = [...item.loc].reverse().find(
        (part) => typeof part === "string" && !["body", "query", "path"].includes(part),
      );
      if (field) fieldErrors[field] = item.msg;
    }
    if (Array.isArray(item.detail)) item.detail.forEach(consume);
    else if (item.detail && typeof item.detail === "object") consume(item.detail);
    if (Array.isArray(item.errors)) item.errors.forEach(consume);
  };

  if (Array.isArray(detail)) detail.forEach(consume);
  else consume(detail);
  return { code, message: message || fallback, fieldErrors };
}
