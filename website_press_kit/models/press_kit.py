# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

LINK_KINDS = [('mix', "Mix"), ('video', "Video"), ('music', "Music"), ('social', "Social"),
              ('press', "Press"), ('other', "Other")]


class WebsitePressKit(models.Model):
    """The press kit of one website, shown at /press-kit."""
    _name = 'website.press.kit'
    _description = 'Press Kit'
    _rec_name = 'name'

    website_id = fields.Many2one('website', required=True, ondelete='cascade',
                                 default=lambda self: self.env['website'].get_current_website())
    is_published = fields.Boolean(string="Published", copy=False)
    name = fields.Char(string="Act Name", required=True, help="As it should appear in print.")
    tagline = fields.Char(help="One line under the name, e.g. Open-format DJ for weddings and clubs.")
    bio = fields.Html(sanitize_attributes=True, help="A short bio promoters can copy.")
    genres = fields.Char(help="Separated by commas, e.g. House, Disco, Top 40.")
    based_in = fields.Char(string="Based In")
    booking_email = fields.Char()
    booking_phone = fields.Char()
    book_url = fields.Char(string="Book Button Link", default='/book',
                           help="Where the Book button goes. Leave empty for no button.")
    show_events = fields.Boolean(string="Show Upcoming Events", default=True)
    rider = fields.Binary(string="Technical Rider", attachment=True)
    rider_filename = fields.Char()
    photo_ids = fields.One2many('website.press.kit.photo', 'kit_id', string="Photos")
    link_ids = fields.One2many('website.press.kit.link', 'kit_id', string="Links")

    _one_per_website = models.Constraint('UNIQUE(website_id)', "A website has one press kit.")

    @api.constrains('book_url')
    def _check_book_url(self):
        for kit in self:
            if kit.book_url and not kit.book_url.startswith(('/', 'https://', 'http://')):
                raise ValidationError(_("The Book button link must be a page of your website (/book) or a web address."))

    def genre_list(self):
        return [g.strip() for g in (self.genres or '').split(',') if g.strip()]

    def _upcoming_events(self, limit=8):
        """Published events still to come on this kit's website, including
        appearances at other people's events."""
        self.ensure_one()
        return self.env['event.event'].sudo().search([
            ('website_published', '=', True), ('date_end', '>=', fields.Datetime.now()),
            ('website_id', 'in', [self.website_id.id, False]),
        ], order='date_begin', limit=limit)

    def action_view_page(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': '/press-kit', 'target': 'new'}


class WebsitePressKitPhoto(models.Model):
    _name = 'website.press.kit.photo'
    _description = 'Press Kit Photo'
    _order = 'sequence, id'

    kit_id = fields.Many2one('website.press.kit', required=True, ondelete='cascade', index=True)
    # Not named "image": Odoo serves a field of that name at 1024 px at most,
    # and this one must download at full size.
    image_full = fields.Image(string="Photo", required=True, max_width=0, max_height=0,
                              help="Full size: it's what they download.")
    image_display = fields.Image(string="Web Size", related='image_full', max_width=1024, max_height=1024,
                                 store=True)
    caption = fields.Char()
    credit = fields.Char(string="Photo Credit")
    sequence = fields.Integer(default=10)

    # Odoo shrinks every uploaded image to 1920 px (base.image_autoresize_max_px);
    # press photos are for print too, so keep the original.
    @api.model_create_multi
    def create(self, vals_list):
        return super(WebsitePressKitPhoto, self.with_context(image_no_postprocess=True)).create(vals_list)

    def write(self, vals):
        return super(WebsitePressKitPhoto, self.with_context(image_no_postprocess=True)).write(vals)

    @api.model
    def _download_name(self, photo):
        base = (photo.kit_id.name or 'press-photo').lower().replace(' ', '-')
        return f"{base}-{photo.id}"


class WebsitePressKitLink(models.Model):
    _name = 'website.press.kit.link'
    _description = 'Press Kit Link'
    _order = 'sequence, id'

    kit_id = fields.Many2one('website.press.kit', required=True, ondelete='cascade', index=True)
    kind = fields.Selection(LINK_KINDS, required=True, default='mix')
    label = fields.Char(required=True, help="e.g. Summer 2026 mix, Live at Ledson")
    url = fields.Char(string="URL", required=True)
    sequence = fields.Integer(default=10)

    @api.constrains('url')
    def _check_url(self):
        for link in self:
            if not (link.url or '').startswith(('https://', 'http://')):
                raise ValidationError(_("Links must be web addresses starting with https://"))
