# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import file_open

# Same shape as meskis-deploy-agent's own agent/validators.py - failing
# fast here, before ever making an HTTP call to the agent, is friendlier
# than only finding out a domain/db name is malformed from a 422 over
# the wire. Kept in sync by hand (small, stable patterns) rather than
# genuinely shared code between two separate repos/runtimes.
DOMAIN_RE = re.compile(
    r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$')
DB_NAME_RE = re.compile(r'^[a-z][a-z0-9_]{2,62}$')

BOOTSTRAP_SCRIPT_RESOURCE = 'managed_odoo_instances/data/bootstrap_script.sh'


class DeploymentInstance(models.Model):
    """One customer Odoo database, deployed onto a deployment.server -
    the whole point of this module. Billed through
    reseller_subscriptions' own contract.billing.mixin: action_request
    creates the contract (no line yet, nothing invoices) alongside a
    real project.project deployment checklist; action_mark_live is
    what actually starts billing.
    """
    _name = 'deployment.instance'
    _description = 'Managed Customer Odoo Instance'
    _inherit = ['mail.thread', 'contract.billing.mixin']
    _rec_name = 'domain'

    partner_id = fields.Many2one('res.partner', required=True, tracking=True)
    server_id = fields.Many2one('deployment.server', required=True, tracking=True)
    domain = fields.Char(required=True, help="The customer's own domain, e.g. example.com.")
    db_name = fields.Char(
        required=True,
        help="The actual Postgres/Odoo database name on server_id - "
             "lowercase, starts with a letter, letters/digits/"
             "underscores only.")
    app_ids = fields.Many2many('deployment.app', string="Apps to Install")
    admin_email = fields.Char(
        required=True,
        help="The customer contact who becomes this instance's admin login.")
    company_name = fields.Char(required=True)
    state = fields.Selection(
        [('requested', 'Requested'),
         ('bootstrap_pending', 'Server Bootstrap Pending'),
         ('provisioning', 'Provisioning'),
         ('live', 'Live'),
         ('suspended', 'Suspended'),
         ('cancelled', 'Cancelled')],
        default='requested', required=True, tracking=True)
    contract_id = fields.Many2one('contract.contract', string="Billing Contract", copy=False)
    payment_token_id = fields.Many2one(
        'payment.token', string="Saved Payment Method", copy=False)
    project_id = fields.Many2one('project.project', readonly=True, copy=False)

    @api.constrains('domain')
    def _check_domain(self):
        for instance in self:
            if not DOMAIN_RE.match(instance.domain or ''):
                raise ValidationError(_(
                    "%(domain)s doesn't look like a valid domain.", domain=instance.domain))

    @api.constrains('db_name')
    def _check_db_name(self):
        for instance in self:
            if not DB_NAME_RE.match(instance.db_name or ''):
                raise ValidationError(_(
                    "%(db)s isn't a valid database name - lowercase, starts with a "
                    "letter, only letters/digits/underscores.", db=instance.db_name))

    def _all_module_names(self):
        self.ensure_one()
        seen = set()
        result = []
        for app in self.app_ids:
            for name in app.module_names_list():
                if name not in seen:
                    seen.add(name)
                    result.append(name)
        return result

    # -- request: contract shell + the deployment checklist -----------------

    def action_request(self):
        for instance in self:
            if not instance.contract_id:
                contract = self.env['contract.contract'].create({
                    'name': _("%(domain)s - Managed Odoo", domain=instance.domain),
                    'partner_id': instance.partner_id.id,
                    'contract_type': 'sale',
                    'line_recurrence': True,
                })
                instance.contract_id = contract.id
            instance._generate_project()
            needs_bootstrap = (
                instance.server_id.kind == 'dedicated'
                and instance.server_id.bootstrap_state != 'done')
            instance.state = 'bootstrap_pending' if needs_bootstrap else 'provisioning'

    def _generate_project(self):
        self.ensure_one()
        project = self.env['project.project'].create({
            'name': _("Deploy: %(partner)s (%(domain)s)",
                      partner=self.partner_id.name, domain=self.domain),
            'partner_id': self.partner_id.id,
        })
        self.project_id = project.id

        sequence = 10
        needs_bootstrap = (
            self.server_id.kind == 'dedicated' and self.server_id.bootstrap_state != 'done')
        if needs_bootstrap:
            sequence = self._create_bootstrap_tasks(sequence)
        self.env['project.task'].create(self._deployment_task_vals(sequence))

    def _create_bootstrap_tasks(self, sequence):
        """Creates the three bootstrap tasks and attaches the actual
        script to the "run it" one - a real ir.attachment linked via
        res_model/res_id, not project.task's own attachment_ids (that
        field is computed, read-only from *its own* search of
        ir.attachment - writing (4, id) commands to it on create() is
        silently a no-op, caught by this module's own tests).
        Returns the next free sequence number for whatever follows.
        """
        self.ensure_one()
        self.env['project.task'].create({
            'project_id': self.project_id.id, 'sequence': sequence,
            'name': _("Confirm server access (%(hostname)s)",
                      hostname=self.server_id.hostname),
            'description': _(
                "Make sure you can SSH into %(hostname)s as root before "
                "the next step.", hostname=self.server_id.hostname),
        })
        run_task = self.env['project.task'].create({
            'project_id': self.project_id.id, 'sequence': sequence + 10,
            'name': _("Run the bootstrap script on the server"),
            'description': _(
                "Copy the attached bootstrap.sh onto %(hostname)s and run "
                "it as root (sudo bash bootstrap.sh). It prints an agent "
                "token and the Odoo master password once - paste the "
                "token into this server's own Agent Token field before "
                "continuing. Never send this script to the customer - "
                "it's for you to run by hand.", hostname=self.server_id.hostname),
        })
        with file_open(BOOTSTRAP_SCRIPT_RESOURCE, 'rb') as f:
            script_content = f.read()
        self.env['ir.attachment'].create({
            'name': 'bootstrap.sh',
            'type': 'binary',
            'raw': script_content,
            'mimetype': 'text/x-shellscript',
            'res_model': 'project.task',
            'res_id': run_task.id,
        })
        self.env['project.task'].create({
            'project_id': self.project_id.id, 'sequence': sequence + 20,
            'name': _("Confirm the agent is reachable"),
            'description': _(
                "Paste the printed token into this server's Agent Token "
                "field, then click Test Connection on the server record."),
        })
        return sequence + 40

    def _deployment_task_vals(self, sequence):
        self.ensure_one()
        return [
            {
                'project_id': self.project_id.id, 'sequence': sequence,
                'name': _("Create nginx vhost for %(domain)s", domain=self.domain),
            },
            {
                'project_id': self.project_id.id, 'sequence': sequence + 10,
                'name': _("Issue SSL certificate"),
            },
            {
                'project_id': self.project_id.id, 'sequence': sequence + 20,
                'name': _("Create the database and install apps"),
            },
            {
                'project_id': self.project_id.id, 'sequence': sequence + 30,
                'name': _("Preliminary configuration"),
                'description': _(
                    "Chart of accounts, fiscal localization, and any other "
                    "deeper setup the customer needs - not automated, review "
                    "with them directly."),
            },
            {
                'project_id': self.project_id.id, 'sequence': sequence + 40,
                'name': _("Mark instance live"),
            },
        ]

    # -- the actual deployment steps, each a thin call to the agent ---------

    def action_create_vhost(self):
        for instance in self:
            instance.server_id._get_client().create_vhost(instance.domain, instance.db_name)
            if instance.state == 'bootstrap_pending':
                instance.state = 'provisioning'

    def action_issue_certificate(self):
        for instance in self:
            instance.server_id._get_client().issue_certificate(instance.domain)

    def action_create_database(self):
        for instance in self:
            instance.server_id._get_client().create_database(
                instance.db_name, instance._all_module_names(),
                instance.admin_email, instance.company_name)

    def action_mark_live(self):
        """Where billing actually starts - one recurring contract line
        per selected app that has a sellable product, added now rather
        than at action_request time, so a customer who requests an
        instance isn't billed for the days/weeks it takes to actually
        stand it up.
        """
        today = fields.Date.context_today(self)
        for instance in self:
            if instance.state == 'live':
                continue
            billable_apps = instance.app_ids.filtered('product_template_id')
            if billable_apps and instance.contract_id and not instance.contract_id.contract_line_ids:
                instance.contract_id.write({
                    'contract_line_ids': [
                        (0, 0, {
                            'product_id': app.product_template_id.product_variant_id.id,
                            'name': app.name,
                            'quantity': 1,
                            'price_unit': app.product_template_id.list_price,
                            'date_start': today,
                            'recurring_interval': 1,
                            'recurring_rule_type': 'monthly',
                            'recurring_invoicing_type': 'pre-paid',
                        })
                        for app in billable_apps
                    ],
                })
            instance.state = 'live'

    def action_suspend(self):
        self.filtered(lambda i: i.state == 'live').write({'state': 'suspended'})

    def action_cancel(self):
        today = fields.Date.context_today(self)
        for instance in self.filtered(lambda i: i.state in ('live', 'suspended')):
            if instance.contract_id:
                instance.contract_id.contract_line_ids.filtered(
                    lambda line: not line.date_end or line.date_end >= today
                ).write({'date_end': today})
            instance.state = 'cancelled'
