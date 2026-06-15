# Mailgun Integration Notes

Status date: 2026-06-16

## Existing Repository State

- Backend already has Mailgun configuration routes under `/api/v1/mailgun`.
- Mailgun secrets are stored through the existing external API credential service, not returned to the frontend.
- Existing Mailgun send behavior is limited to password-rotation/onboarding notices.

## ICO Slice Added

- Whitelist submission writes an `ico_email_outbox` row in the same database transaction as the application and consent events.
- Database persistence does not depend on a synchronous Mailgun response.
- The outbox includes an idempotency key, email type, template key, recipient fingerprint, status, attempts, and provider message ID fields.
- A basic backend outbox worker processes pending ICO confirmation email jobs when Mailgun is configured.
- A verified ICO Mailgun webhook endpoint records delivery events and creates local suppressions for complaint, unsubscribe, and failure events.

## Required Next Work

- Add detailed webhook event history to the admin UI.
- Add admin test-email action with safe error messages and audit logging.
- Add focused ICO marketing update drafting/sending workflow for confirmed, consented, non-suppressed recipients only.

## Production Warning

Do not send ICO marketing emails until explicit marketing consent and confirmation are both recorded. Whitelist confirmation email is transactional and must not be used to bypass marketing consent.
