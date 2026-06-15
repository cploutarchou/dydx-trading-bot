# ICO Content Research

Access date: 2026-06-16

This research was used to shape ExecutionLab's ICO information architecture. It was not used to copy wording, claims, branding, or unsupported token-sale terms.

| Source | Pattern observed | Adopted | Rejected | URL |
| --- | --- | --- | --- | --- |
| ICOHotList | ICO directories emphasize compact sale facts, token name/symbol, status, dates, and documentation links. | Clear sale facts and document states. | Ranking-style investment framing and promotional urgency. | https://www.icohotlist.com/ |
| CoinList token-sale help/pages | Participation pages commonly separate sale access from KYC/AML eligibility and explain that KYC is required for sales. | Whitelist submission is not approval; eligibility/KYC remains subject to final terms. | Any claim that ExecutionLab already has a completed KYC policy or approved jurisdictions. | https://coinlist.co/faq |
| CryptoRank token sale / unlock pages | Tokenomics pages present total supply, allocations, TGE unlocks, and vesting/unlock schedules as structured data. | Tokenomics pages call out missing allocation and vesting data rather than inventing it. | Filling the remaining 75% allocation with arbitrary categories. | https://cryptorank.io/token-unlock |
| CryptoRank upcoming ICO pages | Upcoming-sale pages surface start dates, launch platforms, and key sale details. | Compact sale overview and timeline structure. | Launchpad, listing, or partnership claims not present in this repo. | https://cryptorank.io/upcoming-ico |
| Mailgun official API overview | Mailgun supports US and EU base URLs; region must match the configured sending domain. | Existing Mailgun region config is preserved; docs call out region validation. | Hardcoding one Mailgun endpoint. | https://documentation.mailgun.com/docs/mailgun/api-reference/api-overview |
| Mailgun webhook docs | Webhooks are account/domain event callbacks and must be handled by event type without duplicate processing. | Production-readiness checklist includes verified webhooks and idempotency. | Trusting unverified webhook payloads. | https://documentation.mailgun.com/docs/mailgun/api-reference/send/mailgun/webhooks |
| Mailgun unsubscribe tracking docs | Suppression/unsubscribe tracking can remove recipients from mailings. | Marketing consent and unsubscribe state are separated from whitelist status. | Treating whitelist submission as marketing subscription. | https://mailgun-docs.redoc.ly/docs/mailgun/user-manual/tracking-messages/ |
| GDPR/email marketing guidance | Email marketing needs an appropriate legal basis, and unsubscribe/opt-out must be clear. | Required privacy acceptance and separate optional marketing consent, unchecked by default. | Claiming the implementation guarantees GDPR/ePrivacy compliance. | https://gdpr-info.eu/issues/email-marketing/ |

## Implementation Notes

- Public ICO copy should stay informational and avoid return, listing, liquidity, security, or regulatory guarantees.
- Tokenomics must remain draft until allocation percentages total 100% and token amounts reconcile to total supply.
- Marketing emails must be excluded until explicit consent and confirmation are recorded.
