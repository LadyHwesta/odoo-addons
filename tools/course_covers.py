#!/usr/bin/env python3
"""Course cover images for every eLearning course, one picture per subject.

Drawn as constellations (light lines, ringed nodes at the corners, one glowing
hub), the same family as the Meskis product images but without the bear: most
of these courses run on other organizations' websites. Each suite gets its own
night-sky palette; each course gets its own picture.

    python3 tools/course_covers.py            # writes every cover
    python3 tools/course_covers.py channel_x  # only the named course(s)
    python3 tools/course_covers.py --sheet out.png  # also a contact sheet

Writes <repo>/<module>/static/img/cover_<course>.png (1024 x 1024). The
picture stays inside the middle 16:9 band, because the course cards crop
the square to 16:9. Needs rsvg-convert (brew install librsvg) and Pillow.
"""
import math
import random
import subprocess
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]  # ~/Documents, beside every repo

PALETTES = {
    # name: (sky inner, sky outer, line, node, accent)
    'business':   ('#1D5466', '#0B2530', '#EAF4F6', '#6FD3E0', '#F4B740'),
    'general':    ('#284A78', '#111E36', '#ECF2FA', '#8CC8FF', '#FFB454'),
    'club':       ('#21386B', '#0B1430', '#EEF2FB', '#9AD1FF', '#FF8A3D'),
    'performers': ('#4A1F6E', '#1A0B2B', '#F5EEFB', '#B9A0FF', '#FF4FA3'),
    'nonprofit':  ('#22574A', '#0C2621', '#EEF7F2', '#8FE0B9', '#F6C445'),
    'practitioner':  ('#55294F', '#1F0E22', '#FBF1F3', '#F7CDBF', '#F48FB1'),
    'meskis':     ('#3A2850', '#1C1428', '#FDF5F7', '#C4B5D0', '#EC3072'),
}

# (repo, module, course xml id, palette, picture)
COURSES = [
    ('odoo-addons', 'business_elearning', 'channel_sales', 'business', 'funnel'),
    ('odoo-addons', 'business_elearning', 'channel_work', 'business', 'kanban'),
    ('odoo-addons', 'resource_booking_online_elearning', 'channel_online_booking', 'general', 'calendar_check'),
    ('odoo-addons', 'calendar_public_meeting_elearning', 'channel_public_meetings', 'general', 'lectern'),
    ('odoo-addons', 'dms_elearning_team_folder', 'channel_team_folders', 'general', 'folder'),
    ('odoo-addons', 'elearning_video_meetings', 'channel_video_meetings', 'general', 'video'),
    ('odoo-addons', 'telehealth_booking_elearning', 'channel_telehealth', 'general', 'monitor_pulse'),
    ('odoo-addons', 'accounting_elearning', 'channel_books', 'general', 'book_coin'),
    ('odoo-addons', 'accounting_elearning_bank', 'channel_bank', 'general', 'bank'),
    ('odoo-addons', 'club_elearning_amateur_radio', 'channel_amateur_radio', 'club', 'tower'),
    ('odoo-addons', 'club_elearning_membership', 'channel_membership', 'club', 'member_card'),
    ('odoo-addons', 'club_elearning_equipment_loan', 'channel_equipment_loan', 'club', 'crate'),
    ('odoo-addons', 'performers_elearning', 'channel_bookings', 'performers', 'calendar_note'),
    ('odoo-addons', 'performers_elearning', 'channel_gear_music', 'performers', 'speaker'),
    ('odoo-addons', 'performers_elearning', 'channel_promotion', 'performers', 'star'),
    ('odoo-addons', 'performers_elearning_events', 'channel_own_events', 'performers', 'ticket'),
    ('odoo-elearning', 'elearning_website', 'channel_website', 'general', 'browser'),
    ('nonprofit-addons', 'nonprofit_elearning_event_parade', 'channel_event_parade', 'nonprofit', 'bunting'),
    ('nonprofit-addons', 'nonprofit_elearning_donations', 'channel_donations', 'nonprofit', 'heart'),
    ('nonprofit-addons', 'nonprofit_elearning_grants', 'channel_grants', 'nonprofit', 'grant'),
    ('nonprofit-addons', 'nonprofit_elearning_event_venue', 'channel_event_venue', 'nonprofit', 'stall'),
    ('nonprofit-addons', 'nonprofit_elearning_finance', 'channel_finance', 'nonprofit', 'scale'),
    ('nonprofit-addons', 'nonprofit_elearning_event_logistics', 'channel_event_logistics', 'nonprofit', 'clipboard'),
    ('nonprofit-addons', 'nonprofit_elearning_volunteers', 'channel_volunteers', 'nonprofit', 'people'),
    ('nonprofit-addons', 'nonprofit_elearning_event_entertainment', 'channel_event_entertainment', 'nonprofit', 'stage'),
    ('nonprofit-addons', 'nonprofit_elearning_access_rights', 'channel_access_rights', 'nonprofit', 'key'),
    ('practitioner-addons', 'practice_elearning_billing', 'channel_billing', 'practitioner', 'receipt'),
    ('practitioner-addons', 'practice_elearning_client_portal', 'channel_client_portal', 'practitioner', 'camera'),
    ('practitioner-addons', 'practice_elearning', 'channel_records', 'practitioner', 'chart'),
    ('practitioner-addons', 'practice_elearning', 'channel_scheduling', 'practitioner', 'clock'),
    ('practitioner-addons', 'practice_elearning_review', 'channel_reviews', 'practitioner', 'star'),
    ('meskis-reseller-addons', 'meskis_team_elearning', 'channel_standards', 'meskis', 'compass'),
    ('meskis-reseller-addons', 'meskis_team_elearning', 'channel_services', 'meskis', 'tag'),
    ('meskis-reseller-addons', 'meskis_team_elearning', 'channel_sales', 'meskis', 'target'),
    ('meskis-reseller-addons', 'meskis_team_elearning', 'channel_support', 'meskis', 'headset'),
    ('meskis-reseller-addons', 'meskis_team_elearning', 'channel_pay', 'meskis', 'coins'),
    ('meskis-reseller-addons', 'meskis_demo_elearning', 'channel_getting_around', 'meskis', 'map'),
]


