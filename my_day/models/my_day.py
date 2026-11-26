# -*- coding: utf-8 -*-
"""My Day: what the current user should plan and work through today.

get_day() returns the header and a list of sections. Each section comes from
a method named _my_day_section_<key>, listed in _my_day_sections(); a
section returns None when its app isn't installed or the user may not see
it. Other modules add sections by extending _my_day_sections() and adding a
method. Everything runs with the user's own access rights (no sudo), within
the companies selected in the company switcher.
"""
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.tools import format_amount, format_date, format_time
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

LIMIT = 8  # items per section unless the person chose otherwise

# Each person can show or hide every section they're allowed to see, move it
# between the columns, reorder it and choose how many items it lists (My Day
# tab in Preferences). These are the extra options some sections offer:
# 'days' (how far ahead, default, label), 'team' (include team or unassigned
# items, default, label) and 'limit' (a different default item count).
SECTION_OPTIONS = {
    'schedule': {'limit': 30},
    'todo': {'limit': 24, 'days': (0, _lt("Also list to-dos due in the next N days"))},
    'phone': {'team': (True, _lt("Include my call groups' voicemails and callbacks"))},
    'sms': {'team': (True, _lt("Include texts nobody has taken yet"))},
    'leads': {'team': (True, _lt("Show new unassigned leads in my sales teams"))},
    'helpdesk': {'team': (True, _lt("Count unassigned tickets in my teams"))},
    'tasks': {'days': (7, _lt("Task deadlines up to N days ahead"))},
    'money': {'days': (7, _lt("Bills due in the next N days"))},
    'events': {'days': (7, _lt("Events and gigs in the next N days"))},
}


