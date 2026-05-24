const API_BASE =
  import.meta.env.VITE_API_URL || "https://azmus-crm.onrender.com";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      data?.error ||
      data?.detail ||
      (Array.isArray(data?.detail) ? data.detail[0]?.msg : null) ||
      response.statusText;
    throw new Error(message || "Request failed");
  }

  if (data?.error) {
    throw new Error(data.error);
  }

  return data;
}

export const api = {
  getOrders: () => request("/orders"),
  createOrder: (body) =>
    request("/orders", { method: "POST", body: JSON.stringify(body) }),
  updateOrderStatus: (id, status) =>
    request(`/orders/${id}?status=${encodeURIComponent(status)}`, {
      method: "PUT",
    }),
  deleteOrder: (id) => request(`/orders/${id}`, { method: "DELETE" }),
  login: (body) =>
    request("/login", { method: "POST", body: JSON.stringify(body) }),
  getUsers: () => request("/users"),
  createUser: (body) =>
    request("/create-user", { method: "POST", body: JSON.stringify(body) }),
};

export { API_BASE };
