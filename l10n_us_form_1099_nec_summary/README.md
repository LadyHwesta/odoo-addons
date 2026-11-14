# US Form 1099-NEC Summary

Year-end 1099-NEC figures for contractors, on top of OCA's
`l10n_us_form_1099` (ported to 19.0 in this repo).

## Use

1. On each contractor's contact (Sales & Purchase tab): tick **Is a 1099?**,
   type **NEC**, and fill in their taxpayer ID (from their Form W-9) and
   address.
2. On any journal that pays through a card network or payment app, tick
   **Payments Reported on 1099-K**: those payments are left out.
3. Accounting > Reporting > **1099-NEC Summary**: choose the year, click
   **Calculate**. Contractors at or above the threshold show **1099-NEC
   Needed**; fix any flagged issues.
4. Enter the figures in the IRS IRIS Taxpayer Portal (or its CSV template),
   and **Print Recipient Statements** to send each contractor their copy by
   31 January.

## Rules it uses

- Sent, completed payments only (`paid` or `in_process`), dated in the year.
- Threshold: $600 for 2025 and earlier, $2,000 from 2026 (One Big Beautiful
  Bill Act). From 2027 it is indexed for inflation: set the year's figure
  as system parameter `l10n_us_1099_nec.threshold.<year>`.
- The recipient's TIN shows only its last four digits on their statement.

## Tests

`tests/test_summary.py` (6): payment filtering, thresholds by year,
issue flags, the statement's content and TIN masking, nothing to print
below the threshold.
