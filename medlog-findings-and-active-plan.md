# MedLog — Findings & Active (Aggressive) Test Plan

> Companion to `medlog-pentest-context.md`. This file is the working pentest
> dossier for the ACTIVE phase. New local Claude Code session on branch `V3.7`:
> "Read medlog-findings-and-active-plan.md and let's continue the active testing."

---

## 0. Authorization & Rules of Engagement (unchanged)
- **Owner consent:** DerHanzie gave explicit written consent to penetration test
  (chat screenshot on file). Target is his own app, **test data only**.
- **Phase:** moving from passive recon -> ACTIVE/aggressive testing.
- **Still in force:**
  - Destructive / availability-impacting / persistent-artifact actions => **ASK FIRST**.
    (DoS, load testing, dropping/truncating data, leaving planted rows behind.)
  - Account creation and writes ARE in scope for the active phase, but clean up
    after (delete test accounts/rows you create) and keep volume minimal.
  - If a finding can be proven read-only, prefer that over a mutation.

## 1. Target / Stack (from early-version black-box; RE-VERIFY on V3.7)
- Front: `https://medlog.worldofhanz.cc` — Vite + React 18 + React Router v6,
  Radix/shadcn UI, PWA + service worker, PDFObject. Scaffolded by Lovable.
- Edge: **Caddy** (auto-HTTPS, HTTP/3).
- Backend: self-hosted **Supabase** — API gateway `https://db.worldofhanz.cc`
  (PostgREST 12.2.11, GoTrue auth). Postgres behind it.

## 2. Credentials / Keys
- **Supabase anon key (PUBLIC — ships in browser bundle):**
  - Decoded claims observed: `{"role":"anon","iss":"supabase","iat":1775080800,"exp":1932847...}`
  - Raw token: `PASTE_ANON_JWT_HERE`  ← re-extract with:
    `grep -aoE 'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+' app.js | sort -u`
  - Use in requests as: `-H "apikey: $ANON" -H "Authorization: Bearer $ANON"`
- **service_role key:** NOT seen client-side (good). Verify still absent on V3.7.
  If it ever appears in the bundle/.env shipped to client => CRITICAL (bypasses RLS).

## 3. Schema (from PostgREST OpenAPI root — anon-readable)
Endpoint: `GET https://db.worldofhanz.cc/rest/v1/`  (apikey header required)
Tables + known columns:
- `profiles`            : id, display_name, created_at
- `medication_profiles` : id, user_id, encrypted_payload, created_at, updated_at, deleted_at
- `medication_events`   : (columns TBD — enumerate from OpenAPI)
- `metric_events`       : (columns TBD)
- `user_keys`           : (columns TBD — KEY MATERIAL; highest-value table)

Design note: sensitive data is an `encrypted_payload` blob (app-level encryption),
not plaintext columns. `user_keys` holds key material. STRENGTH depends entirely on
whether crypto is real and keys are user-password-wrapped (see §6).

## 4. Findings So Far
| # | Finding | Sev | Status |
|---|---------|-----|--------|
| F1 | RLS enforced for anon on `profiles` & `medication_profiles` (SELECT => `[]`) | — | ✅ boundary holds (anon read) |
| F2 | PostgREST OpenAPI introspection readable by anon (full schema disclosure) | Low | Open / likely accept |
| F3 | Anon read of `user_keys`/`medication_events`/`metric_events` | ? | NOT YET TESTED |

## 5. ACTIVE TEST PLAN — priority order

### A. Finish anon-read sweep (read-only, do first)
```
for t in user_keys medication_events metric_events; do
  echo "== $t =="; curl -sS "https://db.worldofhanz.cc/rest/v1/$t?select=*&limit=5" \
    -H "apikey: $ANON" -H "Authorization: Bearer $ANON"; echo; done
```
Expect `[]`. Rows back, esp. from `user_keys`, = high/critical.

### B. Authenticated horizontal-access / IDOR  (THE headline test) — needs 2 test accounts
Goal: prove user A cannot read/write user B's rows. RLS "on" is meaningless if the
policy is `USING (true)` or `USING (auth.uid() IS NOT NULL)` instead of
`USING (auth.uid() = user_id)`.
1. Sign up two throwaway users via GoTrue:
   `curl -sS -X POST "https://db.worldofhanz.cc/auth/v1/signup" -H "apikey: $ANON" \
     -H "Content-Type: application/json" -d '{"email":"pentestA@example.com","password":"..."}'`
   (capture access_token for A and B; note if email confirmation is required)
2. As user A, create a medication_profile (write test).
3. As user B's token, attempt to SELECT / PATCH / DELETE user A's row by id and by
   filtering user_id. Any success = broken RLS (IDOR). Test EVERY table.
4. `user_keys`: as B, try to read A's key row. Success = encryption model defeated.
- Cleanup: delete created rows/users after.

### C. Write-policy / mass-assignment (mutations — minimal, cleanup, ask if unsure)
- Anon INSERT into each table (should fail).
- Authed INSERT/PATCH setting `user_id` to someone else (mass-assignment / row spoofing).
- PATCH columns you shouldn't own (e.g., flip another user's `deleted_at`).

### D. PostgREST / Supabase-specific
- `GET /rest/v1/rpc/` style: enumerate exposed RPCs; look for SECURITY DEFINER
  functions that bypass RLS or leak cross-user data.
- Embedded joins: `?select=*,other_table(*)` to pull related rows past RLS.
- Supabase Storage: check for public buckets / object listing if storage is used.
- Count leakage: `Prefer: count=exact` to learn row counts even when rows are hidden.

### E. Auth / GoTrue
- Is signup open? Email confirmation enforced or bypassable?
- Password reset flow abuse; rate limiting on login/signup.
- JWT tampering: `alg:none`, role swap anon->authenticated->service_role (should fail
  unless the JWT secret is weak/leaked). Check token expiry/refresh handling.

### F. Source review on V3.7 (authoritative — do alongside)
- `supabase/migrations/*.sql`: confirm `ENABLE ROW LEVEL SECURITY` + per-table
  policies are `auth.uid() = user_id`. This validates/explains B.
- Encryption module: `crypto.subtle` + PBKDF2/Argon2 + AES-GCM, key derived from
  user secret, never stored server-side recoverable. Confirm `encrypted_payload`
  isn't `btoa(JSON.stringify(...))`.
- `.env*` / client config: no service_role key client-side.
- `package.json` + lockfile: dependency CVEs.
- Optional: scan git history for committed-then-deleted secrets.

## 6. Severity-calibration reminders (avoid scanner-grade false positives)
- "Anon key in bundle" = BY DESIGN public. NOT a finding on its own.
- Schema disclosure (F2) = Low; note and likely accept.
- The REAL severity drivers: (a) IDOR / permissive RLS, (b) `user_keys` readable by
  others, (c) service_role key client-side, (d) fake/keyless "encryption".
