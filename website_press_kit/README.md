# Website Press Kit

A press kit page (`/press-kit`) for performers and artists: what promoters,
venues and journalists ask for, on one page of your website. Built for DJ
EmBass (djembass.com), 2026-11-16.

## Set up

**Website > Site > Press Kit**: one press kit per website.

- **Act name**, **tagline**, **genres** (separated by commas), **based in**,
  booking **email** and **phone**.
- **Bio** tab: a short bio promoters can copy.
- **Photos** tab: the first photo is the big one at the top. Upload full
  size. The page shows a 1024 px copy, and **Download** gives the original
  with your caption and credit. Press photos skip Odoo's usual 1920 px
  shrink on upload, so they print well.
- **Links** tab: mixes, videos, music, socials, press (web addresses only).
- **Technical rider**: a file to download.
- **Book Button Link**: `/book` by default (Gig Bookings' request form).
  Leave it empty for no button.
- **Show Upcoming Events**: published events on this website still to come,
  including appearances at other people's events (Event Appearances).

Tick **Published**, then add `/press-kit` to the website menu. An
unpublished kit, or a website without one, answers 404.

## Look

The page uses plain Bootstrap and the theme's color classes (`o_cc`), so it
takes each website's own colors and fonts.
