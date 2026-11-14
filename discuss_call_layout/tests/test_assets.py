# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged

# Passes when the module loaded without errors and its button is registered.
CHECK = """
const mod = odoo.loader.modules.get('@discuss_call_layout/call_layout');
const registry = odoo.loader.modules.get('@web/core/registry').registry;
if (mod && registry.category('discuss.call/actions').contains('call-layout')
        && mod.callLayout.value === 'gallery') {
    console.log('test successful');
} else {
    console.error('call layout not loaded');
}
"""


@tagged('post_install', '-at_install')
class TestCallLayoutLoads(HttpCase):

    def test_in_the_backend(self):
        self.browser_js('/odoo/discuss', CHECK, login='admin')

    def test_on_the_guest_page(self):
        channel = self.env['discuss.channel']._create_group(
            [self.env.ref('base.partner_admin').id], name='Meeting')
        self.browser_js(channel.invitation_url, CHECK)


LOGIC = """
const { applyCallLayout, callLayout } = odoo.loader.modules.get('@discuss_call_layout/call_layout');
function session(id, extra) {
    const s = Object.assign({ id, hasVideo: true, is_screen_sharing_on: false,
                              mainVideoStreamType: 'camera' }, extra);
    s.notEq = (o) => o !== s;
    return s;
}
const self = session(1), presenter = session(2), other = session(3);
const channel = { id: 7, rtc_session_ids: [self, presenter, other], activeRtcSession: undefined };
channel.notEq = (o) => o !== channel;
const store = { rtc: { selfSession: self, channel } };
const fail = (why) => { throw new Error(why); };

callLayout.value = 'gallery';
presenter.is_screen_sharing_on = true; presenter.mainVideoStreamType = 'screen';
channel.activeRtcSession = presenter;
applyCallLayout(channel, store);
if (channel.activeRtcSession !== presenter) fail('a shared screen should stay big');

presenter.is_screen_sharing_on = false; presenter.mainVideoStreamType = 'camera';
applyCallLayout(channel, store);
if (channel.activeRtcSession !== undefined) fail('after the share, gallery should come back');

callLayout.value = 'speaker';
applyCallLayout(channel, store);
if (!channel.activeRtcSession || channel.activeRtcSession === self) fail('speaker view should show someone else');

callLayout.value = 'gallery';
console.log('test successful');
"""


@tagged('post_install', '-at_install')
class TestCallLayoutLogic(HttpCase):

    def test_screen_share_then_back_to_gallery_and_speaker_view(self):
        self.browser_js('/odoo/discuss', LOGIC, login='admin')


@tagged('post_install', '-at_install')
class TestNoTestsImportedAtLoad(HttpCase):

    def test_no_module_of_ours_loads_its_tests_with_the_server(self):
        """Odoo finds tests by itself. A module whose __init__.py imports its
        tests makes every server start load the test framework, which logs
        "Importing test framework" as an error on production."""
        import os
        from odoo.modules.module import get_module_path
        repo = os.path.dirname(get_module_path('discuss_call_layout'))
        offenders = []
        for name in sorted(os.listdir(repo)):
            init = os.path.join(repo, name, '__init__.py')
            if os.path.isfile(os.path.join(repo, name, '__manifest__.py')) and os.path.isfile(init):
                with open(init) as f:
                    if 'import tests' in f.read():
                        offenders.append(name)
        self.assertFalse(offenders, offenders)
