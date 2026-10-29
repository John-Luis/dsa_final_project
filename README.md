# SerbisyoQ

A working **Python / Flask / SQLite** prototype for a DSA final project: a PESO queue management portal for jobseekers, students, employers, and staff. Built from the revised **LGU SerbisyoQ.pdf** proposal with an original interface.

## Windows quick start

After cloning or downloading this repository, double-click **START-WINDOWS.cmd** in the project folder. It creates a Windows virtual environment, installs all dependencies (including timezone data), and starts the server on port 5000. Keep its terminal open. The demo staff password is `peso-demo` unless privately overridden.

For another computer or a TV on the same LAN, run Flask with `--host 0.0.0.0` and use your computer’s LAN address. Configure a private staff password before sharing access.

## Run it

Requires Python 3.11+ with `venv` and `pip`. The pinned `tzdata` dependency supplies Philippine time-zone data on Windows, where the system IANA database is usually absent. No Node.js, Google credentials, or external database is needed.

```sh
cd /workspace/dsa_final_project
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# Optional: add fictional records to an EMPTY database. Existing records are preserved.
.venv/bin/python -m flask --app serbisyoq.app seed-demo
.venv/bin/python -m flask --app serbisyoq.app run --host 0.0.0.0 --port 5000
```

On another machine, replace the working directory with your checkout path. On Windows, use `.venv\Scripts\python` in place of `.venv/bin/python`.

Open port 5000 in your development browser. The landing page links to all screens:

| Screen | Path | Purpose |
| --- | --- | --- |
| Service portal | `/` | Program selection, waiting counts, and a real portal QR code |
| Request form | `/request?program=P` | Requirements, validated applicant details, and consent |
| Confirmation | `/ticket/<private-token>` | Ticket, status, counter, and applicants ahead |
| Public monitor | `/monitor` | Multimedia TV display, live Philippine clock, per-counter current/up-next; queue polls every 5 seconds |
| Staff sign-in | `/staff/login` | Demo password: **`peso-demo`** |
| Staff dashboard | `/staff` | Sidebar navigation, live Number/Name/Concern/Time table, counters, and announcements |
| Reports | `/staff/reports` | Date-range line/bar/pie charts and downloadable CSV |
| TV media | `/staff/media` | Upload/remove public image and video announcements |
| Email log | `/staff/email` | Delivery states, private message previews, and retries |

The SQLite database is initialized automatically in ignored `instance/serbisyoq.sqlite`. It persists across process restarts. Do not commit it; it may contain applicant data. A seeded demo has fictional completed, called, and waiting transactions. The seed command refuses to change a nonempty database.

The QR code points to the URL used to access the portal. To scan it from a phone, visit the portal using a hostname/IP reachable from that phone first; a loopback address belongs to the phone itself.

## Features

- Job Placement (`P`), SPES Application (`S`), Employer Registration (`E`).
- Daily per-program numbers (`P-001`, `S-001`, `E-001`) allocated atomically. A ticket's identity includes its day; its private confirmation link remains unique.
- Dedicated counters: 1 for Job Placement, 2 for SPES, 3 for Employers. Each calls the oldest eligible waiting applicant for today.
- Staff can assess, skip, requeue, cancel waiting/skipped entries, and complete requests with an outcome: Served, Referred, or Requirements incomplete.
- Skipping frees the counter; rejoining places today's applicant at the end. Past-day skipped requests require a new submission to join another day's queue.
- Transaction audit history and previous/next navigation through the waiting list.
- Search by name or ticket; filter records by day, program, and status.
- Public monitor excludes applicant names, contact details, concerns, and private tokens.
- Reports show volumes, completion counts, average wait/service durations, demand by program, and arrivals by hour in Philippine Standard Time. Reports default to the latest seven days. Python generates line, bar, and pie charts from the selected records, with text legends and a trend-data table. Exports exclude personal contact data.
- A confirmation email is prepared automatically after form submission. SMTP delivery is configurable; without SMTP, a local preview is saved and clearly labeled as unsent.
- The public monitor cycles images and muted videos while updating counter numbers independently. Staff can upload PNG/JPEG/GIF/WebP images or MP4/WebM videos (25 MB maximum each, 5–120-second display limit). Built-in PESO slides display when the custom playlist is empty.
- Staff queue records and counters poll every 5 seconds without clearing filters or unsaved announcement text. Disconnected screens display a stale-data notice and attempt to reconnect.

