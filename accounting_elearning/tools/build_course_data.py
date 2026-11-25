"""Builds the accounting course's data files from the content below.

Run from the repository root after changing a lesson:

    python3 accounting_elearning/tools/build_course_data.py

It writes accounting_elearning/data/slide_channel_data.xml. Keep lessons in step with the screens: when a
menu or button is renamed, change it here and rebuild.
"""
import os
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---- lesson building blocks (classes styled by course_content.scss) ----

def p(text):
    return f'<p>{text}</p>'


def path(*steps):
    return '<span class="oe-path">' + ' › '.join(escape(s) for s in steps) + '</span>'


def callout(icon, label, text, kind=''):
    cls = f'oe-callout oe-callout-{kind}' if kind else 'oe-callout'
    return (f'<div class="{cls}"><span class="oe-callout-icon"><i class="fa {icon}" /></span>'
            f'<div><span class="oe-callout-label">{escape(label)}</span><p>{text}</p></div></div>')


def shot(module, image, alt, caption):
    return (f'<div class="oe-diagram"><img src="/{module}/static/img/{image}" alt="{escape(alt)}" class="img-fluid" />'
            f'<p class="oe-diagram-caption"><span class="oe-diagram-caption-tag">Screenshot</span>{caption}</p></div>')


def flow(*steps):
    parts = []
    for i, (icon, text) in enumerate(steps):
        if i:
            parts.append('<span class="oe-flow-arrow"><i class="fa fa-long-arrow-right" /></span>')
        parts.append(f'<div class="oe-flow-step"><span class="oe-flow-step-icon"><i class="fa {icon}" /></span>'
                     f'{escape(text)}</div>')
    return '<div class="oe-diagram"><div class="oe-flow">' + ''.join(parts) + '</div></div>'



M = 'accounting_elearning'

# course: (xmlid, name, description, enroll group xmlid, [sections], quiz)

