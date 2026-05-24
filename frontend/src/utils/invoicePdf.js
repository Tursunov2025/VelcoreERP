import { jsPDF } from "jspdf";
import QRCode from "qrcode";

export async function generateInvoicePdf(order) {
  const doc = new jsPDF();
  const qrData = JSON.stringify({
    id: order.id,
    client: order.client,
    amount: order.amount,
    status: order.status,
  });

  const qrUrl = await QRCode.toDataURL(qrData, { width: 120, margin: 1 });

  doc.setFontSize(22);
  doc.text("AZMUS FURNITURE", 20, 25);
  doc.setFontSize(12);
  doc.text("Invoys / Invoice", 20, 35);

  doc.setFontSize(11);
  doc.text(`Zakaz #: ${order.id}`, 20, 50);
  doc.text(`Mijoz: ${order.client}`, 20, 58);
  doc.text(`Telefon: ${order.phone || "-"}`, 20, 66);
  doc.text(`Holat: ${order.status}`, 20, 74);
  doc.text(`Sana: ${new Date().toLocaleDateString()}`, 20, 82);

  doc.setFontSize(16);
  doc.text(`Summa: ${Number(order.amount).toLocaleString()} so'm`, 20, 98);

  doc.addImage(qrUrl, "PNG", 150, 45, 40, 40);
  doc.setFontSize(8);
  doc.text(`INV-${order.id}`, 150, 90);

  doc.setFontSize(10);
  doc.text("|||||||||||||||||||||||||||", 20, 115);
  doc.text(`Barcode: AZMUS-${String(order.id).padStart(6, "0")}`, 20, 122);

  doc.setFontSize(9);
  doc.text("Rahmat! Azmus CRM ERP", 20, 140);

  return doc;
}

export async function downloadInvoice(order) {
  const doc = await generateInvoicePdf(order);
  doc.save(`invoice-${order.id}.pdf`);
}

export async function printInvoice(order) {
  const doc = await generateInvoicePdf(order);
  const url = doc.output("bloburl");
  const win = window.open(url, "_blank");
  if (win) win.focus();
}