class MyDay(models.AbstractModel):
    _name = 'my.day'
    _description = 'My Day'

    # ---- helpers ----

    def _my_day_tz(self):
        return pytz.timezone(self.env.user.tz or 'UTC')

    def _my_day_today(self):
        return fields.Datetime.now().replace(tzinfo=pytz.UTC).astimezone(self._my_day_tz()).date()

    def _my_day_bounds(self, day, days=1):
        """UTC naive datetimes for the start of `day` and `days` later, in the user's time zone."""
        tz = self._my_day_tz()
        start = tz.localize(datetime.combine(day, time.min))
        end = start + timedelta(days=days)
        return (start.astimezone(pytz.UTC).replace(tzinfo=None),
                end.astimezone(pytz.UTC).replace(tzinfo=None))

    def _my_day_model(self, name):
        """The model if it's installed and the user may read it, else None."""
        if name not in self.env:
            return None
        Model = self.env[name]
        return Model if Model.has_access('read') else None

    def _my_day_company_domain(self, Model, field='company_id'):
        if field in Model._fields:
            return [(field, 'in', self.env.companies.ids + [False])]
        return []

    def _my_day_company_label(self, record, field='company_id'):
        """The company, shown only when several are selected."""
        if len(self.env.companies) < 2 or field not in record._fields:
            return ''
        return record[field].name or ''

    def _my_day_item(self, rec, name=None, meta='', when='', overdue=False, **extra):
        """An item for `rec`. Extra keys: record (what clicking opens, if not
        rec), buttons, url, now..."""
        item = {
            'id': rec.id, 'model': rec._name, 'name': name or rec.display_name,
            'meta': meta, 'when': when, 'overdue': overdue, 'company': self._my_day_company_label(rec),
        }
        item.update(extra)
        return item

    def _my_day_more(self, label, model, domain, name):
        return {'label': label, 'model': model, 'domain': domain, 'name': name}

    def _my_day_button(self, label, icon, model=False, method=False, after='remove', style='secondary', dial=False):
        """A button on an item. Runs `method` on the item's record (model),
        then: 'remove' takes the item off the page, 'dial' calls the number
        the method returns (or `dial` without a method), 'reload' refreshes."""
        return {'label': label, 'icon': icon, 'model': model, 'method': method, 'after': after,
                'style': style, 'dial': dial}

    # ---- each person's choices (my.day.section.setting) ----

    @api.model
    def _my_day_section_options(self):
        """Extra options per section key; extend to give your section some."""
        return dict(SECTION_OPTIONS)

    @api.model
    def _my_day_rows(self):
        """The current person's section settings, in their order, with a row
        added (at its default place) for any section they don't have yet."""
        Setting = self.env['my.day.section.setting'].sudo()
        rows = Setting.search([('user_id', '=', self.env.uid)])
        have = set(rows.mapped('key'))
        options = self._my_day_section_options()
        layout = self._my_day_sections()
        new = []
        for position, (column, key) in enumerate(layout, start=1):
            if key in have:
                continue
            opts = options.get(key, {})
            vals = {'user_id': self.env.uid, 'key': key, 'name': key, 'sequence': position * 10,
                    'column': column, 'limit': opts.get('limit', LIMIT)}
            if 'days' in opts:
                vals.update(has_days=True, days=opts['days'][0], days_label=str(opts['days'][1]))
            if 'team' in opts:
                vals.update(has_team=True, include_team=opts['team'][0], team_label=str(opts['team'][1]))
            new.append(vals)
        if new:
            rows |= Setting._my_day_create(new)
        known = {key for _column, key in layout}
        return rows.filtered(lambda row: row.key in known).sorted(lambda row: (row.sequence, row.id))

    @api.model
    def _my_day_note(self, row, section):
        """Remember the section's title and whether this person can see it,
        for the Preferences list."""
        vals = {}
        available = section is not None
        if row.available != available:
            vals['available'] = available
        if section is not None and section.get('title') and row.name != section['title']:
            vals['name'] = section['title']
        opts = self._my_day_section_options().get(row.key, {})
        for option, field in (('days', 'days_label'), ('team', 'team_label')):
            if option in opts and row[field] != str(opts[option][1]):
                vals[field] = str(opts[option][1])
        if vals:
            row._my_day_write(vals)

    @api.model
    def _my_day_refresh_settings(self):
        """Bring every row up to date, hidden sections too (Preferences)."""
        today = self._my_day_today()
        for row in self._my_day_rows():
            self._my_day_note(row, getattr(self, f'_my_day_section_{row.key}')(today))

    def _my_day_setting(self, key):
        return self.env['my.day.section.setting'].sudo().search(
            [('user_id', '=', self.env.uid), ('key', '=', key)], limit=1)

    def _my_day_limit(self, key, default=LIMIT):
        row = self._my_day_setting(key)
        return max(1, min(30, row.limit)) if row else default

    def _my_day_days(self, key, default):
        row = self._my_day_setting(key)
        return max(0, min(90, row.days)) if row and row.has_days else default

    def _my_day_team(self, key):
        row = self._my_day_setting(key)
        return row.include_team if row and row.has_team else True

    # ---- the day ----

    @api.model
    def _my_day_sections(self):
        """Section keys, in order. Left column first, then right."""
        return [('plan', 'schedule'), ('plan', 'todo'), ('plan', 'phone'), ('plan', 'sms'),
                ('attention', 'security'), ('attention', 'helpdesk'), ('attention', 'leads'),
                ('attention', 'tasks'), ('attention', 'money'), ('attention', 'quotes'),
                ('attention', 'events')]

    @api.model
    def get_day(self, company_ids=None):
        """The day, within the switcher's companies, or the ones picked on
        the page among them (company_ids)."""
        switcher = self.env.companies
        if company_ids:
            picked = switcher.filtered(lambda c: c.id in company_ids)
            if picked:
                return self.with_context(allowed_company_ids=picked.ids)._my_day_build(switcher, picked)
        return self._my_day_build(switcher, switcher)

    @api.model
    def _my_day_build(self, switcher, picked):
        today = self._my_day_today()
        hour = fields.Datetime.now().replace(tzinfo=pytz.UTC).astimezone(self._my_day_tz()).hour
        greeting = _("Good morning") if hour < 12 else _("Good afternoon") if hour < 18 else _("Good evening")
        sections = []
        for row in self._my_day_rows():
            if not row.visible:
                continue
            section = getattr(self, f'_my_day_section_{row.key}')(today)
            self._my_day_note(row, section)
            if section is not None:
                section.update(key=row.key, column=row.column)
                sections.append(section)
        return {
            'greeting': f"{greeting}, {self.env.user.name.split()[0]}",
            'date': format_date(self.env, today, date_format='EEEE d MMMM'),
            'companies': [{'id': c.id, 'name': c.name, 'branch': bool(c.parent_id), 'on': c in picked}
                          for c in switcher],
            'sections': sections,
            'background': self.env.user._my_day_background_url(),
            'background_key': self.env.user.sudo().my_day_background,
            'backgrounds': self.env['res.users']._my_day_backgrounds(),
        }

    @api.model
    def set_background(self, key, image=False):
        """The current user's background: a built-in key, 'custom' with an
        uploaded image (base64), or 'none'."""
        values = {'my_day_background': key}
        if image:
            values['my_day_background_image'] = image
        self.env.user.write(values)
        return self.env.user._my_day_background_url()

    # ---- plan ----

    def _my_day_section_schedule(self, today):
        Event = self._my_day_model('calendar.event')
        if Event is None:
            return None
        start, end = self._my_day_bounds(today)
        # Timed events by their hours; all-day events by their dates (their
        # hours are nominal and can fall outside the day in some time zones).
        events = Event.search([
            ('partner_ids', 'in', self.env.user.partner_id.id),
            '|', '&', ('allday', '=', False), '&', ('start', '<', end), ('stop', '>=', start),
                 '&', ('allday', '=', True), '&', ('start_date', '<=', today), ('stop_date', '>=', today),
        ], order='allday desc, start', limit=self._my_day_limit('schedule', 30))
        tz = self._my_day_tz().zone
        items = []
        for event in events:
            when = _("All day") if event.allday else format_time(
                self.env, event.start, tz=tz, time_format='short')
            items.append(self._my_day_item(
                event, name=event.name, when=when,
                meta=event.location or '', url=event.videocall_location or '',
                now=not event.allday and event.start <= fields.Datetime.now() <= event.stop))
        return {
            'title': _("Today's schedule"), 'icon': 'fa-calendar', 'count': len(items), 'items': items,
            'empty': _("Nothing on your calendar today."),
            'more': {'label': _("Open calendar"), 'action': 'calendar.action_calendar_event'},
        }

    def _my_day_section_todo(self, today):
        Activity = self._my_day_model('mail.activity')
        if Activity is None:
            return None
        ahead = self._my_day_days('todo', 0)
        domain = [('user_id', '=', self.env.uid), ('date_deadline', '<=', today + timedelta(days=ahead))]
        activities = Activity.search(domain, order='date_deadline, id', limit=self._my_day_limit('todo', 24))
        items = []
        for activity in activities:
            overdue = activity.date_deadline < today
            items.append({
                'id': activity.id, 'model': 'mail.activity',
                'name': activity.summary or activity.activity_type_id.name or _("To-do"),
                'meta': activity.res_name or '',
                'when': _("Today") if activity.date_deadline == today
                else format_date(self.env, activity.date_deadline, date_format='d MMM'),
                'overdue': overdue, 'company': '',
                'record': {'model': activity.res_model, 'id': activity.res_id} if activity.res_model else False,
                'buttons': [self._my_day_button(_("Done"), 'fa-check', 'mail.activity', 'action_feedback',
                                                after='remove', style='success')],
            })
        week = Activity.search_count([('user_id', '=', self.env.uid),
                                      ('date_deadline', '>', today + timedelta(days=ahead)),
                                      ('date_deadline', '<=', today + timedelta(days=7))]) if ahead < 7 else 0
        return {
            'title': _("To-dos"), 'icon': 'fa-check-square-o', 'count': len(items), 'items': items,
            'empty': _("Nothing due. Nice."),
            'note': _("%s more due this week", week) if week else '',
            'more': self._my_day_more(_("All my activities"), 'mail.activity',
                                      [('user_id', '=', self.env.uid)], _("My Activities")),
        }

    def _my_day_section_phone(self, today):
        """Unread voicemails and callbacks waiting, for me and my call groups
        (when the phone modules are installed)."""
        Voicemail = self._my_day_model('signalwire.voicemail')
        Callback = self._my_day_model('signalwire.callback_request')
        if Voicemail is None and Callback is None:
            return None
        uid = self.env.uid
        limit = self._my_day_limit('phone')
        groups = self.env['signalwire.call.group'].search([('member_ids', 'in', uid)]) \
            if 'signalwire.call.group' in self.env and self._my_day_team('phone') else []
        tz = self._my_day_tz().zone
        items, count = [], 0
        if Voicemail is not None:
            domain = [('is_read', '=', False), '|', ('user_id', '=', uid), ('call_group_id', 'in', groups.ids if groups else [])]
            count += Voicemail.search_count(domain)
            for vm in Voicemail.search(domain, limit=limit):
                who = vm.partner_id.name or vm.from_number
                snippet = (vm.transcription_text or '').strip().replace('\n', ' ')
                buttons = [self._my_day_button(_("Call back"), 'fa-phone', after='dial', style='primary',
                                               dial=vm.from_number)] if vm.from_number else []
                buttons.append(self._my_day_button(_("Heard"), 'fa-check', 'signalwire.voicemail',
                                                   'action_mark_read', style='success'))
                items.append(self._my_day_item(
                    vm, name=_("Voicemail from %s", who),
                    meta=(snippet[:90] + ('…' if len(snippet) > 90 else '')) or (vm.call_group_id.name or ''),
                    when=self._my_day_when(vm.create_date, today, tz), buttons=buttons))
        if Callback is not None:
            domain = [('state', 'in', ('pending', 'claimed', 'scheduled')), '|', '|',
                      ('target_user_id', '=', uid), ('claimed_by_user_id', '=', uid),
                      ('target_group_id', 'in', groups.ids if groups else [])]
            domain += self._my_day_company_domain(Callback)
            count += Callback.search_count(domain)
            for cb in Callback.search(domain, limit=limit):
                who = cb.partner_id.name or cb.phone_number
                about = cb.related_ref.display_name if 'related_ref' in cb._fields and cb.related_ref else ''
                items.append(self._my_day_item(
                    cb, name=_("Call back %s", who),
                    meta=" · ".join(filter(None, [about, (cb.note or '').strip()[:90]])),
                    when=self._my_day_when(cb.create_date, today, tz), overdue=cb.state == 'pending',
                    # Opening it shows what it's about (set by the receptionist), else the contact.
                    record=cb._open_target() if hasattr(cb, '_open_target') else False,
                    buttons=[
                        self._my_day_button(_("Call back"), 'fa-phone', 'signalwire.callback_request',
                                            'action_call_now', after='dial', style='primary'),
                        self._my_day_button(_("Done"), 'fa-check', 'signalwire.callback_request',
                                            'action_complete', style='success'),
                    ]))
        return {
            'title': _("Phone"), 'icon': 'fa-phone', 'count': count, 'items': items[:limit],
            'empty': _("No voicemails or callbacks waiting."),
        }

    def _my_day_when(self, value, today, tz):
        """A time today, else the date."""
        local = pytz.UTC.localize(value).astimezone(pytz.timezone(tz))
        if local.date() == today:
            return format_time(self.env, value, tz=tz, time_format='short')
        return format_date(self.env, local.date(), date_format='d MMM')

    def _my_day_section_sms(self, today):
        """Texts to our own numbers waiting for an answer: mine, and the
        ones nobody has taken yet."""
        Sms = self._my_day_model('signalwire.sms')
        if Sms is None or 'handled' not in Sms._fields:
            return None
        domain = [('direction', '=', 'inbound'), ('handled', '=', False),
                  ('phone_number_id.number_use', '=', 'own')]
        domain += (['|', ('user_id', '=', self.env.uid), ('user_id', '=', False)] if self._my_day_team('sms')
                   else [('user_id', '=', self.env.uid)])
        tz = self._my_day_tz().zone
        items = []
        for sms in Sms.search(domain, order='create_date', limit=self._my_day_limit('sms')):
            who = sms.partner_id.name or sms.from_number
            text = (sms.body or '').strip().replace('\n', ' ')
            buttons = [self._my_day_button(_("Take"), 'fa-hand-paper-o', 'signalwire.sms', 'action_take',
                                           after='reload')] if not sms.user_id else []
            buttons += [
                self._my_day_button(_("Reply"), 'fa-reply', 'signalwire.sms', 'action_reply',
                                    after='action', style='primary'),
                self._my_day_button(_("Done"), 'fa-check', 'signalwire.sms', 'action_mark_handled',
                                    style='success'),
            ]
            items.append(self._my_day_item(
                sms, name=_("Text from %s", who),
                meta=(text[:90] + ('…' if len(text) > 90 else '')),
                when=self._my_day_when(sms.create_date, today, tz),
                badge=_("Unassigned") if not sms.user_id else '',
                record={'model': 'res.partner', 'id': sms.partner_id.id} if sms.partner_id else False,
                buttons=buttons))
        return {
            'title': _("Texts"), 'icon': 'fa-commenting-o', 'count': Sms.search_count(domain), 'items': items,
            'empty': _("No texts waiting for an answer."),
            'more': self._my_day_more(_("All texts to answer"), 'signalwire.sms', domain, _("Texts to Answer")),
        }

    # ---- needs attention ----

    def _my_day_section_security(self, today):
        """Threat status, for the people who look after security."""
        Event = self._my_day_model('security.event')
        if Event is None:
            return None
        # Only what needs a person, like Security Events' own "Needs Attention":
        # Info events are blocks that worked, shown as a total below instead.
        new = [('state', '=', 'new'), ('severity', 'in', ('warning', 'critical'))]
        counts = dict.fromkeys(('critical', 'warning'), 0)
        for severity, count in Event._read_group(new, ['severity'], ['__count']):
            counts[severity] = count
        level = 'critical' if counts['critical'] else 'warning' if counts['warning'] else 'ok'
        facts = [_("%s critical", counts['critical']), _("%s to review", counts['warning'])]
        Rule = self._my_day_model('security.ip_rule')
        if Rule is not None:
            now = fields.Datetime.now()
            blocked = Rule.search_count([('action', '=', 'block'), '|', ('expires_at', '=', False),
                                         ('expires_at', '>', now)])
            facts.append(_("1 address blocked") if blocked == 1 else _("%s addresses blocked", blocked))
        week = Event.search_count([('severity', '=', 'info'),
                                   ('create_date', '>=', fields.Datetime.now() - timedelta(days=7))])
        facts.append(_("1 automatic block this week") if week == 1
                     else _("%s automatic blocks this week", week))
        rank = {'critical': 0, 'warning': 1}
        events = Event.search(new, order='create_date desc', limit=50).sorted(
            lambda e: (rank.get(e.severity, 3), -e.id))[:self._my_day_limit('security')]
        types = dict(Event._fields['event_type']._description_selection(self.env))
        tz = self._my_day_tz().zone
        items = []
        for event in events:
            detail = (event.detail or '').strip().replace('\n', ' ')
            items.append(self._my_day_item(
                event, name=" · ".join(filter(None, [types.get(event.event_type), event.source_ip])),
                meta=" · ".join(filter(None, [event.login, detail[:90]])),
                when=self._my_day_when(event.create_date, today, tz), overdue=event.severity == 'critical',
                buttons=[self._my_day_button(_("Reviewed"), 'fa-check', 'security.event', 'action_mark_reviewed',
                                             style='success')]))
        return {
            'title': _("Threat status"), 'icon': 'fa-shield', 'count': sum(counts.values()), 'items': items,
            'status': {
                'level': level,
                'label': {'ok': _("All clear"), 'warning': _("Something to review"),
                          'critical': _("Needs you now")}[level],
                'facts': facts,
            },
            'empty': _("Nothing new to review."),
            'more': self._my_day_more(_("All events needing attention"), 'security.event', new,
                                      _("Security Events")),
        }

    def _my_day_section_leads(self, today):
        """My open leads and opportunities (the pipeline's working stages:
        New, Qualified, Proposition...), next step due first; plus new leads
        in my sales teams that nobody has picked up."""
        Lead = self._my_day_model('crm.lead')
        if Lead is None:
            return None
        # Live ones only: not archived (lost leads are archived), not won, and not
        # in a stage folded away in the pipeline (a parking column like "Archived").
        open_ = [('active', '=', True), ('won_status', '!=', 'won'),
                 '|', ('stage_id', '=', False), '&', ('stage_id.is_won', '=', False), ('stage_id.fold', '=', False),
                 ] + self._my_day_company_domain(Lead)
        mine = open_ + [('user_id', '=', self.env.uid)]
        leads = Lead.search(mine, order='priority desc, id desc', limit=100)
        far = today + timedelta(days=36500)
        leads = leads.sorted(lambda lead: (lead.activity_date_deadline or far, -int(lead.priority or 0)))[
            :self._my_day_limit('leads')]
        items = []
        for lead in leads:
            due = lead.activity_date_deadline
            # The next step's date; blank when none is planned.
            when = ('' if not due else _("Today") if due == today
                    else format_date(self.env, due, date_format='d MMM'))
            amount = format_amount(self.env, lead.expected_revenue, lead.company_currency) \
                if lead.expected_revenue and lead.company_currency else ''
            who = lead.partner_id.name or lead.contact_name or lead.partner_name or ''
            items.append(self._my_day_item(
                lead, name=lead.name, when=when, overdue=bool(due and due < today),
                meta=" · ".join(filter(None, [who, lead.stage_id.name, amount]))))
        Team = self.env['crm.team']
        teams = Team.search(['|', ('user_id', '=', self.env.uid), ('crm_team_member_ids.user_id', '=', self.env.uid)]) \
            if Team.has_access('read') and self._my_day_team('leads') else Team
        unassigned = open_ + [('user_id', '=', False), ('team_id', 'in', teams.ids)]
        new_leads = Lead.search(unassigned, order='create_date desc', limit=3) if teams else Lead
        tz = self._my_day_tz().zone
        for lead in new_leads:
            items.append(self._my_day_item(
                lead, name=lead.name, when=self._my_day_when(lead.create_date, today, tz),
                meta=lead.partner_id.name or lead.contact_name or lead.email_from or '',
                badge=_("Unassigned"),
                buttons=[self._my_day_button(_("Take"), 'fa-hand-paper-o', 'my.day', 'take_lead',
                                             after='reload', style='primary')]))
        waiting = Lead.search_count(unassigned) if teams else 0
        return {
            'title': _("Leads"), 'icon': 'fa-star', 'count': Lead.search_count(mine), 'items': items,
            'empty': _("No open leads assigned to you."),
            'note': _("%s unassigned in your teams", waiting) if waiting else '',
            'more': self._my_day_more(_("All my leads"), 'crm.lead', mine, _("My Leads")),
        }

    def take_lead(self):
        """Assign the lead (its id is this record's) to me. Runs with my
        own rights, so only someone allowed to edit it can take it."""
        self.env['crm.lead'].browse(self.ids).write({'user_id': self.env.uid})
        return True

    def _my_day_section_helpdesk(self, today):
        Ticket = self._my_day_model('helpdesk.ticket')
        if Ticket is None or 'stage_id' not in Ticket._fields:
            return None
        open_ = [('stage_id.closed', '=', False)]
        domain = open_ + [('user_id', '=', self.env.uid)] + self._my_day_company_domain(Ticket)
        sla = 'sla_deadline' in Ticket._fields
        tickets = Ticket.search(domain, limit=self._my_day_limit('helpdesk'))  # the ticket's own order: priority first
        tz = self._my_day_tz().zone
        now = fields.Datetime.now()
        items = []
        for ticket in tickets:
            when = ''
            late = ticket.priority in ('3',)
            if sla and ticket.sla_deadline:
                late = ticket.sla_deadline < now
                when = (_("SLA passed") if late else _("SLA %s", self._my_day_when(ticket.sla_deadline, today, tz)))
            number = ticket.number if 'number' in ticket._fields and ticket.number not in (False, '/') else ''
            items.append(self._my_day_item(
                ticket, name=f"{number} {ticket.name}".strip(),
                meta=ticket.partner_id.name or getattr(ticket, 'partner_name', '') or '',
                when=when, overdue=late))
        note = ''
        if 'team_id' in Ticket._fields and 'helpdesk.ticket.team' in self.env and self._my_day_team('helpdesk'):
            teams = self.env['helpdesk.ticket.team'].search([('user_ids', 'in', self.env.uid)]) \
                if 'user_ids' in self.env['helpdesk.ticket.team']._fields else self.env['helpdesk.ticket.team']
            if teams:
                unassigned = Ticket.search_count(open_ + [('user_id', '=', False), ('team_id', 'in', teams.ids)]
                                                 + self._my_day_company_domain(Ticket))
                note = _("%s unassigned in your teams", unassigned) if unassigned else ''
        return {
            'title': _("Helpdesk tickets"), 'icon': 'fa-life-ring', 'count': Ticket.search_count(domain),
            'items': items, 'empty': _("No open tickets assigned to you."), 'note': note,
            'more': self._my_day_more(_("All my tickets"), 'helpdesk.ticket', domain, _("My Tickets")),
        }


    def _my_day_section_tasks(self, today):
        Task = self._my_day_model('project.task')
        if Task is None:
            return None
        _start, week_end = self._my_day_bounds(today, days=self._my_day_days('tasks', 7) + 1)
        today_start, _end = self._my_day_bounds(today)
        domain = [('user_ids', 'in', self.env.uid), ('state', 'not in', ('1_done', '1_canceled')),
                  ('date_deadline', '!=', False), ('date_deadline', '<', week_end)]
        domain += self._my_day_company_domain(Task)
        tasks = Task.search(domain, order='date_deadline, priority desc, id', limit=self._my_day_limit('tasks'))
        tz = self._my_day_tz().zone
        items = []
        for task in tasks:
            items.append(self._my_day_item(
                task, name=task.name, meta=task.project_id.name or '',
                when=format_date(self.env, task.date_deadline, date_format='EEE d MMM', lang_code=None)
                if task.date_deadline >= today_start else
                _("Was due %s", format_date(self.env, task.date_deadline, date_format='d MMM')),
                overdue=task.date_deadline < today_start))
        return {
            'title': _("Tasks due"), 'icon': 'fa-tasks', 'count': Task.search_count(domain), 'items': items,
            'empty': _("No task deadlines this week."),
            'more': self._my_day_more(_("All my tasks"), 'project.task',
                                      [('user_ids', 'in', self.env.uid), ('state', 'not in', ('1_done', '1_canceled'))],
                                      _("My Tasks")),
        }

    def _my_day_section_money(self, today):
        Move = self._my_day_model('account.move')
        if Move is None or not self.env.user.has_group('account.group_account_invoice'):
            return None
        open_moves = [('state', '=', 'posted'), ('payment_state', 'in', ('not_paid', 'partial'))]
        kinds = [
            ('overdue', _("Overdue from customers"),
             open_moves + [('move_type', '=', 'out_invoice'), ('invoice_date_due', '<', today)]),
            ('bills', _("Bills due this week"),
             open_moves + [('move_type', '=', 'in_invoice'),
                           ('invoice_date_due', '<=', today + timedelta(days=self._my_day_days('money', 7)))]),
        ]
        items = []
        for kind, label, domain in kinds:
            groups = Move._read_group(domain + self._my_day_company_domain(Move), ['company_id'],
                                      ['amount_residual_signed:sum', '__count'])
            for company, amount, count in groups:
                amount = abs(amount)
                items.append({
                    'id': f'{kind}-{company.id}', 'model': False, 'name': label,
                    'meta': _("%s documents", count) if count != 1 else _("1 document"),
                    'when': format_amount(self.env, amount, company.currency_id),
                    'overdue': kind == 'overdue', 'company': company.name if len(self.env.companies) > 1 else '',
                    'open': self._my_day_more('', 'account.move', domain + [('company_id', '=', company.id)], label),
                })
        return {
            'title': _("Money"), 'icon': 'fa-money', 'count': len(items), 'items': items,
            'empty': _("Nothing overdue, no bills due this week."),
        }

    def _my_day_section_quotes(self, today):
        Order = self._my_day_model('sale.order')
        if Order is None:
            return None
        domain = [('user_id', '=', self.env.uid), ('state', '=', 'sent')] + self._my_day_company_domain(Order)
        orders = Order.search(domain, order='validity_date, id', limit=self._my_day_limit('quotes'))
        items = []
        for order in orders:
            expires = order.validity_date
            items.append(self._my_day_item(
                order, name=order.partner_id.name, meta=f"{order.name} · {format_amount(self.env, order.amount_total, order.currency_id)}",
                when=_("Expires %s", format_date(self.env, expires, date_format='d MMM')) if expires else '',
                overdue=bool(expires and expires < today)))
        return {
            'title': _("Quotes waiting on customers"), 'icon': 'fa-file-text-o',
            'count': Order.search_count(domain), 'items': items,
            'empty': _("No quotes waiting."),
            'more': self._my_day_more(_("All my quotes"), 'sale.order', domain, _("Quotes Sent")),
        }

    def _my_day_section_events(self, today):
        Event = self._my_day_model('event.event')
        if Event is None:
            return None
        ahead = self._my_day_days('events', 7)
        limit = self._my_day_limit('events')
        start, end = self._my_day_bounds(today, days=ahead + 1)
        domain = [('date_begin', '<', end), ('date_end', '>=', start), ('kanban_state', '!=', 'cancel')]
        domain += self._my_day_company_domain(Event)
        events = Event.search(domain, order='date_begin', limit=limit)
        tz = self._my_day_tz()
        items = []
        for event in events:
            local = pytz.UTC.localize(event.date_begin).astimezone(tz)
            when = (_("Today %s", format_time(self.env, event.date_begin, tz=tz.zone, time_format='short'))
                    if local.date() == today else format_date(self.env, local.date(), date_format='EEE d MMM'))
            seats = (_("%s registered", event.seats_taken)
                     if 'seats_taken' in event._fields and event.seats_taken else '')
            items.append(self._my_day_item(event, name=event.name, when=when, meta=seats,
                                           now=local.date() == today, sort=event.date_begin))
        count = Event.search_count(domain)
        # Booked gigs (Gig Bookings), when installed: they're this week's work too.
        Order = self._my_day_model('sale.order')
        if Order is not None and 'is_gig' in Order._fields:
            gig_domain = [('is_gig', '=', True), ('state', '=', 'sale'), ('gig_date', '>=', today),
                          ('gig_date', '<=', today + timedelta(days=ahead))] + self._my_day_company_domain(Order)
            for gig in Order.search(gig_domain, order='gig_start', limit=limit):
                local_day = gig.gig_date
                when = (_("Today %s", format_time(self.env, gig.gig_start, tz=tz.zone, time_format='short'))
                        if local_day == today else format_date(self.env, local_day, date_format='EEE d MMM'))
                items.append(self._my_day_item(
                    gig, name=gig.venue_name or gig.partner_id.name, meta=_("Gig · %s", gig.partner_id.name),
                    when=when, now=local_day == today, sort=gig.gig_start or fields.Datetime.now()))
                count += 1
            items.sort(key=lambda i: i.pop('sort'))
        else:
            for item in items:
                item.pop('sort')
        return {
            'title': _("Events this week"), 'icon': 'fa-ticket', 'count': count,
            'items': items[:limit], 'empty': _("No events this week."),
            'more': {'label': _("All events"), 'action': 'event.action_event_view'},
        }
