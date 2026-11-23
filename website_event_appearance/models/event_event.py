# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# On an appearance's form, only these tabs stay: the appearance details and
# your own notes. Every other tab (Communication, Questions, Entertainment,
# Logistics, Volunteers, Vendor Map, ...) is about running an event, which the
# host does; tabs added by modules installed later are hidden too.
APPEARANCE_FORM_PAGES = {'appearance', 'event_notes'}
# Fields about registrations and badges, which don't apply either.
APPEARANCE_HIDDEN_FIELDS = ('seats_limited', 'seats_max', 'badge_format', 'badge_image',
                            'ticket_instructions')

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

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form' and arch.xpath("//field[@name='is_appearance']"):
            self._appearance_hide_unused(arch)
        return arch, view

    @api.model
    def _appearance_hide_unused(self, arch):
        """Hide what only matters when we run the event ourselves, whatever
        module added it: the tabs, the smart buttons (attendees, sales, ...)
        and the registration and badge fields."""
        def hide(node):
            current = (node.get('invisible') or '').strip()
            if current in ('1', 'True', 'true'):
                return
            node.set('invisible', f"({current}) or is_appearance"
                     if current and current not in ('0', 'False', 'false') else 'is_appearance')

        for page in arch.xpath("//sheet/notebook/page"):
            if page.get('name') not in APPEARANCE_FORM_PAGES:
                hide(page)
        for button in arch.xpath("//div[@name='button_box']/*"):
            # Keep "Go to Website": the public page is the point of an appearance.
            if button.get('widget') != 'website_redirect_button':
                hide(button)
        for name in APPEARANCE_HIDDEN_FIELDS:
            for node in arch.xpath(f"//field[@name='{name}'] | //label[@for='{name}']"):
                parent = node.getparent()
                # The "Limit Registrations" line and the ticket-instructions block
                # are a label plus a wrapper: hide the wrapper too.
                if node.tag == 'field' and parent.tag in ('div', 'group') and parent.get('name') != 'button_box' \
                        and name in ('seats_limited', 'ticket_instructions'):
                    hide(parent)
                hide(node)

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
