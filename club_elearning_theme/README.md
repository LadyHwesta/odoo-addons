# eLearning: Shared Course Styling

A pure-assets module - no models, no data, nothing visible if you
install it on its own. It ships the CSS (`static/src/scss/course_content.scss`,
loaded via `web.assets_frontend`, scoped under `.oe-course-content`)
that every `club_elearning_*` course in this repo uses for its callout
boxes, numbered step lists, state badges, and diagram styling - one
shared stylesheet instead of three copies of the same file.

Every other eLearning pack in this repo depends on this module; you
won't normally install it by itself.
