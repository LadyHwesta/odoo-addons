# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

_ACTIVE_STATES = ("reserved", "out")


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    is_loanable = fields.Boolean(
        string="Loanable",
        help="Add this item to the club's loaner pool.")
    loan_ids = fields.One2many(
        "club.equipment.loan", "equipment_id", string="Loans")
    loan_count = fields.Integer(compute="_compute_loan_info")
    current_loan_id = fields.Many2one(
        "club.equipment.loan", compute="_compute_loan_info",
        string="Current Loan")
    loan_availability = fields.Selection(
        selection=[
            ("available", "Available"),
            ("reserved", "Reserved"),
            ("on_loan", "On Loan"),
        ],
        compute="_compute_loan_info", store=True, string="Availability")

    @api.depends("loan_ids.state", "is_loanable")
    def _compute_loan_info(self):
        for equipment in self:
            loans = equipment.loan_ids
            equipment.loan_count = len(loans)
            active = loans.filtered(lambda loan_: loan_.state in _ACTIVE_STATES)[:1]
            equipment.current_loan_id = active
            if not equipment.is_loanable:
                equipment.loan_availability = False
            elif not active:
                equipment.loan_availability = "available"
            else:
                equipment.loan_availability = (
                    "on_loan" if active.state == "out" else "reserved")

    def action_view_loans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Loans"),
            "res_model": "club.equipment.loan",
            "view_mode": "list,form",
            "domain": [("equipment_id", "=", self.id)],
            "context": {
                "default_equipment_id": self.id,
                "default_is_loanable": True,
            },
        }
