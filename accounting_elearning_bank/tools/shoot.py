"""Takes the course screenshots from a running sample database.

1. Build the sample (see sample_business.py) and run Odoo on it, for example
   on http://localhost:8077 with --db-filter=^bankcourse$.
2. Run with a Python that has websocket-client (Odoo's own venv does):

       python3 accounting_elearning_bank/tools/shoot.py http://localhost:8077

It drives headless Google Chrome over the DevTools protocol, logs in as
admin/admin and writes PNGs into static/img. Each shot names a screen by URL,
then optional clicks (by visible text) before the picture is taken.
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'img')
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8077'
PORT = 9333


class Tab:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self.n = 0

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({'id': self.n, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == self.n:
                if 'error' in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get('result', {})

    def js(self, expr):
        r = self.call('Runtime.evaluate', expression=expr, awaitPromise=True, returnByValue=True)
        return r.get('result', {}).get('value')

    def go(self, url, settle=2.5):
        self.call('Page.navigate', url=url)
        self.wait('document.readyState === "complete"')
        time.sleep(settle)

    def wait(self, cond, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            if self.js(f'!!({cond})'):
                return True
            time.sleep(0.3)
        raise TimeoutError(cond)

    def click_text(self, text, selector='*', settle=1.5):
        """Real mouse click on the smallest visible element containing the text."""
        box = self.js(f'''(() => {{
            const want = {json.dumps(text)};
            const els = [...document.querySelectorAll({json.dumps(selector)})].filter(e =>
                e.offsetParent !== null && e.textContent.trim().includes(want));
            els.sort((a, b) => a.textContent.length - b.textContent.length);
            if (!els.length) return null;
            els[0].scrollIntoView({{block: 'center'}});
            const r = els[0].getBoundingClientRect();
            return [r.x + r.width / 2, r.y + r.height / 2];
        }})()''')
        if not box:
            raise LookupError(f'nothing visible says {text!r}')
        x, y = box
        for kind in ('mouseMoved', 'mousePressed', 'mouseReleased'):
            self.call('Input.dispatchMouseEvent', type=kind, x=x, y=y, button='left', clickCount=1)
        time.sleep(settle)

    def type_into(self, selector, text, settle=1.5):
        self.js(f"document.querySelector({json.dumps(selector)}).focus()")
        self.call('Input.insertText', text=text)
        self.call('Input.dispatchKeyEvent', type='keyDown', key='Enter', code='Enter', windowsVirtualKeyCode=13)
        self.call('Input.dispatchKeyEvent', type='keyUp', key='Enter', code='Enter', windowsVirtualKeyCode=13)
        time.sleep(settle)

    def shot(self, name, clip=None):
        params = {'format': 'png'}
        if clip:
            params['clip'] = dict(clip, scale=1)
        data = self.call('Page.captureScreenshot', **params)['data']
        with open(os.path.join(OUT, name), 'wb') as f:
            f.write(base64.b64decode(data))
        print('wrote', name)


def main():
    profile = tempfile.mkdtemp()
    chrome = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}', f'--user-data-dir={profile}',
                               '--window-size=1280,800', '--hide-scrollbars', 'about:blank'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                pages = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
                ws = next(p['webSocketDebuggerUrl'] for p in pages if p['type'] == 'page')
                break
            except Exception:
                time.sleep(0.2)
        tab = Tab(ws)
        tab.call('Page.enable')
        tab.call('Emulation.setDeviceMetricsOverride', width=1280, height=800, deviceScaleFactor=1, mobile=False)
        tab.go(f'{BASE}/web/login')
        tab.js('''document.querySelector('#login').value='admin';
                  document.querySelector('#password').value='admin';
                  document.querySelector('form.oe_login_form').submit();''')
        time.sleep(3)
        tab.js("document.cookie = 'cids=1-17; path=/'")  # both companies: Juniper Hollow Design and its branch
        for step in SHOTS:
            step(tab)
    finally:
        chrome.terminate()


def act(xmlid, rec=None):
    # Opened from the Accounting dashboard, so the top bar shows the Accounting app.
    if xmlid == 'account.open_account_journal_dashboard_kanban':
        return f'{BASE}/odoo/accounting'
    return f'{BASE}/odoo/accounting/action-{xmlid}' + (f'/{rec}' if rec else '')


def ids():
    """Record ids the shots need, read once through JSON-RPC as the logged-in tab."""
    return IDS


IDS = {}


def lookup(tab):
    def one(model, domain):
        return tab.js(f'''fetch('/web/dataset/call_kw/' + {json.dumps(model)} + '/search', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{jsonrpc: '2.0', method: 'call', params: {{model: {json.dumps(model)}, method: 'search',
            args: [{json.dumps(domain)}], kwargs: {{limit: 1, context: {{allowed_company_ids: [1, 17]}}}}}}}})}})
            .then(r => r.json()).then(j => (j.result || [])[0])''')
    IDS['checking'] = one('account.journal', [['code', '=', 'BNK1']])
    IDS['mapping'] = one('account.statement.import.sheet.mapping', [])
    IDS['rule'] = one('account.reconcile.model', [['name', '=', 'Top-up from savings']])
    IDS['bill'] = one('account.move', [['partner_id.name', '=', 'Lumen Camera Supply']])
    print('ids', IDS)


def s_dashboard(tab):
    tab.go(act('account.open_account_journal_dashboard_kanban'), settle=3)
    tab.shot('dashboard_cards.png')


def s_journal(tab):
    tab.go(act('account.action_account_journal_form', IDS['checking']))
    tab.shot('journal_form.png')


def s_mapping(tab):
    tab.go(act('account_statement_import_sheet_file.action_statement_import_sheet_report_mappings', IDS['mapping']))
    tab.js("""[...document.querySelectorAll('.o_form_sheet *')].find(e => e.textContent.trim() === 'Columns'
        || e.textContent.trim() === 'COLUMNS').scrollIntoView({block: 'start'})""")
    time.sleep(1)
    tab.shot('sheet_mapping_columns.png')


def s_rules(tab):
    tab.go(act('account.action_account_reconcile_model'))
    tab.shot('reconcile_rules.png')
    tab.go(act('account.action_account_reconcile_model', IDS['rule']))
    tab.shot('rule_form.png')


def s_import(tab):
    tab.go(act('account_statement_import_file.account_statement_import_action'), settle=3)
    tab.shot('import_wizard.png')


def s_reconcile(tab):
    tab.go(act('account.open_account_journal_dashboard_kanban'), settle=3)
    tab.click_text('Reconcile 3 Items', 'button', settle=3)
    tab.wait("document.body.innerText.includes('Lumen Camera Supply')")
    tab.click_text('Lumen Camera Supply', '.o_kanban_record')
    # The screen keeps an unfinished match between visits: start from a clean line.
    tab.click_text('Reset reconciliation', 'button')
    tab.type_into('.o_notebook .o_searchview_input', 'Lumen')
    tab.shot('reconcile_line.png')
    tab.click_text('Lumen Ca', '.o_notebook .o_data_row td')
    tab.shot('reconcile_matched.png')


def s_bill(tab):
    tab.go(act('account.action_move_in_invoice', IDS['bill']))
    tab.shot('branch_bill.png')


SHOTS = [lookup, s_dashboard, s_journal, s_mapping, s_rules, s_import, s_reconcile, s_bill]

if __name__ == '__main__':
    main()
