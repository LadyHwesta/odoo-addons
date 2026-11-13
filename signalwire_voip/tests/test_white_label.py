# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged

# Customers run these modules in their own Odoo; none of what they show
# may name the phone provider (Meskis Works resells it under its own name).
PUBLIC_MODULES = {
    'signalwire_voip', 'signalwire_voip_click2call', 'signalwire_voip_piper_tts',
    'signalwire_sms', 'signalwire_voip_project', 'signalwire_voip_helpdesk_crm',
    'signalwire_voip_portal',
}
VENDOR = 'signalwire'


@tagged('post_install', '-at_install')
class TestWhiteLabel(TransactionCase):

    def _vendor_named(self, *texts):
        return [t for t in texts if t and VENDOR in str(t).lower()]

    def test_field_labels_and_help(self):
        found = []
        for model in self.env.registry.values():
            for field in model._fields.values():
                if getattr(field, '_module', None) not in PUBLIC_MODULES:
                    continue
                bad = self._vendor_named(field.string, field.help)
                if field.type == 'selection' and isinstance(field.selection, list):
                    bad += self._vendor_named(*[label for _key, label in field.selection])
                found += [f"{model._name}.{field.name}: {t}" for t in bad]
            if getattr(model, '_original_module', None) in PUBLIC_MODULES and not model._abstract:
                found += [f"{model._name} description: {t}"
                          for t in self._vendor_named(model._description)]
        self.assertFalse(found, "\n".join(found))

    def test_menus_groups_actions_and_app_names(self):
        data = self.env['ir.model.data'].search([
            ('module', 'in', list(PUBLIC_MODULES)),
            ('model', 'in', ['ir.ui.menu', 'res.groups', 'ir.actions.act_window', 'ir.cron'])])
        found = []
        for xmlid in data:
            record = self.env[xmlid.model].browse(xmlid.res_id).exists()
            name = record.name if record else ''
            found += [f"{xmlid.module}.{xmlid.name}: {t}" for t in self._vendor_named(name)]
        modules = self.env['ir.module.module'].search([('name', 'in', list(PUBLIC_MODULES))])
        for module in modules:
            found += [f"{module.name}: {t}" for t in self._vendor_named(
                module.shortdesc, module.summary, module.description)]
        self.assertFalse(found, "\n".join(found))

    def test_view_text(self):
        data = self.env['ir.model.data'].search([
            ('module', 'in', list(PUBLIC_MODULES)), ('model', '=', 'ir.ui.view')])
        found = []
        for view in self.env['ir.ui.view'].browse(data.mapped('res_id')).exists():
            arch = view.arch_db or ''
            # Strip technical names (models, fields, xml ids, assets paths).
            import re
            visible = re.sub(r'"[^"]*"', '""', re.sub(r'<!--.*?-->', '', arch, flags=re.S))
            visible = re.sub(r'</?[^>]+>', ' ', visible)
            labels = re.findall(r'(?:string|help|placeholder|title)="([^"]*)"', arch)
            found += [f"{view.key or view.name}: {t}" for t in self._vendor_named(visible, *labels)]
        self.assertFalse(found, "\n".join(found))