# -- geometry, on a 100 x 100 grid -------------------------------------------

def arc(cx, cy, r, a0, a1, n, ry=None):
    """n points from angle a0 to a1 (degrees, 0 = right, 90 = down)."""
    ry = r if ry is None else ry
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1)))) for i in range(n)]


def ring(cx, cy, r, n, start=-90, ry=None):
    return arc(cx, cy, r, start, start + 360 * (n - 1) / n, n, ry)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# Element kinds:
#   L open line   C closed outline   A accent line (open)   AC accent outline
#   F faint accent fill (no nodes)   P panel: hides what is behind it
#   S soft line (no nodes)           N extra nodes   H hub
#   W spokes from a hub (first point) to the other points
#   O / AO plain circle (line / accent colour), for heads, coins and seals
def L(*p): return ('L', list(p))
def C(p): return ('C', list(p))
def A(*p): return ('A', list(p))
def AC(p): return ('AC', list(p))
def F(p): return ('F', list(p))
def P(p): return ('P', list(p))
def S(*p): return ('S', list(p))
def N(*p): return ('N', list(p))
def H(x, y): return ('H', [(x, y)])
def O(x, y, r): return ('O', [(x, y), (r, 0)])
def AO(x, y, r): return ('AO', [(x, y), (r, 0)])
def W(hub, pts): return ('W', [hub] + list(pts))


def calendar(extra):
    dots = [N(*[(x, y) for x in (28, 40, 52, 64, 76)]) for y in (48,)]
    return [C(rect(16, 22, 84, 84)), L((16, 36), (84, 36)),
            L((32, 14), (32, 28)), L((68, 14), (68, 28)), *dots] + extra


def heart_pts():
    pts = []
    for i in range(14):
        t = 2 * math.pi * i / 14
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((50 + x * 2.0, 44 + y * 2.0))
    return pts


