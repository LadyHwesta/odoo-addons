# -*- coding: utf-8 -*-
"""Website setup, shared by the install hook and the upgrade migration that
fixes a pre-19.0.1.2.0 install (see MENU_BUG in create_nav_menu below).
"""

# (name, url, sequence, [(child name, child url, child sequence), ...])
MENU_SECTIONS = [
    ('Our Club', '/our-club', 15, [
        ('Meetings', '/our-club/meetings', 10),
        ('Officials', '/our-club/club-officials', 20),
        ('Contact Us', '/our-club/contact-us', 30),
        ('Short Skip Newsletter', '/our-club/short-skip', 40),
        ('Club Insurance', '/our-club/club-insurance', 50),
    ]),
    ('Repeaters', '/repeaters', 25, [
        ('DMR', '/repeaters/dmr', 10),
        ('DMR Is Easy', '/repeaters/dmr/is-easy', 20),
        ('DMR Code Plugs', '/repeaters/dmr/code-plugs', 30),
        ('Yaesu System Fusion - WIRES-X', '/repeaters/yaesu-fusion', 40),
        ('IRLP', '/repeaters/irlp', 50),
        ('Repeater Policy', '/repeaters/policy', 60),
    ]),
    ('Events', '/events', 35, [
        ('Classes', '/events/classes', 10),
        ('Amateur Radio Exam Sessions', '/events/ve-testing', 20),
        ('Public Service', '/events/public-service', 30),
        ('Field Day', '/events/field-day', 40),
        ('Winter Field Day', '/events/winter-field-day', 50),
    ]),
    ('Resources', '/resources', 45, [
        ('Service Net Script', '/resources/net-script', 10),
        ('Emergency Services', '/resources/emergency-services', 20),
        ('FRS / GMRS', '/resources/frs-gmrs', 30),
        ('FRS / GMRS FAQs', '/resources/frs-gmrs/faqs', 31),
        ('FRS / GMRS Radios', '/resources/frs-gmrs/radios', 32),
        ('Why FRS / GMRS?', '/resources/frs-gmrs/why', 33),
        ('GMRS Operations During an Emergency', '/resources/frs-gmrs/emergency-ops', 34),
        ('FRS / GMRS Activity in Sonoma County', '/resources/frs-gmrs/activity-in-sonoma-county', 35),
        ('Useful Links', '/resources/useful-links', 40),
        ('Smartphone Apps', '/resources/smartphone-apps', 50),
    ]),
    ('Donate', '/donate', 55, []),
]

HOMEPAGE_URL = '/our-club'


def _all_leaf_urls():
    # Leaf items (no children) keep a real url; a top-level item's own url
    # gets overwritten to "#" the moment it has a child (website.menu.url
    # is a compute depending on child_id), so a stale top-level container
    # from a previous run can't be matched by url. Deliberately NOT swept
    # up by name instead - see the DANGER note in create_nav_menu below.
    urls = []
    for name, url, sequence, children in MENU_SECTIONS:
        if not children:
            urls.append(url)
        urls.extend(child_url for child_name, child_url, child_sequence in children)
    return urls


def _target_website(env):
    """The one website this module's content belongs to. Falls back to
    "whatever website exists" rather than hardcoding an xmlid throughout,
    since a module-local ref to ``website.default_website`` would silently
    target the wrong site on an instance where that isn't the live one.
    """
    return env.ref('website.default_website', raise_if_not_found=False) \
        or env['website'].search([], limit=1)


def create_nav_menu(env, website):
    """(Re)build the club's nav menu, explicitly scoped to one real website.

    MENU_BUG: a ``website.menu`` record created via plain XML data, with no
    explicit ``website_id``, gets silently duplicated by Odoo's own
    ``website.menu.create()`` for every website in the database - and,
    whenever its ``parent_id`` is ``website.main_menu``, an *additional*
    orphan copy (``website_id=False``) is created too and ends up owning
    the record's external ID (see ``odoo/addons/website/models/
    website_menu.py``'s ``create()``). A child menu that references that
    external ID as its own ``parent_id`` then attaches to the orphan, not
    to the scoped copy that's actually part of a website's rendered nav
    tree (walked from that website's own ``menu_id`` downward - never from
    the orphan, and never from ``website.main_menu`` itself, which isn't
    any website's real root either). The dropdown silently never renders.
    That's exactly what this module's original ``data/menus.xml`` hit.

    Building the whole tree here instead, with ``website_id`` set
    explicitly throughout and every ``parent_id`` pointing at an actual,
    correctly-scoped record, sidesteps all of that.

    DANGER, learned the hard way while testing this fix: don't try to also
    sweep up an old *top-level* orphan by name. ``website.menu.unlink()``
    has its own override - if a record being deleted has ``parent_id ==
    website.main_menu`` (true of exactly the old orphans this bug
    produces), it additionally searches for and deletes *every other*
    ``website.menu`` record, on *any* website, that happens to share its
    ``url`` - and a top-level container's url is almost always the generic
    "#" once it has children, which huge numbers of unrelated menus share.
    Deleting one buggy orphan this way took down a real site's entire root
    menu in testing. Leaf items are safe to delete (their ``parent_id`` is
    never ``main_menu``), so only those are swept here - old top-level
    orphans are left behind as inert clutter (parented to ``main_menu``,
    which is no website's real root, so they never render anywhere)
    rather than risk that cascade.
    """
    Menu = env['website.menu']
    Menu.search([('url', 'in', _all_leaf_urls())]).unlink()

    root = website.menu_id

    def add(name, url, sequence, parent):
        return Menu.create({
            'name': name,
            'url': url,
            'sequence': sequence,
            'parent_id': parent.id,
            'website_id': website.id,
        })

    for name, url, sequence, children in MENU_SECTIONS:
        top = add(name, url, sequence, root)
        for child_name, child_url, child_sequence in children:
            add(child_name, child_url, child_sequence, top)


def set_homepage(env, website):
    website.homepage_url = HOMEPAGE_URL


def setup_website_content(env):
    website = _target_website(env)
    if not website:
        return
    set_homepage(env, website)
    create_nav_menu(env, website)


def post_init_hook(env):
    setup_website_content(env)
