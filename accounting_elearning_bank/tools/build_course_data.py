"""Builds the bank course's data file from the content below.

Run from the repository root after changing a lesson:

    python3 accounting_elearning_bank/tools/build_course_data.py

It writes accounting_elearning_bank/data/slide_channel_data.xml. Keep lessons
in step with the screens: when a menu or button is renamed, change it here,
rebuild, and retake the screenshots with tools/shoot.py.
"""
import os
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---- lesson building blocks (classes styled by course_content.scss) ----

def p(text):
    return f'<p>{text}</p>'


def ul(*items):
    return '<ul>' + ''.join(f'<li>{i}</li>' for i in items) + '</ul>'


def ol(*items):
    return '<ol>' + ''.join(f'<li>{i}</li>' for i in items) + '</ol>'


def path(*steps):
    return '<span class="oe-path">' + ' › '.join(escape(s) for s in steps) + '</span>'


def callout(icon, label, text, kind=''):
    cls = f'oe-callout oe-callout-{kind}' if kind else 'oe-callout'
    return (f'<div class="{cls}"><span class="oe-callout-icon"><i class="fa {icon}" /></span>'
            f'<div><span class="oe-callout-label">{escape(label)}</span><p>{text}</p></div></div>')


def shot(image, alt, caption):
    return (f'<div class="oe-diagram"><img src="/{M}/static/img/{image}" alt="{escape(alt)}" class="img-fluid" />'
            f'<p class="oe-diagram-caption"><span class="oe-diagram-caption-tag">Screenshot</span>{caption}</p></div>')


def flow(*steps):
    parts = []
    for i, (icon, text) in enumerate(steps):
        if i:
            parts.append('<span class="oe-flow-arrow"><i class="fa fa-long-arrow-right" /></span>')
        parts.append(f'<div class="oe-flow-step"><span class="oe-flow-step-icon"><i class="fa {icon}" /></span>'
                     f'{escape(text)}</div>')
    return '<div class="oe-diagram"><div class="oe-flow">' + ''.join(parts) + '</div></div>'


M = 'accounting_elearning_bank'
SAMPLE = ("the sample business in these screenshots is Juniper Hollow Design, with a second business name, "
          "Juniper Hollow Photo, banking at Cedar Valley Credit Union. All made up.")

# ---- the course ----
# course: (xmlid, name, description, enroll group xmlid, [sections], quiz), section: (name, [lessons]),
# lesson: (name, html), quiz: [(question, [answers], index of the right one)]

