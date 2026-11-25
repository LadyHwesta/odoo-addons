"""Sample business for the course screenshots. Run in an odoo-bin shell on a
throwaway database with account_reconcile_oca,
account_statement_import_sheet_file and account_usability installed (generic chart):

    odoo-bin shell -d bankcourse < accounting_elearning_bank/tools/sample_business.py

Juniper Hollow Design (a sole proprietor) with a branch for its second
business name, Juniper Hollow Photo, banking at the made-up Cedar Valley
Credit Union: deposits land in savings, and checking pulls from savings
whenever a card purchase posts. Imports October and leaves the lines that
need a person (two purchases, a bank fee, a customer's check) unreconciled.
"""
import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.environ['SAMPLE_DIR']

company = env['res.company'].browse(1)
company.write({'name': 'Juniper Hollow Design', 'country_id': env.ref('base.us').id})
company.partner_id.tz = 'America/Los_Angeles'
branch = env['res.company'].search([('name', '=', 'Juniper Hollow Photo')]) or env['res.company'].create(
    {'name': 'Juniper Hollow Photo', 'parent_id': company.id})
admin = env.ref('base.user_admin')
admin.write({'company_ids': [(4, company.id), (4, branch.id)], 'tz': 'America/Los_Angeles', 'name': 'Alex Rowan'})
env.user.write({'company_ids': [(4, company.id), (4, branch.id)]})
env = env(context=dict(env.context, allowed_company_ids=[company.id, branch.id]))
Account = env['account.account'].with_company(company)


def account(code, name=None, kind='expense'):
    a = Account.search([('code', '=', code)], limit=1)
    return a or Account.create({'code': code, 'name': name, 'account_type': kind})


transfer, capital = account('101701'), account('301000')
draws = account('310000', 'Owner Draws', 'equity')
supplies, equipment, fees = account('613000', 'Supplies'), account('611000'), account('620000')

bank = env['res.bank'].search([('name', '=', 'Cedar Valley Credit Union')]) or env['res.bank'].create(
    {'name': 'Cedar Valley Credit Union'})


def bank_account(number):
    PB = env['res.partner.bank']
    return PB.search([('acc_number', '=', number)], limit=1) or PB.create(
        {'acc_number': number, 'partner_id': company.partner_id.id, 'bank_id': bank.id})


Mapping = env['account.statement.import.sheet.mapping']
mapping = Mapping.search([('name', '=', 'Cedar Valley Credit Union (CSV)')], limit=1) or Mapping.create({
    'name': 'Cedar Valley Credit Union (CSV)', 'float_thousands_sep': 'comma', 'float_decimal_sep': 'dot',
    'delimiter': 'comma', 'quotechar': '"', 'timestamp_format': '%m/%d/%y', 'timestamp_column': 'Date',
    'amount_type': 'simple_value', 'amount_column': 'Amount', 'transaction_id_column': 'Transaction ID',
    'description_column': 'Name', 'notes_column': 'Description'})

Journal = env['account.journal'].with_company(company)
checking = Journal.search([('code', '=', 'BNK1')], limit=1)
checking.write({'name': 'Cedar Valley Checking', 'bank_account_id': bank_account('204417-S10').id,
                'bank_statements_source': 'file_import_oca', 'default_sheet_mapping_id': mapping.id})
savings = Journal.search([('code', '=', 'BNK2')], limit=1) or Journal.create({
    'name': 'Cedar Valley Savings', 'code': 'BNK2', 'type': 'bank', 'company_id': company.id,
    'bank_account_id': bank_account('204417-S01').id})
savings.write({'bank_statements_source': 'file_import_oca', 'default_sheet_mapping_id': mapping.id})

Model = env['account.reconcile.model'].with_company(company)


def rule(name, label, acc, journals, trigger='auto_reconcile'):
    if Model.search([('name', '=', name)]):
        return
    Model.create({'name': name, 'company_id': company.id, 'trigger': trigger,
                  'match_journal_ids': [(6, 0, journals.ids)],
                  'match_label': 'contains' if label else False, 'match_label_param': label or False,
                  'line_ids': [(0, 0, {'account_id': acc.id, 'amount_type': 'percentage', 'amount_string': '100',
                                       'label': name})]})


rule('Top-up from savings', 'Transfer From Share 01', transfer, checking)
rule('Top-up to checking', 'Transfer To Share 10', transfer, savings)
rule('Money I put in (owner contribution)', 'From Rowan Alex', capital, checking | savings)
rule('Money I took out (owner draw)', 'To Rowan Alex', draws, checking | savings)
rule('Owner draw (cash or personal use)', False, draws, checking | savings, trigger='manual')

Partner = env['res.partner']


def partner(name):
    return Partner.search([('name', '=', name)], limit=1) or Partner.create({'name': name, 'is_company': True})


Move = env['account.move']
if not Move.search_count([('move_type', '=', 'out_invoice')]):
    inv = Move.with_company(company).create({
        'move_type': 'out_invoice', 'partner_id': partner('Pinecone Studio').id, 'invoice_date': '2026-10-01',
        'invoice_line_ids': [(0, 0, {'name': 'Logo and signage design', 'quantity': 1, 'price_unit': 850.0,
                                     'tax_ids': [(5, 0, 0)]})]})
    inv.action_post()
    env['account.payment.register'].with_context(active_model='account.move', active_ids=inv.ids).create(
        {'journal_id': savings.id, 'payment_date': '2026-10-04'})._create_payments()
    bills = Move
    for co, vendor, day, what, acc, amount in (
            (company, 'Paper Moon Art Supply', '2026-10-06', 'Sketchbooks and markers', supplies, 45.20),
            (branch, 'Lumen Camera Supply', '2026-10-13', 'Speedlight for product shoots', equipment, 129.99)):
        env.cr.commit()  # a main-company bill and a branch bill in one transaction trip Odoo's due-date check
        env.invalidate_all()
        bills |= Move.with_company(co).create({
            'move_type': 'in_invoice', 'company_id': co.id, 'partner_id': partner(vendor).id, 'invoice_date': day, 'date': day,
            'invoice_line_ids': [(0, 0, {'name': what, 'account_id': acc.id, 'quantity': 1, 'price_unit': amount,
                                         'tax_ids': [(5, 0, 0)]})]})
    bills.action_post()

for journal, name in ((checking, 'checking_october.csv'), (savings, 'savings_october.csv')):
    if env['account.bank.statement.line'].search_count([('journal_id', '=', journal.id)]):
        continue
    data = open(os.path.join(HERE, 'sample', name), 'rb').read()
    env['account.statement.import'].with_context(journal_id=journal.id).create({
        'statement_file': base64.b64encode(data), 'statement_filename': name,
        'sheet_mapping_id': mapping.id}).import_file_button()

for journal in checking | savings:
    for line in env['account.bank.statement.line'].search([('journal_id', '=', journal.id)], order='date, id'):
        print(journal.code, line.date, '%9.2f' % line.amount, 'OK' if line.is_reconciled else '--', line.payment_ref)
env.cr.commit()
print('SAMPLE READY')
