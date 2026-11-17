# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

ENTRY_LABELS = {
    'tickets': "Get tickets",
    'registration': "Register",
    'info': "More info",
    'free': "",
}


class EventEvent(models.Model):
    """An appearance: an event someone else runs, that we're performing at
    (or speaking, or vending). Listed on the website like our own events,
    but nothing is sold or registered here: the page links to the host's
    tickets or registration and shows their flyer."""
    _inherit = 'event.event'

    is_appearance = fields.Boolean(
        string="Appearance",
        help="Someone else runs this event; we're appearing at it. Odoo takes no "
             "registrations or ticket sales for it: the page links to the host's.")
    appearance_host_id = fields.Many2one(
        'res.partner', string="Hosted By",
        help="Who runs the event (the venue, promoter or organisation).")
    appearance_entry = fields.Selection(
        [('tickets', "Tickets sold by the host"),
         ('registration', "Registration with the host"),
         ('free', "Free entry, nothing needed"),
         ('info', "Just a link for more information")],
        string="Getting In", default='tickets')
    appearance_url = fields.Char(
        string="Link", help="Where people buy tickets, register or read more.")
    appearance_button_label = fields.Char(
        string="Button Text", compute='_compute_appearance_button_label',
        store=True, readonly=False)
    appearance_badge = fields.Char(
        string="Badge", default="Performing",
        help="Shown on this event in the events list, e.g. \"Performing\" or \"Live set\".")
    appearance_material_ids = fields.Many2many(
        'ir.attachment', 'event_appearance_material_rel', 'event_id', 'attachment_id',
        string="Marketing Materials",
        help="The host's flyers, posters and press images, shown on the event page "
             "for anyone to view or download.")

    @api.depends('appearance_entry')
    def _compute_appearance_button_label(self):
        for event in self:
            event.appearance_button_label = _(ENTRY_LABELS[event.appearance_entry]) \
                if event.appearance_entry and ENTRY_LABELS[event.appearance_entry] else False

    @api.constrains('is_appearance', 'appearance_entry', 'appearance_url')
    def _check_appearance_url(self):
        for event in self.filtered('is_appearance'):
            url = (event.appearance_url or '').strip()
            if event.appearance_entry in ('tickets', 'registration', 'info') and not url:
                raise ValidationError(_("Add the link where people get in for %(event)s.",
                                        event=event.name))
            if url and not url.startswith(('https://', 'http://')):
                raise ValidationError(_("The link for %(event)s should start with https://",
                                        event=event.name))

    @api.depends('is_appearance')
    def _compute_event_registrations_open(self):
        """Nothing is registered or sold here for an appearance."""
        super()._compute_event_registrations_open()
        for event in self.filtered('is_appearance'):
            event.event_registrations_open = False

    @api.onchange('appearance_host_id')
    def _onchange_appearance_host_id(self):
        """The host runs it, so they're the organizer shown on the page."""
        if self.is_appearance and self.appearance_host_id:
            self.organizer_id = self.appearance_host_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_appearance') and vals.get('appearance_host_id') \
                    and 'organizer_id' not in vals:
                vals['organizer_id'] = vals['appearance_host_id']
        events = super().create(vals_list)
        events._publish_appearance_materials()
        return events

    def write(self, vals):
        result = super().write(vals)
        if 'appearance_material_ids' in vals or 'is_appearance' in vals:
            self._publish_appearance_materials()
        return result

    def _publish_appearance_materials(self):
        """Marketing materials are for the public: anyone viewing the event
        page can open them."""
        materials = self.filtered('is_appearance').appearance_material_ids
        if materials:
            materials.sudo().write({'public': True})
