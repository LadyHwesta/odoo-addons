# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import config

URGENCY = [('low', "When you get a chance"), ('normal', "Today, please"), ('high', "I'm stuck")]

# What the person who reported it may change on their own request.
REQUESTER_FIELDS = {'name', 'description', 'trying_to', 'urgency', 'state'}


def server_setting(key):
    """The server's default from odoo.conf, e.g. support_provider_email."""
    return config.get(f'support_provider_{key}') or ''


def provider_setting(env, key):
    """A provider setting: this database's own (Settings), else the server's
    odoo.conf (`support_provider_email`...), so a hosting provider can set it
    once per server for every database on it."""
    value = env['ir.config_parameter'].sudo().get_param(f'support_request_escalation.{key}')
    return value or server_setting(key)


class SupportRequest(models.Model):
    _name = 'support.request'
    _description = 'Support Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_names_search = ['name', 'reference']

    reference = fields.Char(readonly=True, copy=False, default='/', index=True)
    name = fields.Char(string="What's wrong", required=True, tracking=True)
    description = fields.Text(string="Details", help="What happened, any error message, what you expected.")
    trying_to = fields.Text(string="What were you trying to do?")
    urgency = fields.Selection(URGENCY, default='normal', required=True, tracking=True)
    requester_id = fields.Many2one('res.users', string="Reported by", default=lambda self: self.env.user,
                                   readonly=True, index=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True,
                                 readonly=True)
    coordinator_id = fields.Many2one('res.users', string="Looked at by", readonly=True, tracking=True)
    page_url = fields.Char(string="Page", readonly=True, help="Where they were when they reported it.")
    page_title = fields.Char(string="Screen", readonly=True)
    user_agent = fields.Char(string="Browser", readonly=True)
    state = fields.Selection([
        ('new', "New"),
        ('review', "Being looked at"),
        ('solved', "Solved here"),
        ('escalated', "Sent to support"),
        ('closed', "Closed"),
    ], default='new', required=True, tracking=True, index=True)
    escalated_on = fields.Datetime(readonly=True, copy=False)
    escalated_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    provider_name = fields.Char(compute='_compute_provider', string="Support provider")
    can_escalate = fields.Boolean(compute='_compute_provider')
    is_coordinator = fields.Boolean(compute='_compute_is_coordinator')

    @api.depends_context('uid')
    def _compute_is_coordinator(self):
        coordinator = self.env.user.has_group('support_request_escalation.group_support_coordinator')
        self.is_coordinator = coordinator

    def _compute_provider(self):
        name = provider_setting(self.env, 'name') or _("your Odoo provider")
        has_email = bool(provider_setting(self.env, 'email'))
        for request in self:
            request.provider_name = name
            request.can_escalate = has_email and request.state in ('new', 'review', 'solved')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', '/') == '/':
                vals['reference'] = self.env['ir.sequence'].sudo().next_by_code('support.request') or '/'
        requests = super().create(vals_list)
        requests._tell_coordinators()
        return requests

    @api.depends('reference', 'name')
    def _compute_display_name(self):
        for request in self:
            request.display_name = f"{request.reference} {request.name}" if request.reference not in (False, '/') \
                else request.name

    def write(self, vals):
        if not self.env.su and not self.env.user.has_group(
                'support_request_escalation.group_support_coordinator'):
            if set(vals) - REQUESTER_FIELDS - {'message_follower_ids', 'activity_ids'}:
                raise AccessError(_("Only a support coordinator can change that."))
            if 'state' in vals and vals['state'] != 'closed':
                raise AccessError(_("Only a support coordinator can move a request along."))
            if any(r.requester_id != self.env.user for r in self) and set(vals) & REQUESTER_FIELDS:
                raise AccessError(_("You can only change requests you reported."))
        return super().write(vals)

    # ---- who hears about it ----

    def _coordinators(self):
        group = self.env.ref('support_request_escalation.group_support_coordinator')
        users = group.sudo().all_user_ids.filtered(lambda u: u.active and not u.share)
        return users.filtered(lambda u: self.company_id in u.company_ids)

    def _tell_coordinators(self):
        """Each coordinator gets a to-do (shown on My Day too); taking the
        request clears everyone else's."""
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for request in self:
            coordinators = request._coordinators()
            request.message_subscribe(partner_ids=(request.requester_id.partner_id | coordinators.partner_id).ids)
            if not todo:
                continue
            for user in coordinators - request.requester_id:
                request.sudo().activity_schedule(
                    activity_type_id=todo.id, user_id=user.id,
                    summary=_("Support request: %s", request.name),
                    note=escape(request.description or ''))

    def _check_coordinator(self):
        if not self.env.user.has_group('support_request_escalation.group_support_coordinator'):
            raise AccessError(_("Only a support coordinator can do that."))

    # ---- buttons ----

    def action_take(self):
        self._check_coordinator()
        for request in self:
            request.write({'state': 'review', 'coordinator_id': self.env.uid})
            request.activity_ids.filtered(lambda a: a.user_id != self.env.user).sudo().unlink()

    def action_solved(self):
        self._check_coordinator()
        for request in self:
            request.write({'state': 'solved', 'coordinator_id': request.coordinator_id.id or self.env.uid})
            request.activity_ids.sudo().action_feedback(feedback=_("Solved here"))

    def action_close(self):
        self.write({'state': 'closed'})
        self.activity_ids.sudo().unlink()

    def action_reopen(self):
        self._check_coordinator()
        self.write({'state': 'review'})

    def action_escalate(self):
        self.ensure_one()
        self._check_coordinator()
        if not provider_setting(self.env, 'email'):
            raise UserError(_("Set your provider's support email first: Settings › Support Requests."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'support.request.escalate',
            'view_mode': 'form',
            'target': 'new',
            'name': _("Send to %s", self.provider_name),
            'context': {'default_request_id': self.id},
        }

    # ---- escalation ----

    def _provider_partner(self):
        email = provider_setting(self.env, 'email')
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('email', '=ilike', email)], limit=1)
        if not partner:
            partner = Partner.create({'name': provider_setting(self.env, 'name') or email, 'email': email})
        return partner

    def _escalation_body(self, note):
        """What the provider's support team gets: everything they need to find
        the problem, and which system it came from (data-support-* attributes
        let their helpdesk link the ticket to the right customer)."""
        self.ensure_one()
        base_url = self.get_base_url()
        rows = [
            (_("Request"), self.reference),
            (_("Reported by"), f"{self.requester_id.name} <{self.requester_id.email or ''}>"),
            (_("Escalated by"), f"{self.env.user.name} <{self.env.user.email or ''}>"),
            (_("Company"), self.company_id.name),
            (_("Urgency"), dict(URGENCY).get(self.urgency)),
            (_("Screen"), self.page_title),
            (_("Page"), self.page_url),
            (_("Browser"), self.user_agent),
        ]
        table = Markup('').join(
            Markup('<tr><td style="padding:2px 12px 2px 0;color:#666;">%s</td><td>%s</td></tr>') % (label, value)
            for label, value in rows if value)
        parts = []
        if note:
            parts.append(Markup('<p>%s</p>') % note)
        parts.append(Markup('<p><strong>%s</strong></p>') % self.name)
        if self.description:
            parts.append(Markup('<p style="white-space:pre-wrap;">%s</p>') % self.description)
        if self.trying_to:
            parts.append(Markup('<p><em>%s</em><br/><span style="white-space:pre-wrap;">%s</span></p>') % (
                _("What they were trying to do:"), self.trying_to))
        parts.append(Markup('<table>%s</table>') % table)
        # A fixed, untranslated line the provider's helpdesk can read to link the
        # ticket to the right customer (mail sanitizing drops data-* attributes).
        parts.append(Markup('<p style="color:#666;font-size:12px;">%s</p>') % (
            f"[support-system {base_url} {self.env.cr.dbname}]"))
        return Markup('').join(parts)

    def _escalate(self, note=''):
        """Email the provider's support from this request. It goes out from
        this database's catchall address, so the provider's replies come back
        into this request (Odoo files them by the email thread) for everyone
        following it. The provider stays a follower, so later messages here
        reach them too."""
        self.ensure_one()
        provider = self._provider_partner()
        self.message_subscribe(partner_ids=provider.ids)
        catchall = self.company_id.catchall_email if 'catchall_email' in self.company_id._fields else False
        sender = self.env.user
        email_from = (f'"{sender.name} ({self.company_id.name})" <{catchall}>' if catchall
                      else sender.email_formatted)
        self.message_post(
            body=self._escalation_body(note),
            subject=f"[{self.reference}] {self.name}",
            partner_ids=provider.ids,
            email_from=email_from,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        self.write({'state': 'escalated', 'escalated_on': fields.Datetime.now(),
                    'escalated_by_id': self.env.uid,
                    'coordinator_id': self.coordinator_id.id or self.env.uid})
        self.activity_ids.sudo().action_feedback(feedback=_("Sent to %s", self.provider_name))
