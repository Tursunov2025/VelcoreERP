/** Extract PKG label code from QR text or tracking URL. */
export function parseLabelCode(raw) {
  const text = (raw || "").trim();
  if (!text) return "";
  const urlMatch = text.match(/\/track\/package\/([^/?#]+)/i);
  if (urlMatch) return decodeURIComponent(urlMatch[1]);
  const pkgMatch = text.match(/PKG-\d{8}-\d{5}/i);
  if (pkgMatch) return pkgMatch[0].toUpperCase();
  return text;
}
