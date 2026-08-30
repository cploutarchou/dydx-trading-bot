-- Forward companion to the edits in 000021/000049 (review finding 4.1):
-- deployments that already applied the ORIGINAL seed migrations kept
-- password_change_required=FALSE for repo-known seeded accounts, so the
-- server-side password-change gate has nothing to enforce for them. This
-- forward migration flags those accounts on every environment.
UPDATE users
SET password_change_required = TRUE, updated_at = now()
WHERE username IN ('admin', 'user', 'officer', 'ib')
  AND password_change_required = FALSE;