## DSA implementation

See [the design notes](docs/architecture.md) for complexity, database relationships, status transitions, and concurrency behavior. The structures are actual Python implementations, not just labels in the UI.

## Test

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The standard-library suite uses disposable databases. It covers linked-list integrity, concurrent ticket allocation and counter calls, FIFO eligibility, status transitions, validation, authentication/CSRF, public privacy, reporting, restart persistence, and repeatable seeding.

Optional browser checks use Playwright and a disposable seeded database; they do not alter the app's database:

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python tests/browser_smoke.py
```

To use an existing Chromium, set `SERBISYOQ_CHROMIUM` to its executable path. The browser walkthrough submits an applicant, verifies the email preview, checks cross-tab counter updates and the clock, preserves an unsaved staff draft, plays a real video across queue polling, advances to an image, checks report charts/CSV, and checks seven mobile layouts. It uses disposable databases and media directories.

## Confirmation email setup

SMTP is the mail-sending service used by an email provider such as Gmail, Outlook, or Brevo. Without one, the app remains usable in **local preview mode**; it does not claim an email was delivered.

1. Copy `.env.example` to `.env` in the project root.
2. Fill in your provider’s `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_FROM`, `SMTP_USERNAME`, and `SMTP_PASSWORD` privately. For Gmail, follow Google’s current App Password requirements; do not use your normal account password. Provider policies may require a verified sender.
3. Set `SERBISYOQ_PUBLIC_URL` to the portal’s real reachable base address to include private status and public monitor links in messages. Links are omitted if it is unset; the email still includes the ticket and service date.
4. Restart Flask or the Windows launcher. Flask loads `.env` through python-dotenv. Direct calls to `create_app()` use the process environment/config instead.
5. Submit a fictional test request to a mailbox you control, then inspect **Email log**. `Sent` means SMTP accepted the message, not guaranteed inbox delivery. Check spam and provider delivery logs if needed.

Use `SMTP_SECURITY=starttls` for explicit TLS (commonly port 587), or `ssl` for implicit TLS (commonly 465). TLS certificate verification stays enabled. Plaintext SMTP is not supported. Default delivery timeout is 10 seconds; this prototype sends synchronously after saving the ticket. A mail failure does not remove the applicant’s ticket. Failed/preview messages can be retried by staff after correcting configuration. A previously Sent message cannot be sent again through the retry button.

Private email previews are available in the staff email log and as ignored `instance/mail-preview/*.eml` files. The SQLite outbox records delivery status and attempts. A process terminated during delivery may leave a message marked Sending: inspect the provider before any manual recovery to avoid sending a duplicate. Restarting the app does not automatically retry messages.

Never commit `.env`, the SQLite database, SMTP credentials, or uploaded media. If the app sends from another computer, configure its SMTP settings there too.

## Demo boundaries

This is a classroom prototype, not a deployed LGU service. Requirements and eligibility text are illustrative; no official DOLE form or government integration is supplied. Queue handling, persistence, reporting, and SVG chart generation run in Python. Small local JavaScript files handle browser polling, the clock, and media playback; there is no Node build or CDN dependency. The new confirmation feature uses SMTP rather than Google Forms/Sheets/Apps Script. Applicant document uploads are not included; staff media uploads are for public announcements only.

The shared demo login is intentionally visible when no custom password is configured. Use fictional data only. For a private demonstration, set `SERBISYOQ_STAFF_PASSWORD` and `SERBISYOQ_SECRET_KEY` securely before starting. Passwords are hashed in memory; personal details are stored in local SQLite, which is not encrypted. A real deployment would need individual staff accounts, rate limiting, HTTPS, secure cookies, access policies, data-retention controls, database backups, and a production WSGI server. Flask's development server is for development.

If no secret key is supplied, an ephemeral key is generated at startup; sessions expire on restart. Multiple workers require the same configured secret key.

## Git history and updates

Substantial features are committed separately: queue/data structures, intake, staff operations, monitor, reports, confirmations, media management, live staff views, and charts. Inspect them with `git log --oneline --reverse`.

The user has authorized pushing this implementation to GitHub. Runtime data remains local: an existing SQLite database is preserved and gains the new email/media tables automatically on startup. Back up `instance/` before updates, retain `.env` locally, and rerun dependency installation after pulling. Confirmations are created for new submissions; older requests are not emailed retroactively.
