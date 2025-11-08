-- Create dydx_keys table
CREATE TABLE IF NOT EXISTS dydx_keys
(
  id               SERIAL PRIMARY KEY,
  user_id          INTEGER      NOT NULL,
  network          VARCHAR(50)  NOT NULL,
  chain_address    VARCHAR(255) NOT NULL,
  encrypted_secret TEXT         NOT NULL,
  is_active        BOOLEAN      NOT NULL,
  created_at       TIMESTAMP     NOT NULL,
  updated_at       TIMESTAMP     NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users (id),
  UNIQUE (user_id, network)
);

CREATE INDEX ix_dydx_keys_id ON dydx_keys (id);
CREATE INDEX ix_dydx_keys_network ON dydx_keys (network);
CREATE INDEX ix_dydx_keys_user_id ON dydx_keys (user_id);

