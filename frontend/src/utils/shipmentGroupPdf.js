import { jsPDF } from "jspdf";
import QRCode from "qrcode";

export async function generateShipmentGroupPdf(shipment) {
  const doc = new jsPDF();
  const qrData = JSON.stringify({
    shipment_id: shipment.id,
    destination: shipment.destination,
    shipped_at: shipment.shipped_at,
    total: shipment.total_products_count,
  });

  const qrUrl = await QRCode.toDataURL(qrData, { width: 100, margin: 1 });
  const barcode = `AZMUS-SHP-${String(shipment.id).padStart(6, "0")}`;

  doc.setFontSize(20);
  doc.text("AZMUS FURNITURE", 20, 22);
  doc.setFontSize(11);
  doc.text("Yuk jo'natish hujjati / Shipment manifest", 20, 30);
  doc.setFontSize(9);
  doc.text("Manzil: Toshkent | Tel: +998 90 000 00 00", 20, 37);

  doc.setFontSize(12);
  doc.text(`Yuk №: ${shipment.id}`, 20, 50);
  doc.text(
    `Sana: ${
      shipment.shipped_at
        ? new Date(shipment.shipped_at).toLocaleString()
        : new Date().toLocaleString()
    }`,
    20,
    58
  );
  doc.text(`Manzil: ${shipment.destination || "-"}`, 20, 66);
  doc.text(`Izoh: ${shipment.comment || "-"}`, 20, 74);
  doc.text(`Ombor operatori: ${shipment.warehouse_operator || "-"}`, 20, 82);
  doc.text(`Mas'ul: ${shipment.responsible_operator || "-"}`, 20, 90);
  doc.text(`Jami mahsulot: ${shipment.total_products_count || 0}`, 20, 98);

  doc.addImage(qrUrl, "PNG", 155, 42, 38, 38);
  doc.setFontSize(8);
  doc.text(barcode, 150, 84);

  doc.setFontSize(10);
  doc.text("|||||||||||||||||||||||||||", 20, 108);
  doc.text(`Barcode: ${barcode}`, 20, 115);

  let y = 125;
  doc.setFontSize(11);
  doc.text("Mahsulotlar:", 20, y);
  y += 8;

  doc.setFontSize(9);
  doc.text("#", 20, y);
  doc.text("Mijoz", 30, y);
  doc.text("Summa", 100, y);
  doc.text("Soni", 140, y);
  doc.text("Manzil", 160, y);
  y += 6;

  const items = shipment.items || [];
  items.forEach((item, idx) => {
    if (y > 270) {
      doc.addPage();
      y = 20;
    }
    doc.text(String(idx + 1), 20, y);
    doc.text(String(item.client || "").slice(0, 28), 30, y);
    doc.text(String(Number(item.amount || 0).toLocaleString()), 100, y);
    doc.text(String(item.quantity || 1), 140, y);
    doc.text(String(item.product_destination || "").slice(0, 25), 160, y);
    y += 6;
  });

  y += 10;
  if (y > 250) {
    doc.addPage();
    y = 20;
  }
  doc.setFontSize(10);
  doc.text("Imzolar:", 20, y);
  y += 12;
  doc.text("Ombor: _________________________", 20, y);
  y += 10;
  doc.text("Haydovchi: ______________________", 20, y);
  y += 10;
  doc.text("Qabul qiluvchi: __________________", 20, y);

  return doc;
}

export async function downloadShipmentPdf(shipment) {
  const doc = await generateShipmentGroupPdf(shipment);
  doc.save(`shipment-${shipment.id}.pdf`);
}

export async function printShipmentPdf(shipment) {
  const doc = await generateShipmentGroupPdf(shipment);
  const url = doc.output("bloburl");
  const win = window.open(url, "_blank");
  if (win) win.focus();
}
