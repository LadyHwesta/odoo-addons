# -*- coding: utf-8 -*-
import re

from odoo import _, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _namecheap_registrant_fields(self):
        """Map this partner's billing address onto Namecheap's registrant
        contact fields (RegistrantFirstName, RegistrantAddress1, etc.) -
        per the scoping decision, the *ordering customer's* address is
        used directly rather than collecting separate WHOIS contact
        info at checkout.

        domains.create actually needs FOUR contact roles - Registrant,
        Tech, Admin, AuxBilling - not just Registrant (verified against
        a real client's request-building code, 2026-09-14, since
        Namecheap's own docs block automated fetching same as
        everywhere else in this project). This method returns only the
        bare field names (FirstName, LastName, ...) without a role
        prefix; the caller repeats the same dict under all four role
        prefixes, matching the "one person acts as all contact types"
        convention that reference client also uses.

        :raises UserError: if a field domains.create requires is
            missing from the partner's address - better to fail with a
            clear message here than send an incomplete request and get
            back an opaque Namecheap error.
        """
        self.ensure_one()
        missing = [
            label for field, label in [
                ('street', "street address"), ('city', "city"),
                ('zip', "postal code"), ('country_id', "country"),
                ('phone', "phone number"), ('email', "email address"),
            ] if not self[field]
        ]
        if missing:
            raise UserError(_(
                "%(partner)s's address is missing %(missing)s - needed to "
                "register a domain (used as the ICANN registrant contact).",
                partner=self.name, missing=", ".join(missing)))

        name_parts = self.name.strip().split(maxsplit=1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else name_parts[0]

        return {
            'FirstName': first_name,
            'LastName': last_name,
            'Address1': self.street,
            'Address2': self.street2 or '',
            'City': self.city,
            'StateProvince': self.state_id.name or '',
            'PostalCode': self.zip,
            'Country': self.country_id.code,
            'Phone': self._namecheap_format_phone(),
            'EmailAddress': self.email,
        }

    def _namecheap_format_phone(self):
        """Namecheap wants "+CountryCallingCode.DigitsOnly", e.g.
        "+1.6613102107" - a partner's own phone field is free text (any
        format), so this strips everything but digits and splits off
        the country's own calling code, prepending it if the number
        didn't already start with a "+".

        Best-effort, not bulletproof for every country's calling-code
        length when the number already had a "+" prefix - Namecheap's
        own validation is the real backstop here, same as everywhere
        else in this project that defers to the far side's own error
        messages rather than trying to fully replicate its validation.
        """
        self.ensure_one()
        digits = re.sub(r'\D', '', self.phone or '')
        code = str(self.country_id.phone_code or '')
        had_plus = (self.phone or '').strip().startswith('+')
        if had_plus and code and digits.startswith(code):
            return f'+{code}.{digits[len(code):]}'
        if code:
            return f'+{code}.{digits}'
        return f'+{digits}'
