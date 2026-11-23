# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models


class SlidePublicationQueue(models.Model):
    _name = 'slide.publication.queue'
    _description = 'Lesson Waiting for the Course Digest'

    slide_id = fields.Many2one('slide.slide', required=True, ondelete='cascade')
    channel_id = fields.Many2one(related='slide_id.channel_id', store=True)


class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    def write(self, vals):
        if vals.get('is_published'):
            # Already published: saving it again isn't news.
            already = self.filtered('is_published')
            if already:
                self = self.with_context(
                    slides_digest_skip_ids=set(self.env.context.get('slides_digest_skip_ids', ())) | set(already.ids))
        return super(SlideSlide, self).write(vals)

    def _post_publication(self):
        skip = self.env.context.get('slides_digest_skip_ids') or ()
        slides = self.filtered(lambda s: s.id not in skip)
        if self.env.context.get('install_mode'):
            # Loaded by a module install or update: one digest per course.
            todo = slides.filtered(lambda s: s.website_published and s.channel_id.publish_template_id)
            if todo:
                queued = self.env['slide.publication.queue'].sudo().search([('slide_id', 'in', todo.ids)])
                self.env['slide.publication.queue'].sudo().create(
                    [{'slide_id': s.id} for s in todo - queued.slide_id])
                self.env.ref('website_slides_publication_digest.cron_publication_digest').sudo()._trigger(
                    fields.Datetime.now() + timedelta(minutes=1))
            return True
        return super(SlideSlide, slides)._post_publication()

    @api.model
    def _cron_send_publication_digests(self):
        queue = self.env['slide.publication.queue'].sudo().search([])
        by_channel = defaultdict(lambda: self.env['slide.slide'])
        for item in queue:
            slide = item.slide_id
            if slide.website_published and not slide.is_category and slide.channel_id:
                by_channel[slide.channel_id] |= slide
        for channel, slides in by_channel.items():
            slides = slides.sorted('sequence')
            base = channel.get_base_url()
            items = Markup('').join(
                Markup('<li><a href="%s">%s</a></li>') % (f"{base}{s.website_url}", s.name) for s in slides)
            subject = self.env._("%(count)s new in %(course)s", count=len(slides), course=channel.name) \
                if len(slides) > 1 else self.env._("New in %(course)s: %(lesson)s",
                                                   course=channel.name, lesson=slides.name)
            body = Markup('<p>%s</p><ul>%s</ul>') % (
                self.env._("New lessons in %(course)s:", course=channel.name), items)
            channel.with_context(mail_post_autofollow_author_skip=True).message_post(
                subject=subject, body=body,
                subtype_xmlid='website_slides.mt_channel_slide_published',
                email_layout_xmlid='mail.mail_notification_light')
        queue.unlink()
