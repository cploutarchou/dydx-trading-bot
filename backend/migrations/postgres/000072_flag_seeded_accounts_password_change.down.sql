UPDATE users
SET password_change_required = FALSE, updated_at = now()
WHERE username IN ('admin', 'user', 'officer', 'ib');
