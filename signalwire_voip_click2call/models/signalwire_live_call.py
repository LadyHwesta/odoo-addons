# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# SignalWire's words for a call that's over.
FINISHED_STATUSES = ('completed', 'busy', 'failed', 'no-answer', 'canceled')
# No real call lasts this long; anything older is closed without asking.
STALE_AFTER = timedelta(hours=6)
# An agent who just missed a queued caller gets them again only if nobody
# else is free, and not before this.
MISSED_COOLDOWN = timedelta(seconds=60)
# How long a queued caller rings one agent before trying the next.
OFFER_TIMEOUT = 20
OFFER_TIMEOUT_MOBILE = 25  # the mobile leg's "press 1" needs a few seconds more


class SignalWireLiveCall(models.Model):
    """A real, currently-in-progress (or just-ended) inbound call -
    distinct from voip_oca's own voip.call (a per-user call *log*
    entry created client-side once a softphone actually answers or
    dials). This record exists the moment SignalWire's own inbound
    webhook fires, tracks the same call_sid throughout its whole
    routing journey (softphone attempt, fallback steps, IVR), and is
    what the live receptionist panel lists and acts on - a panel
    action works by redirecting *this* call's own live cXML flow via
    SignalWire's Compatibility API, never by the receptionist's own
    softphone joining it.
    """
    _name = 'signalwire.live_call'
    _description = 'Live Call'
    _order = 'create_date desc'
    _rec_name = 'from_number'

    call_sid = fields.Char(required=True, index=True)
    phone_number_id = fields.Many2one('signalwire.phone_number', required=True)
    company_id = fields.Many2one(related='phone_number_id.company_id', store=True)
    from_number = fields.Char()
    assigned_user_id = fields.Many2one('res.users')
    state = fields.Selection(
        [('ringing', "Ringing"), ('queued', "In Queue"), ('parked', "On Hold (Being Routed)"),
         ('connected', "Connected"), ('ended', "Ended")],
        default='ringing', required=True)
    # The queue (19.0.4.17.0): a call group's, or one person's own.
    queue_group_id = fields.Many2one('signalwire.call.group', ondelete='set null', index=True)
    queue_user_id = fields.Many2one(
        'res.users', ondelete='set null', index=True,
        help="Waiting for this person only (their personal queue).")
    queued_at = fields.Datetime(
        index=True, help="When the caller joined the queue: their place in line. Kept "
                         "when an agent doesn't answer, so nobody loses their place.")
    offer_user_id = fields.Many2one('res.users', ondelete='set null')
    offered_at = fields.Datetime()
    last_missed_user_id = fields.Many2one('res.users', ondelete='set null')
    last_missed_at = fields.Datetime()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_panel()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals:
            self._notify_panel()
        return result

    @api.model
    def _cron_close_finished_calls(self):
        """Marks calls ended that SignalWire says are over. A call is
        normally marked ended at the end of its routing flow, but a caller
        who hangs up while it's still ringing never reaches that point, so
        without this it stays "in progress" forever (found live
        2026-11-12: seven such calls on the dashboard and panel). Calls
        older than STALE_AFTER are closed without asking."""
        now = fields.Datetime.now()
        open_calls = self.search([
            ('state', '!=', 'ended'),
            ('create_date', '<', now - timedelta(minutes=2)),
        ], limit=200)
        finished = self.browse()
        for call in open_calls:
            if call.create_date < now - STALE_AFTER:
                finished |= call
                continue
            subproject = call.phone_number_id.subproject_id
            try:
                status = subproject.server_id._get_client().compat_get(
                    f'Accounts/{subproject.account_sid}/Calls/{call.call_sid}.json'
                ).get('status')
            except Exception as exc:
                _logger.warning("SignalWire: couldn't check call %s: %s", call.call_sid, exc)
                continue
            if status in FINISHED_STATUSES:
                finished |= call
        if finished:
            finished.write({'state': 'ended'})

    def _notify_panel(self):
        """Broadcasts to every connected user who's a member of the
        Receptionist group - bus.bus._sendone() requires an
        actual record as its target, and every connected user is
        already auto-subscribed to their own group records
        (ir_websocket._build_bus_channel_list() does this
        unconditionally, confirmed by reading Odoo 19's own source),
        so targeting the group itself reaches every open receptionist
        panel with no extra client-side subscription code needed.
        """
        group = self.env.ref('signalwire_voip_click2call.group_signalwire_receptionist')
        self.env['bus.bus']._sendone(group, 'signalwire_live_call/updated', {})

    def _redirect(self, url):
        """Points this call's own live cXML flow at a new URL via
        SignalWire's Compatibility API "Update a call" endpoint - the
        call keeps ringing/playing whatever that new URL returns, the
        caller never has to hang up and call back. Requires the call
        to still actually be in progress on SignalWire's own side; a
        call SignalWire itself already ended returns a real error
        here, surfaced as-is rather than swallowed. sudo() because a
        receptionist's own group has no access to signalwire.server
        (System-group only, same as every other credential-holding
        record in this project) - this method is the one safe,
        narrow operation it's allowed to trigger.
        """
        self.ensure_one()
        server = self.phone_number_id.sudo().subproject_id.server_id
        client = server._get_client()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        client.compat_post(
            f'Accounts/{self.phone_number_id.sudo().subproject_id.account_sid}/'
            f'Calls/{self.call_sid}.json',
            Url=f'{base_url}{url}')

    def action_route_to_user(self, user_id):
        """Blind route: redirect straight to that user's own SIP
        targets, reusing the exact same fallback chain a normal
        direct-user-routed number already gets if unanswered. Takes a
        plain id (not a recordset) since this is called both from
        Python and, via the receptionist panel, over RPC - browsing
        internally keeps one calling convention for both.
        """
        self.ensure_one()
        user = self.env['res.users'].browse(user_id)
        if not user.voip_username and not user.signalwire_desk_phone_ids.filtered(
                'voip_username'):
            raise UserError(_(
                "%(user)s doesn't have a softphone provisioned yet.",
                user=user.name))
        self._redirect(f'/signalwire/voice/route_to_user/{user.id}/{self.phone_number_id.id}')
        self.write({'assigned_user_id': user.id, 'state': 'ringing'})

    def action_park(self, user_id=None):
        """Puts the caller on a "please hold" loop, freeing the
        receptionist to place a normal, separate outbound call to
        check whether a colleague can take it - see this module's own
        README for why this deliberately isn't a 3-way conference
        bridge.
        """
        self.ensure_one()
        url = f'/signalwire/voice/hold_loop/{self.phone_number_id.id}'
        if user_id:
            # Who's being checked: a caller who asks for a callback while
            # holding is asking for them.
            url += f'?user={int(user_id)}'
        self._redirect(url)
        self.state = 'parked'

    def action_send_to_voicemail(self, user_id):
        self.ensure_one()
        user = self.env['res.users'].browse(user_id)
        self._redirect(
            f'/signalwire/voice/route_to_voicemail/{user.id}/{self.phone_number_id.id}')
        self.write({'assigned_user_id': user.id, 'state': 'ringing'})

    # ------------------------------------------------------------------
    # Queues (19.0.4.17.0): nobody is refused. A caller waits in a call
    # group's queue or one person's own; the agent free the longest is
    # offered the caller who has waited the longest, one agent at a time.
    # ------------------------------------------------------------------

    def _queue_label(self):
        self.ensure_one()
        if self.queue_user_id:
            return _("%(name)s's queue", name=self.queue_user_id.name)
        return self.queue_group_id.name or ''

    def _queue_domain(self):
        self.ensure_one()
        if self.queue_user_id:
            return [('queue_user_id', '=', self.queue_user_id.id)]
        return [('queue_group_id', '=', self.queue_group_id.id), ('queue_user_id', '=', False)]

    def _queue_position(self):
        """1 for the next caller to be offered."""
        self.ensure_one()
        # Times are stored to the second: callers who joined in the same
        # second are in the order they arrived (id).
        return self.search_count(self._queue_domain() + [
            ('state', '=', 'queued'),
            '|', ('queued_at', '<', self.queued_at),
            '&', ('queued_at', '=', self.queued_at), ('id', '<', self.id)]) + 1

    def _queue_agents(self):
        self.ensure_one()
        return self.queue_user_id or self.queue_group_id.member_ids

    @api.model
    def _agent_can_take(self, user):
        """Has something to ring, isn't Away, and isn't ringing or on a call
        (an offer marks them ringing, so nobody gets two offers at once)."""
        reachable = user.voip_username or (
            user.signalwire_presence == 'mobile' and user.signalwire_mobile_forward_id)
        return bool(reachable) and user._signalwire_is_free()

    def _queue_candidates(self):
        """Agents who could take this caller now, best first: the one free
        the longest; whoever just missed this caller goes last, and only
        after MISSED_COOLDOWN."""
        self.ensure_one()
        now = fields.Datetime.now()
        free = self._queue_agents().filtered(self._agent_can_take)
        free = free.sorted(lambda u: u.signalwire_call_state_at or fields.Datetime.to_datetime('1970-01-01'))
        missed = self.last_missed_user_id
        if missed in free:
            free = (free - missed)
            if self.last_missed_at and self.last_missed_at < now - MISSED_COOLDOWN:
                free |= missed
        return free

    def _queue_join(self, group=None, user=None):
        """Put this caller in a queue (keeps their place if already there)."""
        self.ensure_one()
        values = {
            'state': 'queued',
            'queue_group_id': group.id if group else False,
            'queue_user_id': user.id if user else False,
            'offer_user_id': False,
        }
        if not self.queued_at or self.state != 'queued':
            values['queued_at'] = fields.Datetime.now()
        self.write(values)

    def _lock_row(self, table, record_id):
        self.env.cr.execute(
            f'SELECT id FROM {table} WHERE id = %s FOR UPDATE SKIP LOCKED', (record_id,))
        return bool(self.env.cr.fetchone())

    def _queue_try_offer(self, agents=None):
        """Offers this queued caller to the best free agent (or the best of
        `agents`). Returns the agent, or an empty recordset if nobody can
        take it or another request already has this caller. The caller's
        and the agent's rows are locked, so two requests can't hand the
        same caller out twice, or one agent two callers."""
        self.ensure_one()
        Users = self.env['res.users']
        if self.state != 'queued' or not self._lock_row('signalwire_live_call', self.id):
            return Users
        self.invalidate_recordset()
        if self.state != 'queued' or self._queue_position() > 1:
            # Nobody jumps the line: only the caller at the front is offered.
            return Users
        for agent in self._queue_candidates():
            if agents is not None and agent not in agents:
                continue
            if not self._lock_row('res_users', agent.id):
                continue
            agent.invalidate_recordset()
            if not self._agent_can_take(agent):
                continue
            now = fields.Datetime.now()
            self.write({'state': 'ringing', 'assigned_user_id': agent.id,
                        'offer_user_id': agent.id, 'offered_at': now})
            agent.sudo().write({'signalwire_call_state': 'ringing',
                                'signalwire_call_state_at': now})
            return agent
        return Users

    def _queue_dispatch_head(self):
        """If someone is free, give them the caller at the front of this
        caller's queue (who is waiting in the hold loop, so is redirected)."""
        self.ensure_one()
        head = self.search(self._queue_domain() + [('state', '=', 'queued')],
                           order='queued_at, id', limit=1)
        if head and head != self:
            agent = head._queue_try_offer()
            if agent:
                return head._queue_push_to(agent)
        return False

    def _queue_offer_missed(self):
        """The agent didn't answer: back in line in the same place, and the
        next free agent (someone else, if anyone) gets the next try."""
        self.ensure_one()
        agent = self.offer_user_id
        now = fields.Datetime.now()
        self.write({'state': 'queued', 'offer_user_id': False,
                    'last_missed_user_id': agent.id or False, 'last_missed_at': now})
        if agent and agent.signalwire_call_state == 'ringing':
            # Left Available, as decided: they may get the next caller.
            agent.sudo().write({'signalwire_call_state': 'idle',
                                'signalwire_call_state_at': now})

    def _queue_push_to(self, agent):
        """Redirects this caller (waiting in the hold loop) to ring `agent`,
        who has just become free. Undoes the offer if SignalWire can't
        redirect it (the caller hung up meanwhile)."""
        self.ensure_one()
        try:
            self._redirect(f'/signalwire/voice/queue_connect/{self.id}')
        except Exception as exc:  # noqa: BLE001 - the call is gone; keep going
            _logger.info("SignalWire: queued call %s couldn't be redirected: %s", self.call_sid, exc)
            self.write({'state': 'ended'})
            agent.sudo().write({'signalwire_call_state': 'idle',
                                'signalwire_call_state_at': fields.Datetime.now()})
            return False
        return True

    @api.model
    def _queue_dispatch_for(self, agent):
        """`agent` just became free: offer them the caller who has waited the
        longest in their personal queue, otherwise in their groups' queues."""
        if not self._agent_can_take(agent):
            return False
        groups = self.env['signalwire.call.group'].sudo().search([('member_ids', 'in', agent.id)])
        for domain in (
                [('queue_user_id', '=', agent.id)],
                [('queue_group_id', 'in', groups.ids), ('queue_user_id', '=', False)]):
            for call in self.sudo().search(domain + [('state', '=', 'queued')], order='queued_at, id'):
                if call._queue_try_offer(agents=agent):
                    return call._queue_push_to(agent)
        return False

    @api.model
    def _cron_queue_tick(self):
        """Safety net, every minute: offer waiting callers to anyone free
        (in case a hang-up report was missed), and send callers who've
        waited past their group's limit to its voicemail choice."""
        now = fields.Datetime.now()
        for call in self.search([('state', '=', 'queued')], order='queued_at, id'):
            limit = call.queue_group_id.queue_max_wait_minutes if not call.queue_user_id else 0
            if limit and call.queued_at and call.queued_at < now - timedelta(minutes=limit):
                try:
                    call._redirect(f'/signalwire/voice/queue_timeout/{call.id}')
                except Exception as exc:  # noqa: BLE001
                    _logger.info("SignalWire: queued call %s is gone: %s", call.call_sid, exc)
                    call.state = 'ended'
                continue
            agent = call._queue_try_offer()
            if agent:
                call._queue_push_to(agent)

    def action_add_to_queue(self, user_id):
        """Receptionist panel: the colleague asked for this caller to wait
        in their personal queue. The caller hears the queue's hold loop
        (with callback and voicemail options) until that person is free."""
        self.ensure_one()
        user = self.env['res.users'].browse(int(user_id)).exists()
        if not user:
            raise UserError(_("Pick a colleague first."))
        self._queue_join(user=user)
        self._redirect(f'/signalwire/voice/queue_wait/{self.id}')

