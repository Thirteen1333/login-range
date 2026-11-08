# login-range

A self-contained attack range for **login pages** — 12 vulnerability classes,
each with a working proof-of-concept. Run it locally, break it, then read why
each one exists.

```
12 / 12 PoCs passing
```

## Why

Most login pages fail the same 12 ways. This range reproduces every one of them
so you can build the reflex: look at any login form and know what to test first.

## Quick start

```bash
python3 server.py --port 9100 &
sleep 1
python3 exploit_all.py
```

## The 12 vulnerabilities

| # | Class | Attack | Result |
|---|---|---|---|
| V1 | Username enumeration | Different error strings | ✅ |
| V2 | **Timing side-channel** | +20 ms per matched char, recover byte by byte | ✅ recovers `Adm1n!2024` |
| V3 | SQL injection | `' OR '1'='1' -- ` | ✅ admin |
| V4 | No lockout | Wordlist | ✅ `alice:Summer2024!` |
| V5 | Forgeable remember-me | Plain base64 | ✅ |
| V6 | Predictable reset token | `rt-<user>-<4 digits>` | ✅ |
| V7 | Session fixation | Server never rotates SID | ✅ |
| V8 | 2FA bypass | Universal code `000000` | ✅ |
| V9 | Privilege escalation | No server-side check | ✅ alice → admin |
| V10 | Log exposure | Unauthenticated read | ✅ |
| V11 | No CSRF | Cross-site transfer | ✅ |
| V12 | Stack trace leak | Full traceback + paths | ✅ |

## The fix for each

| # | Correct control |
|---|---|
| V1 | Uniform error message **and** uniform response time |
| V2 | `hmac.compare_digest` — constant time |
| V3 | Parameterized queries |
| V4 | Exponential backoff + account lockout + IP rate limit |
| V5 | Server-signed token; never store plaintext |
| V6 | 32 random bytes, single use, short TTL |
| V7 | Regenerate session ID on login |
| V8 | Server-side TOTP, no universal codes |
| V9 | Authorize on the server, never trust the client |
| V10 | Auth + redaction on log endpoints |
| V11 | CSRF token + `SameSite` |
| V12 | Disable debug in production, uniform error page |

## Notes

Four bugs found and fixed while building the exploit suite: comparing status
codes instead of bodies (V1), a 30 ms threshold above the 20 ms signal (V2),
POST against a GET-only route (V7), and a read-before-write ordering issue
(V10/V11). All four are documented in the commit history.

## Scope

Local test range. `127.0.0.1` only. Point it at nothing but itself.

MIT.