BANK = ('channel_bank', "Your Bank in Odoo: Set Up Right, Reconcile Every Month",
    "Set each bank account up once so most of the statement books itself, then turn every monthly "
    "statement into books that match the bank to the cent.",
    'account.group_account_invoice', [
    ("How Odoo sees your bank", [
        ("The statement is the truth", ''.join([
            p("If you've kept books in a check register, you're used to entering a payment and then ticking it "
              "off when it clears. Odoo works the other way round: <strong>the bank's statement comes in, and "
              "you explain each line on it</strong>. That's what reconciling is."),
            p("Every line you import is booked to your bank account straight away, so Odoo's bank balance "
              "always follows the real one. What each line <em>was</em> (a customer paying, a purchase, a "
              "transfer, your own money) is the part you, or a rule, fill in."),
            flow(('fa-university', "Bank statement"), ('fa-upload', "Import the file"),
                 ('fa-link', "Explain each line"), ('fa-check', "Books match the bank")),
            callout('fa-info-circle', "Why it's worth it", "When every line is explained, your profit and "
                    "loss, what customers still owe you and what you owe suppliers are all true, because the "
                    "bank has confirmed each one."),
        ])),
        ("Where money waits", ''.join([
            p("Until a line is explained, Odoo parks it in a holding account. Knowing the four of them makes "
              "every screen in this course easier to read:"),
            ul("<strong>Bank Suspense</strong>: a bank line nobody has explained yet. It should be empty "
               "once you've reconciled.",
               "<strong>Outstanding Receipts</strong>: a payment you recorded on an invoice "
               "(" + path("Register Payment") + "), waiting for the bank line that brings the money in.",
               "<strong>Outstanding Payments</strong>: the same for money you've recorded paying out.",
               "<strong>Liquidity Transfer</strong>: money moving between two of your own accounts, waiting "
               "until both statements show it."),
            p("Reconciling a line moves it out of the holding account and onto what it really was: the invoice "
              "it paid, the bill it settled, an expense, or your own money going in or out."),
            callout('fa-lightbulb-o', "Read a balance like a to-do list", "Anything left in these holding "
                    "accounts is something not yet matched. After a month is reconciled, Bank Suspense and "
                    "Liquidity Transfer should both be zero."),
        ])),
    ]),
    ("Set up from day one", [
        ("One journal per bank account", ''.join([
            p("In Odoo a bank account is a <strong>journal</strong> of the type Bank. Give each real account "
              "its own: checking, savings, a business credit card. Each one has its own statement and its own "
              "balance, so mixing two in one journal can never match."),
            p("In " + path("Accounting", "Configuration", "Accounting", "Journals") + " open your bank or "
              "click <strong>New</strong>. Name it so you can't mix it up (bank name and account type), enter "
              "the <strong>Bank Account Number</strong>, and set <strong>Bank Feeds</strong> to "
              "<strong>Import File</strong>."),
            shot('journal_form.png', "A bank journal form", "a checking account set up as a bank journal. "
                 + SAMPLE),
            callout('fa-exchange', "Savings that tops up checking", "Some banks keep deposits in savings and "
                    "move money into checking whenever a card purchase posts. Give savings its own journal "
                    "too: each top-up then shows on both statements, and a rule books both halves to Liquidity "
                    "Transfer (see <em>Rules for the regulars</em>)."),
            callout('fa-calendar', "Start on a clean date", "The easiest start is the day the account opens, "
                    "at zero. If it already had money in it when you started using Odoo, book that opening "
                    "balance once with a journal entry against your Capital account, dated the day before your "
                    "first statement line, so Odoo's balance starts where the bank's did."),
        ])),
        ("Your bank's file layout", ''.join([
            p("Download your statement from online banking as a <strong>CSV</strong> file: the PDF statement "
              "is for reading, the CSV is for importing. Ask for one file per account."),
            p("Each bank lays its file out a little differently, so tell Odoo once which column is which in "
              + path("Accounting", "Configuration", "Accounting", "Statement Sheet Mappings") + ":"),
            ul("<strong>Timestamp Format</strong>: how dates are written, for example <code>%m/%d/%y</code> "
               "for 10/14/26.",
               "<strong>Amount column</strong>: the signed amount (money out is negative). A $ sign and "
               "thousands commas are fine.",
               "<strong>Unique transaction ID column</strong>: the bank's own ID for each line. With it, "
               "importing the same file twice skips the lines you already have.",
               "<strong>Description Column</strong>: the short name you'll see when reconciling, and "
               "<strong>Notes Column</strong> for the bank's longer detail."),
            shot('sheet_mapping_columns.png', "The columns of a statement file layout",
                 "the columns of a credit union's CSV layout."),
            callout('fa-exclamation-triangle', "Leave Balance Column empty if your bank leaves gaps",
                    "Some banks fill the running balance on only some rows. Odoo would then take a wrong "
                    "ending balance from the file. Without it you check the ending balance against the "
                    "statement yourself, which is the real test anyway.", 'warning'),
            p("Then pick the layout on each bank journal as its default, and the import fills it in for you."),
        ])),
        ("Rules for the regulars", ''.join([
            p("Lines that look the same every month don't need you. In " +
              path("Accounting", "Configuration", "Accounting", "Reconciliation Models") +
              " a rule says: when a line's label contains these words, book it to this account."),
            shot('reconcile_rules.png', "A list of reconciliation rules", "rules for top-ups and the owner's "
                 "own money (Automated), plus buttons for the odd ones out (Manual)."),
            ul("<strong>Automated</strong> rules book matching lines as soon as they're imported.",
               "<strong>Manual</strong> rules become buttons on the reconcile screen, for lines you want to "
               "look at first, such as cash withdrawals or bank fees."),
            shot('rule_form.png', "A reconciliation rule", "every line on checking whose label contains "
                 "<em>Transfer From Share 01</em> is a top-up from savings, booked to Liquidity Transfer."),
            p("Copy the words from your own statement's labels: the part that's always the same, such as "
              "<em>Transfer From Share 01</em> or the name on your personal account. Limit a rule to the "
              "journals it belongs to, and check its first month's results."),
        ])),
        ("Your own money, and your business names", ''.join([
            p("When you own the business yourself, money moves between you and it. Keep that out of your "
              "profit and loss:"),
            ul("Money you put in from your personal account goes to <strong>Capital</strong> (owner "
               "contribution).",
               "Money you take out goes to <strong>Owner Draws</strong>. If your chart has no such account, "
               "add one in " + path("Accounting", "Configuration", "Accounting", "Chart of Accounts") +
               " with the type Equity.",
               "A cash withdrawal you can't tie to a receipt is usually a draw. Ask your tax preparer what "
               "fits your situation."),
            callout('fa-user', "A customer paid into your personal account?", "Register the payment on the "
                    "invoice as usual. It then waits in Outstanding Receipts, because no business bank line "
                    "will ever arrive for it. Clear it with a journal entry from Outstanding Receipts to Owner "
                    "Draws (the money is yours now), and match the two in " +
                    path("Accounting", "Accounting", "Reconcile") + ". Never book it against the bank "
                    "account itself: the business bank never saw that money, and its balance would stop "
                    "matching."),
            p("If you trade under more than one business name, Odoo can treat each one as a "
              "<strong>branch</strong> of your company: one business and one bank, but a separate profit "
              "and loss per name. Switch to the branch in the company menu at the top right and enter its "
              "bills there. The main company's bank lines can still be matched to them."),
            shot('branch_bill.png', "A vendor bill for a branch", "a bill entered under the branch, Juniper "
                 "Hollow Photo, and paid from the main company's checking."),
        ])),
    ]),
    ("When the statement arrives", [
        ("Download and import", ''.join([
            ol("In online banking, export each account as CSV for exactly the statement's dates.",
               "On the " + path("Accounting", "Dashboard") + ", click <strong>Import File</strong> on that "
               "account's card (on some installs it says <strong>Import (OCA)</strong>).",
               "Your bank's layout is already chosen. Upload the file and click <strong>Import and Start to "
               "Reconcile</strong>, or <strong>Import and View</strong> to look at the statement first."),
            shot('dashboard_cards.png', "The Accounting dashboard bank cards", "after importing: the rules "
                 "have done most of it, and each card says how many lines still need you."),
            shot('import_wizard.png', "The statement import window", "importing a statement file."),
            callout('fa-shopping-basket', "Enter the bills first", "For purchases, enter the vendor bill "
                    "with its receipt attached before you reconcile (in the right business name, if you have "
                    "branches). Then each card purchase is a one-click match."),
        ])),
        ("Match line by line", ''.join([
            p("Click <strong>Reconcile <em>N</em> Items</strong> on the card. The statement lines are on the "
              "left. For the selected line, the right side shows its bank line, the part still waiting in "
              "Bank Suspense, your rule buttons, and the tabs."),
            shot('reconcile_line.png', "The reconcile screen", "a card purchase still in Bank Suspense. "
                 "Typing the vendor's name in the Reconcile tab's search finds its bill."),
            ol("In the <strong>Reconcile</strong> tab, search for the customer or vendor and click the "
               "invoice, bill or payment the line belongs to.",
               "Or click a rule button, such as Bank Fees, for a line with no invoice behind it.",
               "Or use <strong>Manual operation</strong> to choose the account yourself.",
               "When nothing is left in Bank Suspense, <strong>Reconcile</strong> lights up. Click it."),
            shot('reconcile_matched.png', "A line matched to its bill", "the bill has replaced Bank Suspense, "
                 "so Reconcile is ready."),
            callout('fa-flag', "Not sure?", "Click <strong>To Check</strong> and move on: the line keeps its "
                    "place, and you or your bookkeeper can come back to it."),
        ])),
        ("Prove it matches", ''.join([
            p("A month is done when Odoo agrees with the bank, not just when the list is empty:"),
            ul("Each bank card's <strong>Balance</strong> on the dashboard equals the ending balance on "
               "that account's statement.",
               "<strong>Bank Suspense</strong> is zero: nothing left unexplained.",
               "<strong>Liquidity Transfer</strong> is zero: every transfer shows on both accounts.",
               "<strong>Outstanding Receipts</strong> and <strong>Outstanding Payments</strong> hold only "
               "payments too recent to be on this statement."),
            p("Check the accounts in " + path("Accounting", "Reporting") + " with a trial balance dated the "
              "statement's last day. Then set a lock date for the month so nothing changes it by accident: "
              "see <em>Fiscal years and lock dates</em> in the course <em>Getting Paid and Keeping the "
              "Books</em>."),
        ])),
        ("When it doesn't match", ''.join([
            p("When the dashboard balance and the statement disagree, the difference is almost always one of "
              "these:"),
            ul("<strong>Something posted straight to the bank account</strong> without a statement line, "
               "such as a journal entry. Open the bank account in " +
               path("Accounting", "Configuration", "Accounting", "Chart of Accounts") + ", look at its journal "
               "items, and find the ones with no statement line. Move each to the account it really belongs "
               "to (often Outstanding Receipts or Owner Draws).",
               "<strong>A file imported for the wrong dates</strong>, so a line is missing or belongs to next "
               "month. Compare the dates in Odoo with the statement's.",
               "<strong>The same transaction twice</strong>, from a file without transaction IDs. Delete the "
               "extra statement line.",
               "<strong>A top-up booked on one account only</strong>. Liquidity Transfer then isn't zero: "
               "import the other account's statement too."),
            callout('fa-search', "Find the amount", "Search the journal items for the exact difference. A "
                    "single amount that explains the gap is usually one entry in the wrong place."),
        ])),
    ]),
], [
    ("Your bank's statement shows a card purchase. What do you do with it in Odoo?",
     ["Nothing: Odoo ticks it off when the payment clears",
      "Explain it: match it to its bill, or book it with a rule or an account",
      "Delete it and enter the purchase by hand"], 1),
    ("After you've reconciled a month, which account should be zero?",
     ["Bank Suspense", "Capital", "Owner Draws"], 0),
    ("Your savings tops up checking whenever a purchase posts. How should those top-ups be booked?",
     ["As income on checking", "To Liquidity Transfer on both accounts",
      "As an owner draw from savings"], 1),
    ("A customer paid an invoice into your personal account. Where does that payment end up?",
     ["Booked against the business bank account", "Owner Draws, cleared from Outstanding Receipts",
      "Left in Outstanding Receipts for good"], 1),
])


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


def build():
    body = course_xml(M, BANK[:5], BANK[5])
    return ('<?xml version="1.0" encoding="utf-8" ?>\n<!-- Built by accounting_elearning_bank/tools/'
            'build_course_data.py: edit there and rebuild. -->\n<odoo noupdate="0">\n\n' + body + '</odoo>\n')


if __name__ == '__main__':
    target = os.path.join(ROOT, M, 'data', 'slide_channel_data.xml')
    with open(target, 'w') as f:
        f.write(build())
    print(target)
