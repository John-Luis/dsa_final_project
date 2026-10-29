# Prototype review walkthrough

Start the app using the README. Use fictional details. To begin with populated counters, run `seed-demo` before adding any requests. An existing nonempty database is left intact.

1. **Services:** inspect Job Placement, SPES, and Employer Registration. Each has its own requirements, code, and current waiting count. Scan the portal QR from a phone using a reachable host address.
2. **Intake:** choose Job Placement, review requirements, and submit fictional details with the two confirmations checked. Invalid details should show an error without creating a ticket.
3. **Receipt:** save the private confirmation URL. Verify the category number, date, status, and number of applicants ahead. Refresh it after staff actions.
4. **Staff:** sign in with `peso-demo` if no custom password is configured. Inspect request filters, search, and applicant details. Previous/next links follow the waiting linked list.
5. **Counter:** a seeded counter already has an active request. Open it, assess it, select an outcome, and complete it. Call next. Verify it is the oldest waiting applicant for that counter's program, rather than the most recently submitted applicant.
6. **Skip/rejoin:** skip a waiting/called applicant. Rejoin them from their detail page. They should retain their ticket but move behind other waiting applicants. Calling again should honor the updated order.
7. **Public screen:** verify the counter/number changes and upcoming list. Publish an announcement from the dashboard; wait up to 5 seconds or refresh the monitor. Applicant names/contact details should never appear there.
8. **Reports:** choose a date range; check program volumes, waiting/service averages, and hourly demand. Download CSV and inspect completed outcomes. A range without records should show an empty report.
9. **Mobile:** inspect intake, dashboard, public monitor, and reports at a narrow viewport. Tables/charts scroll within their containers.
10. **History:** inspect `git log --oneline --reverse`. Each substantial component has its own local commit. The user has authorized pushing the feature commits to GitHub.

## What is deliberately a prototype

The requirements list is illustrative, staff access is a shared demonstration login, and analytics are supporting summaries rather than an official DOLE form. The new requested additions include SMTP confirmations, staff announcement uploads, a live staff table, and expanded report charts. SMTP is optional for local preview mode; real mail needs private configuration. A real LGU deployment needs additional identity, security, operational, and policy work described in the README.


## Added-feature review

- Submit a new request, then open Email log → View message. With no SMTP, the message must explicitly say Preview, not Sent. Configure SMTP privately and restart to test an actual mailbox; retry a preview/failed message and inspect delivery state.
- Open the TV monitor in a second tab. Call the next applicant in the dashboard; verify now-serving and per-counter up-next update within 5 seconds while the clock ticks each second.
- Upload an image and muted video from TV media. Verify upload order, pause/resume, previous/next, video completion, and display duration. Queue polling must not restart playback. Remove custom media to restore the two built-in slides.
- Leave an announcement draft unsaved, then submit another applicant in a separate tab. Verify the live Number/Name/Concern/Time table updates without clearing the draft or active filters.
- Inspect the Reports line chart, program bars, status pie, and hourly bars. Select an empty range and verify no fabricated slices or averages appear. Expand View trend data to compare chart values with the underlying table.
