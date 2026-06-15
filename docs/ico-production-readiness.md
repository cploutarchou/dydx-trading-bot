# ICO Production Readiness

Status date: 2026-06-16

This implementation is not production ready.

## Approval Checklist

- [ ] Business approval
- [ ] Legal approval
- [ ] Tokenomics approval
- [ ] Technical approval
- [ ] Final legal entity/controller details
- [ ] Smart-contract address and explorer link
- [ ] Smart-contract audit status
- [ ] KYC/AML provider and policy
- [ ] Restricted jurisdictions
- [ ] Token price
- [ ] Accepted currencies
- [ ] Final allocation table totaling 100%
- [ ] Vesting and unlock schedule
- [ ] Participation terms
- [ ] Privacy Notice
- [ ] Risk disclosure
- [ ] Consent version approval
- [ ] Mailgun domain verification
- [ ] SPF
- [ ] DKIM
- [ ] DMARC
- [x] Basic transactional confirmation email template
- [x] Outbox worker
- [x] Mailgun webhook signature verification endpoint
- [x] Basic suppression handling for webhook complaints, unsubscribe, and failures
- [ ] Database backup
- [ ] Monitoring
- [ ] Alerting
- [ ] Rate limiting tuned for public launch
- [ ] Production smoke test

## Implemented

- Dedicated whitelist persistence tables.
- Consent event history table.
- Email outbox table.
- Public whitelist submission API.
- Public confirmation API and frontend result page.
- Public unsubscribe and withdrawal APIs and frontend result pages.
- Basic Mailgun outbox worker.
- Basic Mailgun webhook verification and suppression handling.
- Basic admin whitelist list and outbox processing page.
- Frontend form with required privacy acceptance and separate optional marketing consent.
- Draft privacy notice and participation terms pages.

## Blockers

- Full admin review actions, bulk actions, CSV export, and audit event surfaces are not implemented.
- Mailgun delivery analytics UI is minimal; detailed webhook event history is not yet exposed in the frontend.
- Marketing campaign drafting/sending workflow is not implemented.
- Tokenomics data is incomplete and must not be published as final.
