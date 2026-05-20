-- Roll back users.last_login compatibility column.
ALTER TABLE users
DROP COLUMN IF EXISTS last_login;