BOOKS = ('channel_books', "Getting Paid and Keeping the Books",
    "Invoices that chase themselves, a bank statement matched in minutes, and the reports your accountant asks for.",
    'account.group_account_invoice', [
    ("Getting paid", [
        ("Payment reminders", ''.join([
            p("Overdue invoices are chased by email on a schedule. " + path("Accounting", "Configuration",
              "Payment Reminders") + " lists the steps: each has a <strong>Days Offset</strong> from the due "
              "date (negative is before it) and the email it sends."),
            shot(M, 'reminders.png', "Four payment reminder steps from 3 days before due to a final notice",
                 "the standard schedule: a friendly note 3 days before, on the day, a week late and a final notice."),
            p("Reminders go out once a day, each step once per invoice, and stop as soon as it's paid. Edit the "
              "emails' wording in " + path("Settings", "Email Templates") + ". For a customer you'd rather call, "
              "tick <strong>Exclude from Automatic Payment Reminders</strong> on their contact."),
        ])),
        ("Customer statements", ''.join([
            p("A statement lists everything a customer owes. In " + path("Accounting", "Customers", "Customers") +
              ", tick the customer, then " + path("Actions", "Partner Outstanding Statement") + ". "
              "<strong>View</strong> shows it on screen; <strong>Export PDF</strong> makes one to email."),
            shot(M, 'statement_wizard.png', "The outstanding statement options for one customer",
                 "an outstanding statement for Bright Path Tutoring."),
            p("Tick <strong>Show Aging Buckets</strong> to split the total into current, 1 to 30 days late and "
              "so on. The <strong>Activity Statement</strong> instead lists every invoice and payment between "
              "two dates."),
            callout('fa-cog', "Switch them on first", "Statements appear in the Actions menu once "
                    "<strong>Outstanding Statement</strong> and <strong>Activity Statements</strong> are ticked "
                    "in " + path("Accounting", "Configuration", "Settings") + ", under Partner Statements."),
        ])),
    ]),
    ("The bank", [
        ("Importing a bank statement", ''.join([
            p("Download a statement from your bank's website as a CSV or Excel file, then on the " +
              path("Accounting", "Dashboard") + " click <strong>Import File</strong> on the Bank card."),
            shot(M, 'dashboard.png', "The Accounting dashboard with Sales, Purchases and Bank cards",
                 "the dashboard: what's unpaid and late, and the bank card's Import File and Reconcile buttons."),
            p("Pick your bank's <strong>mapping</strong> (which column is the date, the amount, the description), "
              "upload the file, and choose <strong>Import and Start to Reconcile</strong>."),
            shot(M, 'import_statement.png', "The Import Bank Statement File dialog",
                 "importing a statement file with a mapping."),
            callout('fa-table', "Set the mapping up once", "Each bank's file is laid out a little "
                    "differently. Describe yours in " + path("Accounting", "Configuration", "Accounting",
                    "Statement Sheet Mappings") + " the first time, and pick it every month after."),
        ])),
        ("Reconciling", ''.join([
            p("Reconciling means saying what each line on the statement was. Click <strong>Reconcile</strong> on "
              "the Bank card: the statement lines are on the left, and for the selected line the open invoices "
              "and bills are listed below."),
            shot(M, 'reconcile.png', "The reconcile screen with four statement lines and matching invoices",
                 "a $85 card deposit from Pinecone Studio, about to be matched to its invoice."),
            p("Click the invoice it pays to add it, then <strong>Reconcile</strong>: the invoice is marked paid. "
              "For a line with no invoice, such as a bank fee, use a button like <strong>Bank Fees</strong>, or "
              "the <strong>Manual operation</strong> tab to choose the account yourself."),
            callout('fa-question-circle', "Not sure?", "Mark it <strong>To Check</strong> and carry on; your "
                    "bookkeeper can find those later."),
        ])),
    ]),
    ("Reports and closing", [
        ("The reports your accountant asks for", ''.join([
            p(path("Accounting", "Reporting", "Financial Reports") + " has the Trial Balance, General Ledger, "
              "Aged Partner Balance, Open Items and Journal Ledger. Pick a <strong>Date range</strong> (or type "
              "the dates), then <strong>View</strong>, <strong>Export PDF</strong> or <strong>Export "
              "XLSX</strong> for a spreadsheet."),
            shot(M, 'trial_balance_wizard.png', "The Trial Balance options with the 2026 date range",
                 "the Trial Balance for 2026."),
            shot(M, 'trial_balance.png', "A trial balance for the year",
                 "the result: each account's opening balance, debits, credits and closing balance."),
            p("Click any amount to see the entries behind it. The sales tax owed is in " +
              path("Accounting", "Reporting", "Taxes Balance") + "."),
            callout('fa-calendar', "Date ranges", "Make one per year (and per quarter, if you file quarterly) "
                    "in " + path("Accounting", "Configuration", "Date Ranges", "Generate Date Ranges") + "."),
        ])),
        ("Fiscal years and lock dates", ''.join([
            p("Set your fiscal year once in " + path("Accounting", "Configuration", "Accounting", "Fiscal Years") +
              ". Then, once a period is filed, lock it so nothing in it can change by accident: " +
              path("Accounting", "Accounting", "Lock Dates") + "."),
            shot(M, 'lock_dates.png', "The Lock Dates dialog", "lock dates: sales, purchases, tax returns, everything."),
            p("A <strong>Tax Return Lock Date</strong> after you file sales tax, and a <strong>Global Lock "
              "Date</strong> once the accountant has closed the year, are usually all you need."),
            callout('fa-exclamation-triangle', "The hard lock can't be undone", "The <strong>Hard Lock "
                    "Date</strong> is permanent. Leave it to your accountant.", 'warning'),
        ])),
        ("Assets and repeating entries", ''.join([
            p("Equipment you'll use for years (a printer, a vehicle) goes in " + path("Accounting", "Assets",
              "Assets") + " with an <strong>Asset Profile</strong> that says how it depreciates; "
              + path("Compute Assets") + " posts the depreciation for the period."),
            p("For an entry you make the same way every month, such as a loan payment split between interest "
              "and principal, save it once in " + path("Accounting", "Configuration", "Accounting",
              "Journal Entry Templates") + " and use " + path("Accounting", "Accounting",
              "Create Entry from Template") + "."),
        ])),
    ]),
], [
    ("An invoice is due on the 10th. When does a step with a Days Offset of -3 send its email?",
     ["On the 7th", "On the 13th", "On the 10th", "Three days after it's paid"], 0),
    ("Where do you click to bring in this month's bank statement file?",
     ["Import File on the Bank card of the Accounting dashboard", "Sales, Orders", "Settings, Technical",
      "The customer's contact"], 0),
    ("A statement line is a $12 monthly bank fee with no bill. How do you reconcile it?",
     ["With the Bank Fees button or the Manual operation tab", "Create a fake customer invoice",
      "Delete the line", "Leave it until the end of the year"], 0),
    ("Your accountant has closed last year. What stops anyone changing it?",
     ["A Global Lock Date at the year's last day", "Archiving the old invoices", "Changing the fiscal year",
      "Nothing, it's automatic"], 0),
])

