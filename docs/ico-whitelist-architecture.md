# ICO Whitelist Architecture

Status date: 2026-06-16

## Implemented Slice

- Public submit endpoint:
  - `POST /api/v1/public/ico/whitelist`
  - Compatibility alias: `POST /api/public/ico/whitelist`
- Public confirmation endpoint:
  - `GET /api/v1/public/ico/whitelist/confirm?token=...`
  - `POST /api/v1/public/ico/whitelist/confirm`
- Frontend form posts to the backend and no longer uses `mailto:`.
- Privacy acceptance is required.
- Marketing consent is separate, optional, and unchecked by default.
- Whitelist applicants are stored separately from platform users.

## Tables

- `ico_whitelist_applications`
  - Stores applicant email, normalized email, application status, consent snapshot fields, token hash, confirmation expiry, review fields, unsubscribe/withdrawal timestamps, and limited source metadata.
- `ico_consent_events`
  - Append-only consent evidence for privacy acceptance and optional marketing consent.
- `ico_email_outbox`
  - Transactional outbox stub for whitelist confirmation emails.

## Security Choices

- Raw confirmation tokens are not stored.
- The public submit response is generic and does not reveal whether an applicant already exists.
- Email fingerprinting uses SHA-256 of the normalized email for limited metadata.
- Honeypot field is accepted as `company_website`; populated honeypot submissions receive a generic success response and are not persisted.
- Marketing confirmation is only activated when marketing consent was explicitly selected.

## Current Limitations

- Confirmation emails are processed by a basic backend outbox worker when Mailgun is configured.
- Unsubscribe and withdrawal endpoints are implemented with tokenized public result pages.
- Basic admin list/outbox processing is implemented; full review/export/bulk workflow is not.
- IP hashing/retention policy remains documented but not implemented.
