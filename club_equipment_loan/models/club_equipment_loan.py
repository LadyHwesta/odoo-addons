# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_ACTIVE_STATES = ("reserved", "out")


class ClubEquipmentLoan(models.Model):
    _name = "club.equipment.loan"
    _description = "Club Equipment Loan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "checkout_date desc, id desc"

    name = fields.Char(
        string="Reference", default="/", copy=False, readonly=True, index=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Equipment", required=True,
        domain="[('is_loanable', '=', True)]", tracking=True)
    borrower_id = fields.Many2one(
        "res.partner", string="Borrower", required=True, tracking=True,
        index=True)
    user_id = fields.Many2one(
        "res.users", string="Loan Officer", tracking=True,
        default=lambda self: self.env.user)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company)

    checkout_date = fields.Date(
        string="Checked Out", default=fields.Date.context_today, tracking=True)
    due_date = fields.Date(string="Due Back", required=True, tracking=True)
    return_date = fields.Date(string="Returned", readonly=True, tracking=True)

    state = fields.Selection(
        selection=[
            ("reserved", "Reserved"),
            ("out", "On Loan"),
            ("returned", "Returned"),
            ("cancelled", "Cancelled"),
        ],
        default="reserved", required=True, tracking=True)
    is_overdue = fields.Boolean(
        compute="_compute_is_overdue", store=True,
        help="On loan and past its due date.")
    overdue_notified = fields.Boolean(
        default=False, copy=False, readonly=True,
        help="The overdue sweep has already emailed the borrower about this "
             "loan; stops it nagging on every run.")

    borrower_accepted = fields.Boolean(
        string="Borrower Accepted Terms",
        help="The borrower has agreed to the loan agreement. Required before "
             "the item can be checked out.")
    condition_out = fields.Text(string="Condition Out")
    condition_in = fields.Text(string="Condition In")
    notes = fields.Text()

    _check_due_after_checkout = models.Constraint(
        "CHECK (due_date >= checkout_date)",
        "The due date can't be before the checkout date.",
    )

    # ------------------------------------------------------------------
    @api.model
    def _default_loan_days(self):
        param = self.env["ir.config_parameter"].sudo().get_param(
            "club_equipment_loan.default_days", "14")
        try:
            return max(int(param), 1)
        except (TypeError, ValueError):
            return 14

    @api.onchange("checkout_date")
    def _onchange_checkout_date_due(self):
        if self.checkout_date and not self.due_date:
            self.due_date = self.checkout_date + timedelta(days=self._default_loan_days())

    @api.depends("state", "due_date")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for loan in self:
            loan.is_overdue = bool(
                loan.state == "out" and loan.due_date and loan.due_date < today)

    @api.constrains("equipment_id", "state")
    def _check_single_active_loan(self):
        for loan in self.filtered(lambda loan_: loan_.state in _ACTIVE_STATES):
            clash = self.search_count([
                ("id", "!=", loan.id),
                ("equipment_id", "=", loan.equipment_id.id),
                ("state", "in", _ACTIVE_STATES),
            ])
            if clash:
                raise ValidationError(_(
                    "%(equipment)s is already out on another loan.",
                    equipment=loan.equipment_id.display_name))

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "club.equipment.loan") or "/"
            if not vals.get("due_date"):
                base = fields.Date.to_date(vals.get("checkout_date")) \
                    or fields.Date.context_today(self)
                vals["due_date"] = base + timedelta(days=self._default_loan_days())
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_check_out(self):
        for loan in self:
            if loan.state != "reserved":
                raise UserError(_("Only a reserved loan can be checked out."))
            if not loan.borrower_accepted:
                raise UserError(_(
                    "%(borrower)s needs to accept the loan agreement first.",
                    borrower=loan.borrower_id.name))
            loan.write({
                "state": "out",
                "checkout_date": loan.checkout_date or fields.Date.context_today(loan),
            })
            loan.message_post(body=_("Checked out to %s.", loan.borrower_id.name))
            template = self.env.ref(
                "club_equipment_loan.mail_template_loan_checkout",
                raise_if_not_found=False)
            if template:
                template.send_mail(loan.id, force_send=False)
        return True

    def action_check_in(self):
        for loan in self:
            if loan.state != "out":
                raise UserError(_("Only a loan that's out can be returned."))
            loan.write({
                "state": "returned",
                "return_date": fields.Date.context_today(loan),
                "overdue_notified": False,
            })
            loan.message_post(body=_("Returned by %s.", loan.borrower_id.name))
        return True

    def action_cancel(self):
        self.filtered(lambda loan_: loan_.state in _ACTIVE_STATES).write(
            {"state": "cancelled"})
        return True

    def action_reset_to_reserved(self):
        self.filtered(lambda loan_: loan_.state == "cancelled").write(
            {"state": "reserved", "overdue_notified": False})
        return True

    # ------------------------------------------------------------------
    # Overdue sweep
    # ------------------------------------------------------------------
    @api.model
    def _cron_flag_overdue(self):
        today = fields.Date.context_today(self)
        # `is_overdue` is a live computed field - it flips on its own the day
        # a loan passes its due date. `overdue_notified` is the separate
        # bookkeeping flag that keeps this sweep from nagging every run.
        newly_overdue = self.search([
            ("state", "=", "out"),
            ("overdue_notified", "=", False),
            ("due_date", "<", today),
        ])
        if not newly_overdue:
            return
        newly_overdue.write({"overdue_notified": True})
        template = self.env.ref(
            "club_equipment_loan.mail_template_loan_overdue",
            raise_if_not_found=False)
        for loan in newly_overdue:
            if template:
                template.send_mail(loan.id, force_send=False)
            if loan.user_id:
                loan.activity_schedule(
                    "mail.mail_activity_data_todo",
                    date_deadline=today,
                    user_id=loan.user_id.id,
                    summary=_("Overdue loan: %s", loan.name),
                    note=_(
                        "%(equipment)s is overdue - lent to %(borrower)s, was "
                        "due %(date)s.",
                        equipment=loan.equipment_id.display_name,
                        borrower=loan.borrower_id.name,
                        date=loan.due_date),
                )