# ---- writing the data ----

def course_xml(module, course, quiz):
    xmlid, name, description, group, sections = course
    out = [f'''    <record id="{xmlid}" model="slide.channel">
        <field name="name">{escape(name)}</field>
        <field name="image_1920" type="base64" file="{module}/static/img/cover_{xmlid.removeprefix('channel_')}.png" />
        <field name="channel_type">training</field>
        <field name="description" type="html"><p>{escape(description)}</p></field>
        <field name="visibility">members</field>
        <field name="enroll">invite</field>
        <field name="is_published" eval="True" />
        <field name="enroll_group_ids" eval="[(6, 0, [ref('{group}')])]" />
    </record>
''']
    seq = 0
    for s_index, (section, lessons) in enumerate(sections, 1):
        seq += 10
        out.append(f'''    <record id="{xmlid}_s{s_index}" model="slide.slide">
        <field name="channel_id" ref="{xmlid}" />
        <field name="is_published" eval="True" />
        <field name="name">{escape(section)}</field>
        <field name="is_category" eval="True" />
        <field name="sequence">{seq}</field>
    </record>
''')
        for l_index, (lesson, html) in enumerate(lessons, 1):
            seq += 1
            out.append(f'''    <record id="{xmlid}_s{s_index}_l{l_index}" model="slide.slide">
        <field name="channel_id" ref="{xmlid}" />
        <field name="is_published" eval="True" />
        <field name="name">{escape(lesson)}</field>
        <field name="slide_category">article</field>
        <field name="sequence">{seq}</field>
        <field name="html_content" type="html"><div class="oe-course-content">{html}</div></field>
    </record>
''')
    out.append(f'''    <record id="{xmlid}_quiz" model="slide.slide">
        <field name="channel_id" ref="{xmlid}" />
        <field name="is_published" eval="True" />
        <field name="name">Check what you've learned</field>
        <field name="slide_category">quiz</field>
        <field name="sequence">{seq + 50}</field>
    </record>
''')
    for q_index, (question, answers, right) in enumerate(quiz, 1):
        out.append(f'''    <record id="{xmlid}_q{q_index}" model="slide.question">
        <field name="slide_id" ref="{xmlid}_quiz" />
        <field name="sequence">{q_index}</field>
        <field name="question">{escape(question)}</field>
    </record>
''')
        for a_index, answer in enumerate(answers, 1):
            out.append(f'''    <record id="{xmlid}_q{q_index}_a{a_index}" model="slide.answer">
        <field name="question_id" ref="{xmlid}_q{q_index}" />
        <field name="sequence">{a_index}</field>
        <field name="text_value">{escape(answer)}</field>
        <field name="is_correct" eval="{a_index - 1 == right}" />
    </record>
''')
    return ''.join(out)


def write(module, courses):
    body = ''.join(course_xml(module, course[:5], course[5]) for course in courses)
    target = os.path.join(ROOT, module, 'data', 'slide_channel_data.xml')
    with open(target, 'w') as f:
        f.write('<?xml version="1.0" encoding="utf-8" ?>\n<!-- Built by accounting_elearning/tools/'
                'build_course_data.py: edit there and rebuild. -->\n<odoo noupdate="1">\n\n' + body + '</odoo>\n')
    print(target)


if __name__ == '__main__':
    write(M, [BOOKS])
