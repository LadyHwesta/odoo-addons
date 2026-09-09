# Copyright 2016 Tecnativa  - Antonio Espinosa
# Copyright 2017-19 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
# 19.0 port (downstream, not yet upstreamed) - see vendor/oca/README.md.
# Re-pointed from `membership_extension` to `membership`: the OCA `membership`
# 19.0 module absorbed everything membership_extension 18.0 provided.
{
    "name": "Membership withdrawal",
    "summary": "Log membership withdrawal reason and date of request",
    "version": "19.0.1.0.0",
    "category": "Association",
    "website": "https://github.com/OCA/vertical-association",
    "author": "Tecnativa, Onestein, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["membership"],
    "data": [
        "security/ir.model.access.csv",
        "data/membership_withdrawal_reason_data.xml",
        "views/membership_withdrawal_reason_view.xml",
        "views/res_partner_view.xml",
    ],
}
