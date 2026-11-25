# eLearning: Your Bank in Odoo

One course for whoever keeps the books, built into Odoo's eLearning app on
install (members only, by invitation, for invoicing users), with a quiz and
screenshots from a made-up sole proprietor, Juniper Hollow Design, and its
second business name, Juniper Hollow Photo, banking at Cedar Valley Credit
Union:

- **How Odoo sees your bank**: the statement is the truth; Bank Suspense,
  Outstanding Receipts and Payments, and Liquidity Transfer.
- **Set up from day one**: one bank journal per account (savings that tops
  up checking included), the bank's CSV layout, automatic rules, the owner's
  own money, business names as branches.
- **When the statement arrives**: import, match line by line, prove the
  books match the bank, and what to check when they don't.

Uses OCA's `account_statement_import_sheet_file` and `account_reconcile_oca`.

The data file is built by `tools/build_course_data.py`: edit the lessons
there and rerun it. Screenshots in `static/img` are taken by
`tools/shoot.py` from the sample business that `tools/sample_business.py`
builds on a throwaway database (sample statements in `tools/sample/`).