def bunting(y0, sag, flags, offset=0):
    def at(t):
        return (8 + 84 * t, y0 + sag * 4 * t * (1 - t))
    out = [S(*[at(i / 12) for i in range(13)])]
    for i in range(flags):
        t = (i + 0.5 + offset) / (flags + offset)
        (xa, ya), (xb, yb) = at(t - 0.045), at(t + 0.045)
        tip = ((xa + xb) / 2, (ya + yb) / 2 + 14)
        out.append((F if i % 2 else C)([(xa, ya), (xb, yb), tip]))
        if i % 2:
            out.append(AC([(xa, ya), (xb, yb), tip]))
    return out


PICTURES = {
    'bank': [
        C([(14, 36), (50, 14), (86, 36)]), L((16, 40), (84, 40)),
        S((26, 44), (26, 76)), S((42, 44), (42, 76)), S((58, 44), (58, 76)), S((74, 44), (74, 76)),
        L((18, 80), (82, 80)), L((12, 88), (88, 88)),
        AO(50, 29, 5), H(50, 29)],
    'funnel': [
        C([(18, 24), (82, 24), (58, 54), (58, 76), (42, 84), (42, 54)]),
        S((24, 31), (76, 31)), S((42, 54), (58, 54)),
        N((30, 10), (50, 6), (70, 11)), S((30, 10), (40, 22)), S((50, 6), (50, 22)), S((70, 11), (60, 22)),
        F(ring(50, 94, 6, 10)), H(50, 94), A((50, 84), (50, 88))],
    'kanban': [
        C(rect(10, 14, 34, 86)), C(rect(38, 14, 62, 86)), C(rect(66, 14, 90, 86)),
        F(rect(14, 22, 30, 34)), F(rect(14, 40, 30, 52)), F(rect(14, 58, 30, 70)),
        F(rect(42, 22, 58, 34)), F(rect(42, 40, 58, 52)),
        AC(rect(70, 22, 86, 34)), A((73, 28), (77, 32), (83, 24)), H(77, 32)],
    'calendar_check': calendar([
        S((22, 60), (78, 60)), S((22, 72), (78, 72)),
        A((36, 64), (46, 74), (66, 52)), H(46, 74)]),
    'calendar_note': calendar([
        F(ring(42, 72, 6, 10)), F(ring(62, 68, 6, 10)),
        A((47, 72), (47, 54), (67, 50), (67, 68)), S((47, 60), (67, 56)), H(47, 54)]),
    'lectern': [
        C([(26, 46), (74, 46), (70, 56), (30, 56)]), C([(34, 56), (66, 56), (60, 88), (40, 88)]),
        L((40, 88), (60, 88)), O(40, 30, 8),
        L((60, 46), (64, 32)), H(65, 28),
        A(*arc(65, 28, 10, -60, 40, 4)), A(*arc(65, 28, 20, -60, 40, 5))],
    'folder': [
        C([(12, 28), (36, 28), (42, 36), (88, 36), (88, 84), (12, 84)]),
        P(rect(24, 16, 70, 48)), C(rect(24, 16, 70, 48)), S((30, 24), (62, 24)), S((30, 32), (56, 32)),
        P([(12, 46), (88, 46), (84, 84), (16, 84)]), C([(12, 46), (88, 46), (84, 84), (16, 84)]),
        AC(rect(40, 58, 60, 70)), H(50, 64)],
    'video': [
        C([(14, 32), (60, 32), (64, 36), (64, 68), (60, 72), (14, 72), (10, 68), (10, 36)]),
        C([(64, 44), (88, 30), (88, 74), (64, 60)]),
        O(36, 46, 7), L(*arc(36, 70, 13, -165, -15, 6)),
        F(ring(20, 40, 3, 8)), H(20, 40)],
    'monitor_pulse': [
        C(rect(10, 16, 90, 66)), L((50, 66), (50, 78)), L((32, 80), (68, 80)),
        A((18, 44), (34, 44), (40, 28), (50, 58), (57, 38), (62, 44), (82, 44)), H(40, 28)],
    'book_coin': [
        C([(50, 32), (14, 26), (14, 80), (50, 86)]), C([(50, 32), (86, 26), (86, 80), (50, 86)]),
        S((22, 40), (42, 43)), S((22, 50), (42, 53)), S((22, 60), (42, 63)),
        S((58, 43), (78, 40)), S((58, 53), (78, 50)), S((58, 63), (72, 61)),
        AO(50, 14, 9), H(50, 14)],
    'tower': [
        L((34, 90), (50, 24), (66, 90)), L((40, 66), (60, 66)), L((44, 48), (56, 48)),
        S((38, 80), (60, 66), (40, 66), (56, 48), (44, 48)), L((50, 24), (50, 16)), H(50, 16),
        A(*arc(50, 16, 12, -160, -20, 5)), A(*arc(50, 16, 24, -160, -20, 7)),
        A(*arc(50, 16, 12, 20, 160, 5)[:2]), A(*arc(50, 16, 12, 20, 160, 5)[-2:])],
    'member_card': [
        C(rect(10, 24, 90, 78)), O(32, 44, 9), L(*arc(32, 70, 15, -165, -15, 6)),
        S((52, 38), (80, 38)), S((52, 50), (76, 50)), S((52, 62), (68, 62)),
        AC([(10, 24), (90, 24), (90, 32), (10, 32)]), H(32, 44)],
    'crate': [
        C(rect(22, 44, 78, 88)), L((22, 56), (78, 56)), S((40, 44), (40, 88)), S((60, 44), (60, 88)),
        A((28, 14), (72, 14)), A((65, 8), (72, 14), (65, 20)),
        A((72, 32), (28, 32)), A((35, 26), (28, 32), (35, 38)), H(72, 14)],
    'speaker': [
        C(rect(26, 10, 74, 90)), O(50, 30, 7), C(ring(50, 64, 16, 12)),
        W((50, 64), ring(50, 64, 16, 12)), H(50, 64), N((32, 16), (68, 16), (32, 84), (68, 84))],
    'star': [
        C([(50 + (36 if i % 2 == 0 else 15) * math.cos(math.radians(-90 + 36 * i)),
            52 + (36 if i % 2 == 0 else 15) * math.sin(math.radians(-90 + 36 * i))) for i in range(10)]),
        W((50, 52), [(50 + 15 * math.cos(math.radians(-54 + 72 * i)),
                      52 + 15 * math.sin(math.radians(-54 + 72 * i))) for i in range(5)]),
        H(50, 52),
        A((84, 14), (84, 26)), A((78, 20), (90, 20)), A((16, 74), (16, 84)), A((11, 79), (21, 79))],
    'ticket': [
        C([(12, 30), (88, 30), (88, 42)] + arc(88, 50, 8, -90, -270, 5)[1:-1]
          + [(88, 58), (88, 70), (12, 70), (12, 58)] + arc(12, 50, 8, 90, -90, 5)[1:-1] + [(12, 42)]),
        N(*[(66, y) for y in (36, 44, 52, 60, 66)]),
        S((22, 42), (56, 42)), S((22, 52), (50, 52)), S((22, 60), (44, 60)),
        AC(ring(77, 50, 6, 5)), H(77, 50)],
    'browser': [
        C(rect(8, 16, 92, 84)), L((8, 28), (92, 28)), N((15, 22), (21, 22), (27, 22)),
        F(rect(16, 36, 84, 54)), AC(rect(16, 62, 42, 78)), H(29, 70),
        S((50, 64), (84, 64)), S((50, 71), (78, 71)), S((50, 78), (70, 78))],
    'bunting': bunting(20, 14, 6) + bunting(52, 12, 5, offset=0.5) + [H(50, 27)],
    'heart': [
        C(heart_pts()), W((50, 46), heart_pts()), H(50, 46),
        A((16, 72), (30, 84), (70, 84), (84, 72))],
    'grant': [
        C([(22, 10), (70, 10), (78, 18), (78, 90), (22, 90)]), L((70, 10), (70, 18), (78, 18)),
        S((30, 24), (62, 24)), S((30, 34), (68, 34)), S((30, 44), (64, 44)), S((30, 54), (52, 54)),
        A((56, 76), (52, 92)), A((68, 76), (72, 92)), AO(62, 68, 10), H(62, 68)],
    'stall': [
        L((12, 34), (50, 14), (88, 34)), C(rect(12, 34, 88, 44)),
        A(*sum([arc(x, 44, 6.33, 0, 180, 4) for x in (18.3, 31, 43.7, 56.3, 69, 81.7)], [])),
        L((18, 50), (18, 88)), L((82, 50), (82, 88)), C(rect(12, 66, 88, 72)),
        F(ring(34, 60, 5, 8)), F(ring(48, 59, 6, 8)), F(ring(64, 60, 5, 8)), H(50, 14)],
    'scale': [
        L((50, 22), (50, 84)), L((32, 86), (68, 86)), L((16, 28), (84, 28)), H(50, 22),
        S((16, 28), (8, 54)), S((16, 28), (24, 54)), L(*arc(16, 54, 10, 0, 180, 5)),
        S((84, 28), (76, 54)), S((84, 28), (92, 54)), L(*arc(84, 54, 10, 0, 180, 5)),
        AO(16, 51, 4), F(ring(84, 51, 4, 8))],
    'clipboard': [
        C(rect(20, 14, 80, 90)), P(rect(38, 9, 62, 20)), C(rect(38, 9, 62, 20)),
        C(rect(30, 32, 38, 40)), C(rect(30, 50, 38, 58)), AC(rect(30, 68, 38, 76)),
        A((31, 35), (34, 39), (40, 30)), A((31, 53), (34, 57), (40, 48)),
        S((46, 36), (70, 36)), S((46, 54), (70, 54)), S((46, 72), (64, 72)), H(34, 72)],
    'people': [
        O(22, 48, 8), L(*arc(22, 78, 12, -170, -10, 6)),
        O(78, 48, 8), L(*arc(78, 78, 12, -170, -10, 6)),
        O(50, 36, 9), L(*arc(50, 72, 15, -170, -10, 7)),
        A((61, 61), (64, 44), (64, 22)), H(64, 22)],
    'stage': [
        L((8, 14), (92, 14)), C([(8, 14), (26, 14), (20, 42), (24, 72), (8, 72)]),
        C([(92, 14), (74, 14), (80, 42), (76, 72), (92, 72)]),
        F([(50, 16), (36, 72), (64, 72)]), S((50, 16), (36, 72)), S((50, 16), (64, 72)),
        C([(6, 74), (94, 74), (86, 86), (14, 86)]), H(50, 16), AC(ring(50, 60, 6, 5))],
    'key': [
        C(ring(30, 50, 16, 12)), O(30, 50, 6), W((30, 50), ring(30, 50, 16, 12)),
        L((46, 50), (90, 50)), A((76, 50), (76, 62)), A((86, 50), (86, 64)), H(30, 50)],
    'receipt': [
        C([(24, 8), (76, 8), (76, 84)] + [(76 - 52 * i / 8, 84 + (4 if i % 2 else 0)) for i in range(1, 9)]),
        S((32, 22), (68, 22)), S((32, 32), (60, 32)), S((32, 42), (64, 42)), S((32, 52), (56, 52)),
        A((32, 68), (68, 68)), H(68, 68)],
    'camera': [
        C([(12, 32), (34, 32), (40, 22), (60, 22), (66, 32), (88, 32), (88, 80), (12, 80)]),
        C(ring(50, 56, 16, 12)), W((50, 56), ring(50, 56, 16, 12)), H(50, 56),
        F(ring(80, 14, 9, 10)), A((75, 14), (79, 18), (86, 10)), N((20, 40))],
    'chart': [
        C([(22, 10), (70, 10), (78, 18), (78, 90), (22, 90)]), L((70, 10), (70, 18), (78, 18)),
        AC([(45, 24), (55, 24), (55, 34), (65, 34), (65, 44), (55, 44), (55, 54), (45, 54),
            (45, 44), (35, 44), (35, 34), (45, 34)]), H(50, 39),
        S((32, 66), (68, 66)), S((32, 74), (62, 74)), S((32, 82), (54, 82))],
    'clock': [
        C(ring(50, 50, 36, 12)), A((50, 50), (50, 26)), A((50, 50), (68, 60)), H(50, 50)],
    'compass': [
        S(*ring(50, 50, 38, 16), ring(50, 50, 38, 16)[0]),
        C([(50, 12), (56, 44), (88, 50), (56, 56), (50, 88), (44, 56), (12, 50), (44, 44)]),
        W((50, 50), [(56, 44), (56, 56), (44, 56), (44, 44)]), AC([(50, 12), (56, 44), (44, 44)]),
        H(50, 50)],
    'tag': [
        C([(12, 50), (38, 24), (86, 24), (86, 76), (38, 76)]), O(30, 50, 5),
        A((30, 50), (20, 30), (22, 12)), S((48, 40), (76, 40)), S((48, 50), (72, 50)), S((48, 60), (66, 60)),
        H(30, 50)],
    'target': [
        C(ring(46, 54, 34, 14)), C(ring(46, 54, 22, 12)), C(ring(46, 54, 10, 8)),
        A((46, 54), (84, 16)), A((76, 16), (84, 16), (84, 24)), H(46, 54)],
    'headset': [
        L(*arc(50, 52, 32, 180, 360, 9)), C(rect(12, 50, 24, 72)), C(rect(76, 50, 88, 72)),
        A((18, 72), (24, 84), (42, 87)), H(45, 87)],
    'coins': [
        C(ring(50, 38, 26, 12, ry=9)), W((50, 38), ring(50, 38, 26, 12, ry=9)),
        L(*arc(50, 50, 26, 0, 180, 9, ry=9)), L(*arc(50, 62, 26, 0, 180, 9, ry=9)),
        L(*arc(50, 74, 26, 0, 180, 9, ry=9)), L((24, 38), (24, 74)), L((76, 38), (76, 74)), H(50, 38),
        A((86, 14), (86, 26)), A((80, 20), (92, 20))],
    'map': [
        C([(10, 26), (36, 18), (64, 26), (90, 18), (90, 76), (64, 84), (36, 76), (10, 84)]),
        S((36, 18), (36, 76)), S((64, 26), (64, 84)),
        A((20, 72), (32, 58), (46, 62), (60, 46)),
        P(arc(60, 30, 10, 135, 405, 10) + [(60, 48)]), AC(arc(60, 30, 10, 135, 405, 10) + [(60, 48)]),
        H(60, 30)],
}


