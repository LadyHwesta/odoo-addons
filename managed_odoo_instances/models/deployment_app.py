# -*- coding: utf-8 -*-
from odoo import fields, models


class DeploymentApp(models.Model):
    """A sellable, deployable Odoo app/suite - e.g. "Nonprofit Suite",
    mapping to the real technical module names a deployment.instance's
    database gets installed with. Deliberately a small curated catalog
    (seed data covers the three existing suites), not a free-for-all -
    module_names still allows adding anything else by hand when
    needed, without requiring a new deployment.app record for a
    one-off extra module.
    """
    _name = 'deployment.app'
    _description = 'Deployable Odoo App/Suite'
    _order = 'name'

    name = fields.Char(required=True)
    module_names = fields.Char(
        required=True,
        help="Comma-separated technical Odoo module names installed "
             "when this app is selected, e.g. \"nonprofit_base,donation\".")
    product_template_id = fields.Many2one(
        'product.template', string="Sellable Product",
        help="What this app is billed as, if sold as its own line "
             "item - optional, some apps might only ever be bundled.")

    def module_names_list(self):
        self.ensure_one()
        return [name.strip() for name in (self.module_names or '').split(',') if name.strip()]
