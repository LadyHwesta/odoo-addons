# -*- coding: utf-8 -*-
{
    'name': 'Gig Bookings',
    'version': '19.0.1.4.0',
    'category': 'Sales/Sales',
    'summary': "Booking requests for performers: gig details, quote with e-sign and deposit, double-booking check",
    'description': """
Gig Bookings
============

For DJs, bands and other performers who are booked for events. A request
form on your website creates a lead with the gig's details (date, times,
venue, event type, guests); quotes carry the same details, and Odoo's own
online signature and deposit book the date. Before a date is quoted or
confirmed, it's checked against your other gigs and events, so you're
never booked twice. A calendar shows every booked date.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'support': 'sales@meskis.net',
    'depends': ['sale_management', 'sale_crm', 'website_crm', 'website_event_appearance'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_model_data.xml',
        'data/ir_cron.xml',
        'views/crm_lead_views.xml',
        'views/sale_order_views.xml',
        'views/product_template_views.xml',
        'views/gig_booking_slot_views.xml',
        'views/res_config_settings_views.xml',
        'views/website_templates.xml',
        'views/portal_templates.xml',
        'report/gig_load_in_report.xml',
    ],
    'installable': True,
}
