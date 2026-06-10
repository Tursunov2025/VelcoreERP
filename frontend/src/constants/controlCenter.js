import { NAV_ITEMS } from "./workflow";

/** All menu keys Super Admin can show/hide (matches backend DEFAULT_NAV_VISIBILITY). */
export const MENU_NAV_KEYS = [
  ...NAV_ITEMS.map((item) => ({
    iconKey: item.iconKey,
    path: item.path,
    labelKey: `nav.${item.iconKey}`,
  })),
  { iconKey: "controlCenter", path: "/control-center", labelKey: "nav.controlCenter" },
  { iconKey: "invoices", path: "/invoices", labelKey: "nav.invoices" },
  { iconKey: "settings", path: "/settings", labelKey: "nav.settings" },
];

export const DASHBOARD_WIDGET_DEFS = [
  { id: "order_stats", labelKey: "controlCenter.widgetOrderStats" },
  { id: "clock", labelKey: "controlCenter.widgetClock" },
  { id: "online_operators", labelKey: "controlCenter.widgetOperators" },
  { id: "production_chart", labelKey: "controlCenter.widgetProductionChart" },
  { id: "delayed_summary", labelKey: "controlCenter.widgetDelayed" },
  { id: "export_shipments", labelKey: "controlCenter.widgetExportShipments" },
  { id: "currency_rates", labelKey: "controlCenter.widgetCurrencyRates" },
  { id: "top_debtors", labelKey: "controlCenter.widgetTopDebtors" },
  { id: "warehouse_forecast", labelKey: "controlCenter.widgetWarehouseForecast" },
];

export const DEFAULT_DASHBOARD_WIDGETS = DASHBOARD_WIDGET_DEFS.map((w, i) => ({
  id: w.id,
  enabled: true,
  order: i + 1,
}));

export const CONTROL_CENTER_NAV_ITEM = {
  path: "/control-center",
  label: "Control Center",
  iconKey: "controlCenter",
  adminOnly: true,
  permission: null,
};

export function applyNavVisibility(items, navVisibility, isAdmin) {
  if (!navVisibility || isAdmin) {
    if (isAdmin) return items;
  }
  return items.filter((item) => {
    if (item.adminOnly && !isAdmin) return false;
    const key = item.iconKey;
    if (!key) return true;
    return navVisibility[key] !== false;
  });
}

export function isWidgetEnabled(widgets, widgetId) {
  if (!widgets?.length) return true;
  const row = widgets.find((w) => w.id === widgetId);
  return row ? row.enabled !== false : true;
}
