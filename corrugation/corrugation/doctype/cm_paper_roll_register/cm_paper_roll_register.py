# -*- coding: utf-8 -*-
# Copyright (c) 2017, sathishpy@gmail.com and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import nowdate

class CMPaperRollRegister(Document):
	def autoname(self):
		self.name = self.purchase_receipt + "-roll-register"

	def populate_rolls(self):
		if (self.purchase_receipt is None): return
		self.total_weight, self.purchase_weight = 0, self.get_purchase_weight()
		receipt = frappe.get_doc("Purchase Receipt", self.purchase_receipt)

		last_idx = frappe.db.count("CM Paper Roll")
		idx = last_idx + 1
		roll_name = frappe.db.get_value("CM Paper Roll", filters={"number": idx})
		while (roll_name is not None):
			idx = idx + 1
			roll_name = frappe.db.get_value("CM Paper Roll", filters={"number": idx})

		self.supplier = receipt.supplier
		print("Populating {0} Paper items for receipt {1} starting {2} from {3}".format(len(receipt.items), self.purchase_receipt, idx, receipt.supplier))
		self.paper_rolls, self.charges = [], []

		item_rates = self.get_actual_roll_rates()
		for item in receipt.items:
			item_doc = frappe.get_doc("Item", item.item_name)
			if item_doc.item_group != "Paper": continue

			weight = item.qty
			while (weight > 0):
				paper_roll = frappe.new_doc("CM Paper Roll Detail")
				paper_roll.paper = item.item_code
				paper_roll.number = idx
				idx += 1
				if (weight > 500):
					paper_roll.weight = 500
					weight -= 500
				else:
					paper_roll.weight = weight
					weight = 0
				(basic, tax, charge) = item_rates[paper_roll.paper]
				paper_roll.unit_cost = (basic + charge)
				self.append("paper_rolls", paper_roll)
				self.total_weight += paper_roll.weight
				print "Creating Roll {0}-{1}".format(item.item_code, paper_roll.weight)

	def register_rolls(self):
		jentry = None
		if (len(self.charges) > 0):
			jentry = frappe.new_doc("Journal Entry")
			jentry.update({"voucher_type": "Journal Entry", "posting_date": nowdate(), "is_opening": "No", "remark": "Purchase Charges"})
		for item in self.charges:
			jentry.append("accounts", {"account": item.from_account, "credit_in_account_currency": item.amount})
			jentry.append("accounts", {"account": item.to_account, "debit_in_account_currency": item.amount})
		if (jentry is not None):
			jentry.submit()
			self.charge_entry = jentry.name

		item_rates = self.get_actual_roll_rates()

		for roll in self.paper_rolls:
			paper_roll = frappe.new_doc("CM Paper Roll")
			paper_roll.paper = roll.paper
			paper_roll.number = roll.number
			paper_roll.weight = roll.weight
			paper_roll.roll_receipt = self.name
			paper_roll.supplier = self.supplier
			paper_roll.manufacturer = self.manufacturer
			(basic, tax, charge) = item_rates[roll.paper]
			paper_roll.basic_cost = basic
			paper_roll.tax_cost = tax
			paper_roll.misc_cost = charge
			paper_roll.status = "Ready"
			paper_roll.save()

	def get_actual_roll_rates(self):
		bill_doc = frappe.get_doc("Purchase Receipt", self.purchase_receipt)
		if (self.purchase_invoice):
			bill_doc = frappe.get_doc("Purchase Invoice", self.purchase_invoice)
		item_rates = {}
		std_cost = taxes = charges = 0

		std_cost = (bill_doc.total - bill_doc.discount_amount)
		if (self.purchase_invoice):
			 std_cost = std_cost - bill_doc.write_off_amount
		for item in bill_doc.taxes:
			account_type = frappe.db.get_value("Account", item.account_head, "account_type")
			if (account_type == "Tax"):
				taxes += item.tax_amount
			else:
				charges += item.tax_amount

		for item in self.charges:
			charges += item.amount

		print("Rate for {0}: Basic={1} Tax={2} Charges={3}".format(bill_doc.name, std_cost, taxes, charges))
		for item in bill_doc.items:
			unit_share = float(item.amount/bill_doc.total)/item.qty
			item_rates[item.item_name] = (std_cost * unit_share, taxes * unit_share, charges * unit_share)
			print ("Item {0}:{1}".format(item.item_name, item_rates[item.item_name]))
		return item_rates

	def update_roll_cost(self):
		item_rates = self.get_actual_roll_rates()

		for roll in self.paper_rolls:
			roll_name = "{0}-RL-{1}".format(roll.paper, roll.number)
			(basic, tax, charge) = item_rates[roll.paper]
			print("New Rates-{0}: Basic={1} Tax={2} Charge={3}".format(roll_name, basic, tax, charge))
			roll.unit_cost = (basic + charge)
			roll.save()
			if (frappe.db.get_value("CM Paper Roll", roll_name) == None): continue
			paper_roll = frappe.get_doc("CM Paper Roll", roll_name)
			print("Old Rates-{0}: Basic={1} Tax={2} Charge={3}".format(paper_roll.name, paper_roll.basic_cost, paper_roll.tax_cost, paper_roll.misc_cost))
			paper_roll.basic_cost = basic
			paper_roll.tax_cost = tax
			paper_roll.misc_cost = charge
			paper_roll.save()

	def get_purchase_weight(self):
		receipt = frappe.get_doc("Purchase Receipt", self.purchase_receipt)
		weight = 0
		for item in receipt.items:
			weight += item.qty
		return weight

	def get_roll_weight(self):
		weight = 0
		for roll in self.paper_rolls:
			weight += roll.weight
		return weight

	def on_submit(self):
		roll_weight = self.get_roll_weight()
		purchase_weight = self.get_purchase_weight()
		if (roll_weight != purchase_weight):
			frappe.throw(_("Paper roll weight doesn't match the purchase weight"))
		self.register_rolls()

	def on_trash(self):
		for roll in self.paper_rolls:
			roll_name = "{0}-RL-{1}".format(roll.paper, roll.number)
			if (frappe.db.get_value("CM Paper Roll", roll_name) == None): break
			paper_roll = frappe.get_doc("CM Paper Roll", roll_name)
			print ("Deleting roll {0}".format(paper_roll.name))
			paper_roll.delete()
		docs = frappe.get_doc("Purchase Invoice", self.purchase_invoice)
		docs += frappe.get_doc("Purchase Receipt", self.purchase_receipt)
		docs += frappe.get_doc("Journal Entry", self.charge_entry)
		for doc in docs:
			print ("Deleting entry {0}".format(doc.name))
			doc.cancel()
			doc.delete()

