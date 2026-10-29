# Design and DSA notes

## Request path

A server-rendered Flask interface handles requests without JavaScript. Flask validates form input and CSRF tokens. SQLite stores programs, counters, requests, daily sequences, events, and announcements. The app initializes the schema on first launch and uses parameterized SQL.

Programs are represented by a normalized `programs` table with foreign keys from requests and counters. This provides separate categories without duplicating an entire physical requests table for each program. Daily sequence numbers have a `(day, program)` primary key; requests enforce a unique `(day, ticket)` pair. Confirmation links use independent random UUID tokens. Know the token to view a receipt; names/contact details are not displayed there.

## Data structures actually used

| Structure | Implementation | Application | Complexity |
| --- | --- | --- | --- |
| FIFO queue | `RequestQueue.first()` and `remove()` | Calls the oldest waiting request eligible for a counter's program | O(n) to find eligible program; O(1) to remove known ID |
| Doubly linked list | `Node.previous`, `Node.next`, head and tail | Dequeue/removal and staff previous/next navigation | O(1) append, indexed removal, and neighbor lookup |
| Hash table | Python `dict` in `RequestQueue.index` | Maps request IDs to list nodes; prevents duplicate nodes | Average O(1) lookup |
| Array/list | `RequestQueue.to_list()` | Builds ordered current/upcoming public display entries | O(n) traversal, O(n) space |

`serbisyoq/structures.py` contains the standalone implementation. `service.py` reconstructs a queue from ordered waiting SQL records inside each operation; a process-local linked list must not become stale when another worker changes SQLite. Building the queue costs O(n) time and space after the SQL read. The complete call operation is therefore **not** constant time. Database lookup for staff details uses the SQLite primary-key index, not a claim that every SQL operation uses our dictionary.

All waiting programs share arrival order; each dedicated counter finds the first eligible program. Earlier applicants in another program do not block that counter. Public upcoming entries are an arrival-order list across programs, not a promise that all counters finish in that order.

## Lifecycle

```text
Submitted → Waiting → Called → For Assessment → Completed
                  ↘       ↘                 ↘
                    Skipped ←────────────────
                       ↓
              Waiting (rejoin at tail today)

Waiting / Skipped → Cancelled
Called may also go directly to Completed.
```

Only documented transitions are allowed by the service, even if a stale browser submits another action. Completed and Cancelled requests are terminal. Referred is an outcome of a Completed transaction, rather than leaving a counter permanently occupied by a referred case. Past requests remain available to staff in date-filtered records and reporting; they are not silently deleted at midnight. Calls only draw from today's queue. A counter with an unresolved older active transaction must be completed or skipped before serving another applicant.

## Concurrency and persistence

SQLite is the source of truth. `BEGIN IMMEDIATE` serializes writes for number allocation, calls, and transitions. Sequence allocation, request insertion, and activity events commit together. A partial unique index prevents two Called/For Assessment transactions occupying the same counter, even if another writer bypasses the service. On failure, operations roll back. Connections enable foreign keys and a 15-second busy timeout. State survives restarts; sessions need a persistent secret key to survive them.

## Reporting definitions

- Selected range includes all statuses by request registration day.
- Wait: most recent `queued_at` to `called_at`, for requests with a recorded call. Rejoining resets queue time and clears the previous call; a later call measures the new wait. Skipped/cancelled records with a past call may still contribute to measured waits.
- Service: latest recorded call to completion, for completed requests.
- Peak: hour with the most arrivals across selected registration days; ties choose the earliest hour.
- Zero measurements display a dash, rather than a misleading zero-minute average.
- CSV exports day, ticket, program, status, outcome, and timestamps, not applicant identity/contact details. Cells are protected against spreadsheet formula interpretation.

The report supports operational analysis. It does not implement a government-prescribed DOLE report template.