# -- drawing -------------------------------------------------------------------

SIZE = 1024
SCALE = 5.2  # grid unit -> px; 100 units = 520 px, inside the 16:9 crop (576 px)


def px(p):
    return (SIZE / 2 + (p[0] - 50) * SCALE, SIZE / 2 + (p[1] - 50) * SCALE)


def pts(points):
    return ' '.join(f'{x:.1f},{y:.1f}' for x, y in map(px, points))


def sky(palette, seed):
    inner, outer, line, node, accent = PALETTES[palette]
    rnd = random.Random(seed)
    out = [f'<defs><radialGradient id="g" cx="50%" cy="46%" r="72%">'
           f'<stop offset="0" stop-color="{inner}"/><stop offset="1" stop-color="{outer}"/>'
           f'</radialGradient></defs><rect width="{SIZE}" height="{SIZE}" fill="url(#g)"/>']
    stars = []
    while len(stars) < 70:
        x, y = rnd.uniform(20, SIZE - 20), rnd.uniform(20, SIZE - 20)
        if abs(x - SIZE / 2) < 270 and abs(y - SIZE / 2) < 270:
            continue  # keep the middle clear for the picture
        stars.append((x, y))
    for a, b in zip(stars[:12], stars[1:13]):
        if math.dist(a, b) < 240:
            out.append(f'<line x1="{a[0]:.0f}" y1="{a[1]:.0f}" x2="{b[0]:.0f}" y2="{b[1]:.0f}" '
                       f'stroke="{node}" stroke-opacity="0.14" stroke-width="2"/>')
    for x, y in stars:
        r = rnd.choice((1.6, 2.2, 2.2, 3.2))
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{line}" '
                   f'opacity="{rnd.uniform(0.25, 0.7):.2f}"/>')
    return out


