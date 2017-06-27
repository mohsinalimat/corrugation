// Copyright (c) 2017, sathishpy@gmail.com and contributors
// For license information, please see license.txt

frappe.ui.form.on('CM Production Order', {
	setup: function(frm) {
		frm.get_field('paper_rolls').grid.editable_fields = [
			  {fieldname: 'rm_type', columns: 1},
				{fieldname: 'paper_roll', columns: 4},
				{fieldname: 'start_weight', columns: 2},
				{fieldname: 'est_final_weight', columns: 1},
				{fieldname: 'final_weight', columns: 2}
			];
		frm.fields_dict['sales_order'].get_query = function(doc, dt, dn) {
			return {
				filters:[
					['Sales Order', 'status', '=', 'To Deliver and Bill']
				]
			}
		}
		frm.add_fetch("CM Paper Roll", "weight", "start_weight");
	},
	onload: function(frm) {
		frm.events.set_default_warehouse(frm);
	},
	refresh: function(frm) {
		if (frm.doc.__islocal) return;
		frm.add_custom_button(__('Make'),
	  	function() {
				frm.events.make_pe(frm)
			});
	},
	set_default_warehouse: function(frm) {
		if (!(frm.doc.source_warehouse || frm.doc.target_warehouse)) {
			frappe.call({
				method: "erpnext.manufacturing.doctype.production_order.production_order.get_default_warehouse",

				callback: function(r) {
					if(!r.exe) {
						frm.set_value("source_warehouse", r.message.wip_warehouse);
						frm.set_value("target_warehouse", r.message.fg_warehouse)
					}
				}
			});
		}
	},

	setup_company_filter: function(frm) {
		var company_filter = function(doc) {
			return {
				filters: {
					'company': frm.doc.company,
					'is_group': 0
				}
			}
		}

		frm.fields_dict.source_warehouse.get_query = company_filter;
		frm.fields_dict.target_warehouse.get_query = company_filter;
	},
	sales_order: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: "get_all_order_items",
			callback: function(r) {
				if(!r.exe) {
					if (r.message.length == 1) {
						frm.set_value("box", r.message[0].item_code)
						frm.set_value("planned_qty", r.message[0].qty)
					} else {
						frm.set_value("box", r.message) //XXX
					}
					refresh_field("box")
					refresh_field("planned_qty")
					frm.events.box(frm)
				}
			}
		});
	},
	box: function(frm) {
		frm.set_query("box_desc", function(doc) {
			if (doc.box) {
				return {
					filters:[
						['CM Box Description', 'item', '=', doc.box]
					]
				}
			} else msgprint(__("Please select the Item first"));
		});
	},
	box_desc: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: "populate_box_rolls",
			callback: function(r) {
				if(!r.exe) {
					refresh_field("paper_rolls");
					refresh_field("bom")
				}
			}
		});
	},
	make_pe: function(frm) {
		frappe.model.open_mapped_doc({
			method: "corrugation.corrugation.doctype.cm_production_order.cm_production_order.make_new_stock_entry",
			frm: frm
		})
	}
});
frappe.ui.form.on("CM Production Roll Detail", "paper_roll", function(frm, cdt, cdn) {
	frappe.call({
		doc: frm.doc,
		method: "update_box_roll_qty",
		callback: function(r) {
			if(!r.exe) {
				refresh_field("paper_rolls");
			}
		}
	});
});