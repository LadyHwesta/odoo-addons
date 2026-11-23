# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.http import request

PLACEHOLDER_NAME = "Booking request"


class CrmLead(models.Model):
    _name = 'crm.lead'
    _inherit = ['crm.lead', 'gig.booking.mixin']

    def _gig_own_ids(self):
        return self.order_ids.ids, []

    @api.model_create_multi
    def create(self, vals_list):
        """A website booking request arrives named just "Booking request":
        name it after the gig so the pipeline is readable."""
        for vals in vals_list:
            if vals.get('gig_date') and not vals.get('company_id'):
                # A booking request belongs to its team's company, else the
                # website's, never to whoever happens to be logged in.
                team = self.env['crm.team'].sudo().browse(vals.get('team_id') or [])
                website = getattr(request, 'website', None) if request else None
                company = team.company_id or (website and website.sudo().company_id)
                if company:
                    vals['company_id'] = company.id
            if vals.get('gig_date') and (vals.get('name') or PLACEHOLDER_NAME) == PLACEHOLDER_NAME:
                kind = dict(self._fields['gig_type'].selection).get(vals.get('gig_type'), '')
                who = vals.get('contact_name') or vals.get('email_from') or ''
                vals['name'] = _("Booking request: %(kind)s %(date)s %(who)s",
                                 kind=kind, date=vals['gig_date'], who=who).replace('  ', ' ').strip()
        return super().create(vals_list)

    def _prepare_opportunity_quotation_context(self):
        """New quotes from this lead start with its gig details."""
        context = super()._prepare_opportunity_quotation_context()
        if self.company_id:
            # The quote belongs where the lead does, so it uses that
            # company's settings and agreement terms.
            context['default_company_id'] = self.company_id.id
        for field in ('gig_date', 'gig_start_hour', 'gig_end_hour', 'gig_type', 'venue_name',
                      'venue_address', 'guest_count', 'gig_setting'):
            value = self[field]
            if value:
                context[f'default_{field}'] = value
        return context