def picture(name, palette):
    inner, outer, line, node, accent = PALETTES[palette]
    lines, nodes, hubs, top = [], [], [], []
    for kind, p in PICTURES[name]:
        if kind in ('L', 'C', 'A', 'AC'):
            closed = kind in ('C', 'AC')
            colour, width = (line, 6) if kind in ('L', 'C') else (accent, 7)
            tag = 'polygon' if closed else 'polyline'
            (top if kind in ('A', 'AC') else lines).append(
                f'<{tag} points="{pts(p)}" fill="none" stroke="{colour}" stroke-opacity="0.9" '
                f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')
            nodes += p
        elif kind == 'F':
            lines.append(f'<polygon points="{pts(p)}" fill="{accent}" fill-opacity="0.22" '
                         f'stroke="{accent}" stroke-opacity="0.35" stroke-width="3"/>')
        elif kind == 'P':
            lines.append(f'<polygon points="{pts(p)}" fill="{inner}"/>')
        elif kind == 'S':
            lines.append(f'<polyline points="{pts(p)}" fill="none" stroke="{line}" stroke-opacity="0.38" '
                         f'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>')
        elif kind == 'W':
            (hx, hy), rest = px(p[0]), p[1:]
            for q in map(px, rest):
                lines.append(f'<line x1="{hx:.1f}" y1="{hy:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" '
                             f'stroke="{node}" stroke-opacity="0.45" stroke-width="3"/>')
        elif kind in ('O', 'AO'):
            (x, y), r = px(p[0]), p[1][0] * SCALE
            colour, width = (line, 6) if kind == 'O' else (accent, 7)
            (top if kind == 'AO' else lines).append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="none" stroke="{colour}" '
                f'stroke-opacity="0.9" stroke-width="{width}"/>')
        elif kind == 'N':
            nodes += p
        elif kind == 'H':
            hubs += p
    out = lines + top
    seen = set()
    for p in nodes:
        x, y = px(p)
        key = (round(x / 6), round(y / 6))
        if key in seen:
            continue
        seen.add(key)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="15" fill="{node}" opacity="0.12"/>'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" fill="{outer}" stroke="{node}" stroke-width="3.5"/>')
    for p in hubs:
        x, y = px(p)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="44" fill="{accent}" opacity="0.18"/>'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="24" fill="{accent}" opacity="0.30"/>'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="{accent}"/>')
    return out


