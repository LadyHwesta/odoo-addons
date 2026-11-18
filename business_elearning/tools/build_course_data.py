"""Builds the Basic Business Suite courses' data files from the content below.

Run from the repository root after changing a lesson:

    python3 business_elearning/tools/build_course_data.py

It writes business_elearning/data/slide_channel_data.xml. Keep lessons in step with the screens: when a
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



M = 'business_elearning'

# ---- the courses ----
# course: (xmlid, name, description, enroll group xmlid, [sections], quiz), section: (name, [lessons]),
# lesson: (name, html), quiz: [(question, [answers], index of the right one)]

SALES = ('channel_sales', "Customers and Sales",
    "Start the day on My Day, keep the pipeline moving, and send quotes customers sign and pay online.",
    'base.group_user', [
    ("Your day", [
        ("Starting on My Day", ''.join([
            p(path("My Day") + " is a start screen for the day: today's meetings, to-dos, tasks and tickets, "
              "money owed to you and money due, and quotes waiting on customers, each with a link to the full list."),
            shot(M, 'my_day.png', "My Day with today's schedule, tickets, tasks due and money",
                 "a print shop's My Day: a proof review, a ticket, a task due tomorrow and $1,830 overdue."),
            p("To open it every time you log in, tick <strong>Start on My Day</strong> in your " +
              path("Preferences") + " (your picture, top right). Everything on it is yours: other people "
              "see their own day."),
            callout('fa-lightbulb-o', "Work from the top", "Plan with the left column (schedule and to-dos), "
                    "then clear the right column (what needs attention) between meetings."),
        ])),
    ]),
    ("Leads to quotes", [
        ("The pipeline", ''.join([
            p(path("CRM", "Sales", "My Pipeline") + " shows every opportunity as a card, in columns from "
              "<strong>New</strong> to <strong>Won</strong>. Drag a card to the next column as it moves on. Each "
              "column totals the expected revenue."),
            shot(M, 'pipeline.png', "The CRM pipeline with opportunities in four columns",
                 "the pipeline: six opportunities from New to Proposition."),
            p("Requests from your website's " + path("Contact us") + " form arrive here as new leads. The clock "
              "on a card is its next activity: schedule a call or a to-do so nothing goes quiet, and it shows "
              "on your My Day when it's due."),
        ])),
        ("Quotes customers sign and pay online", ''.join([
            p("From an opportunity, " + path("New Quotation") + " starts a quote for that customer. Add the "
              "products, then " + path("Send by Email") + ". The customer opens a link, reads the quote, "
              "signs it and pays the deposit right there."),
            shot(M, 'quote_portal.png', "A quote as the customer sees it, with a Sign & Pay button",
                 "what the customer sees: the quote, a 50% down payment and Sign &amp; Pay."),
            p("Switch it on once in " + path("Sales", "Configuration", "Settings") + ": <strong>Online "
              "Signature</strong> and <strong>Online Payment</strong> (with the deposit percentage). Payments "
              "need a payment provider, set up in " + path("Accounting", "Configuration", "Online Payments",
              "Payment Providers") + "."),
            callout('fa-check', "Signed and paid", "When the customer signs and pays, the quote becomes a "
                    "confirmed sales order on its own, and the payment is recorded.", 'success'),
        ])),
    ]),
], [
    ("How do you make My Day open when you log in?",
     ["Tick Start on My Day in your Preferences", "Pin it in the app drawer", "Ask an administrator",
      "Bookmark the page"], 0),
    ("A customer fills in the Contact us form on your website. Where does it go?",
     ["A new lead in the CRM pipeline", "Your personal inbox only", "A helpdesk ticket", "Nowhere until you import it"], 0),
    ("What does the customer need to do for a quote to become a sales order on its own?",
     ["Sign it and pay the deposit online", "Reply to the email", "Download the PDF", "Call you"], 0),
    ("Where are Online Signature and Online Payment switched on?",
     ["Sales, Configuration, Settings", "Each quote's Other Info tab", "CRM, Configuration", "The website editor"], 0),
])

WORK = ('channel_work', "Projects, Helpdesk and Your Website",
    "Projects that include outside people, customer questions as tickets, and a website that sends you leads.",
    'base.group_user', [
    ("Projects and tickets", [
        ("Tasks for outside contacts", ''.join([
            p("A task can belong to someone outside the company: a freelancer, or the customer themselves. "
              "Set <strong>Assigned Contact</strong> on the task, alongside or instead of staff assignees."),
            shot(M, 'task_contact.png', "A task assigned to a freelance designer",
                 "Final artwork, assigned to a freelance designer."),
            p("The contact becomes a follower, so messages you send from the task's chatter reach them by email, "
              "and their email replies land back on the task."),
        ])),
        ("Helpdesk tickets", ''.join([
            p(path("Helpdesk", "Tickets", "All Tickets") + " lists customers' questions and problems, each with "
              "a number, who has it and its stage."),
            shot(M, 'helpdesk.png', "Two helpdesk tickets", "two tickets: faded banners and a reprint question."),
            p("Customers open tickets by email (each team's <strong>Email Alias</strong> in " +
              path("Helpdesk", "Configuration", "Teams") + ") or from their account on your website. Reply from "
              "the ticket's chatter; your reply is emailed to them and the conversation stays on the ticket."),
        ])),
    ]),
    ("Your website and your system", [
        ("Your website", ''.join([
            p(path("Website") + " opens your site with an <strong>Edit</strong> button: click any text to change "
              "it, and drag blocks in from the left. Its <strong>Contact us</strong> form sends leads to CRM."),
            p("Newsletter sign-ups go to " + path("Email Marketing", "Mailing Lists") + ". Choose a "
              "<strong>Welcome Email</strong> on a list and everyone who signs up gets it once."),
        ])),
        ("Looking after your system", ''.join([
            p(path("Security", "Login Attempts") + " shows failed logins; addresses that keep guessing passwords "
              "are blocked for good, listed in " + path("Security", "IP Rules") + "."),
            p("An administrator can put the apps in order and group them into folders in " +
              path("Settings", "Users & Companies", "App Drawer") + "."),
            callout('fa-life-ring', "Need a hand?", "Your hosting includes support: ask us before changing "
                    "settings you're unsure about."),
        ])),
    ]),
], [
    ("You set a freelancer as a task's Assigned Contact. What happens when you send a message from the task?",
     ["They get it by email, and their reply comes back to the task", "Nothing, contacts can't receive messages",
      "It's posted on your website", "It goes to your helpdesk"], 0),
    ("How can a customer open a helpdesk ticket?",
     ["By emailing the team's alias, or from their account on your website", "Only by phoning",
      "Only through CRM", "By editing your website"], 0),
    ("Someone keeps guessing passwords on your login page. What happens?",
     ["Their address is blocked for good", "Your account is deleted", "Nothing", "The website goes offline"], 0),
    ("Where do you change the words on your website's home page?",
     ["Website, then Edit, then click the text", "Settings, Technical", "Email Marketing", "Helpdesk"], 0),
])


# ---- writing the data ----

def course_xml(module, course, quiz):
    xmlid, name, description, group, sections = course
    out = [f'''    <record id="{xmlid}" model="slide.channel">
        <field name="name">{escape(name)}</field>
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
        f.write('<?xml version="1.0" encoding="utf-8" ?>\n<!-- Built by business_elearning/tools/'
                'build_course_data.py: edit there and rebuild. -->\n<odoo noupdate="1">\n\n' + body + '</odoo>\n')
    print(target)


if __name__ == '__main__':
    write(M, [SALES, WORK])
