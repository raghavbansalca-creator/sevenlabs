frappe.ui.form.on("Work Order", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("Send via WhatsApp"),
				function () {
					let phone = "919997155444";

					let msg = `*Work Order: ${frm.doc.name}*\n`;
					msg += `Status: ${frm.doc.status}\n`;
					msg += `Item: ${frm.doc.item_name || frm.doc.production_item}\n`;
					msg += `Qty: ${frm.doc.qty}\n`;

					if (frm.doc.planned_start_date) {
						msg += `Planned Start: ${frm.doc.planned_start_date.split(" ")[0]}\n`;
					}
					if (frm.doc.expected_delivery_date) {
						msg += `Expected Delivery: ${frm.doc.expected_delivery_date.split(" ")[0]}\n`;
					}
					if (frm.doc.company) {
						msg += `Company: ${frm.doc.company}\n`;
					}

					// Add required items
					if (frm.doc.required_items && frm.doc.required_items.length) {
						msg += `\n*Required Items:*\n`;
						frm.doc.required_items.forEach(function (row) {
							msg += `- ${row.item_name}: ${row.required_qty} ${row.uom || ""}\n`;
						});
					}

					let url =
						"https://wa.me/" +
						phone +
						"?text=" +
						encodeURIComponent(msg);
					window.open(url, "_blank");
				},
				__("WhatsApp")
			);
		}
	},
});