def cover_png(course, palette, name):
    body = sky(palette, course) + picture(name, palette)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" '
           f'viewBox="0 0 {SIZE} {SIZE}">{"".join(body)}</svg>')
    raw = subprocess.run(['rsvg-convert', '-w', str(SIZE), '-h', str(SIZE)],
                         input=svg.encode(), capture_output=True, check=True).stdout
    img = Image.open(BytesIO(raw)).convert('RGB')
    buf = BytesIO()
    img.save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def target(repo, module, course):
    return ROOT / repo / module / 'static' / 'img' / f'cover_{course.removeprefix("channel_")}.png'


def main(argv):
    only = [a for a in argv if not a.startswith('--') and not a.endswith('.png')]
    made = []
    for repo, module, course, palette, name in COURSES:
        if only and course not in only and module not in only:
            continue
        path = target(repo, module, course)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(cover_png(course, palette, name))
        made.append(path)
        print(f'{path.relative_to(ROOT)}  ({path.stat().st_size // 1024} KB)')
    if '--sheet' in argv and made:
        cols, thumb = 6, 256
        rows = -(-len(made) // cols)
        sheet = Image.new('RGB', (cols * thumb, rows * thumb), 'white')
        for i, path in enumerate(made):
            sheet.paste(Image.open(path).resize((thumb, thumb)), ((i % cols) * thumb, (i // cols) * thumb))
        out = Path(argv[argv.index('--sheet') + 1]) if argv.index('--sheet') + 1 < len(argv) else Path('course_covers_sheet.png')
        sheet.save(out)
        print(out)


if __name__ == '__main__':
    main(sys.argv[1:])