@frappe.whitelist()
def create_new_rolls(doc, method):
	print("Creating new roll register for doc {0}".format(doc.name))
	new_register = frappe.new_doc("CM Paper Roll Register")
	new_register.purchase_receipt = doc.name
	new_register.populate_rolls()
	new_register.save(ignore_permissions=True)

def find_roll_receipt_matching_invoice(pi):
	open_roll_receipts = frappe.get_all("CM Paper Roll Register", filters={"purchase_invoice": None})
	for receipt in open_roll_receipts:
		print("Checking receipt {0}".format(receipt))
		roll_reg = frappe.get_doc("CM Paper Roll Register", receipt)
		pr = frappe.get_doc("Purchase Receipt", roll_reg.purchase_receipt)
		if (pi.supplier != pr.supplier): continue
		if (len(pr.items) != len(pi.items)): continue
		match = True
		for idx in range(0, len(pi.items)):
			if (pi.items[idx].item_code != pr.items[idx].item_code or pi.items[idx].qty != pr.items[idx].qty):
				match = False
				break
		if (match): return roll_reg

@frappe.whitelist()
def update_invoice(pi, method):
	print("Updating roll register for doc {0}".format(pi.name))
	roll_receipt = find_roll_receipt_matching_invoice(pi)
	if (roll_receipt == None):
		print("Failed to find the roll receipt for invoice {0}".format(pi.name))
		return

	roll_receipt.purchase_invoice = pi.name
	roll_receipt.save()

	roll_receipt.update_roll_cost()
