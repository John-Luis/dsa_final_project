# SerbisyoQ

A working **Python / Flask / SQLite** prototype for a DSA final project: a PESO queue management portal for jobseekers, students, employers, and staff. Built from the revised **LGU SerbisyoQ.pdf** proposal with an original interface.

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
| Public monitor | `/monitor` | Current tickets, upcoming applicants, announcements; refreshes every 10 seconds |
| Staff sign-in | `/staff/login` | Demo password: **`peso-demo`** |
| Staff dashboard | `/staff` | Counter calls, filters, applicant details, and announcements |
| Reports | `/staff/reports` | Date-range analytics and downloadable CSV |

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
- Reports show volumes, completion counts, average wait/service durations, demand by program, and arrivals by hour in Philippine Standard Time. Exports exclude personal contact data.

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

To use an existing Chromium, set `SERBISYOQ_CHROMIUM` to its executable path. The browser walkthrough submits an applicant, signs in, assesses/completes a transaction, calls the next applicant, downloads a CSV, and checks five mobile layouts.

## Demo boundaries

This is a classroom prototype, not a deployed LGU service. Requirements and eligibility text are illustrative; no official DOLE form or government integration is supplied. The revised proposal uses on-screen confirmation, so no emails, Google Forms, Sheets, or Apps Script integrations are included. There are no attachment uploads in this revised scope.

The shared demo login is intentionally visible when no custom password is configured. Use fictional data only. For a private demonstration, set `SERBISYOQ_STAFF_PASSWORD` and `SERBISYOQ_SECRET_KEY` securely before starting. Passwords are hashed in memory; personal details are stored in local SQLite, which is not encrypted. A real deployment would need individual staff accounts, rate limiting, HTTPS, secure cookies, access policies, data-retention controls, database backups, and a production WSGI server. Flask's development server is for development.

If no secret key is supplied, an ephemeral key is generated at startup; sessions expire on restart. Multiple workers require the same configured secret key.

## Review before any push

All implementation commits are local on **`work`**. Nothing has been pushed or merged into `main`. The first scaffold commit used Vite before the replacement PDF was read; the next commit replaces it completely with the required Python stack. No Node tooling is needed by the final project.

Use [the review walkthrough](docs/review-guide.md) to evaluate the prototype, and `git log --oneline --reverse` to inspect feature commits. Push or merge only after you have reviewed and explicitly approved it.
