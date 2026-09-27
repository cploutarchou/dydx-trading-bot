-- Per-strategy assistant chat. A session belongs to one user and one strategy;
-- starting a new chat archives the current one. Assistant messages may carry a
-- server-validated proposal (JSON) whose status moves from pending to applied,
-- created or dismissed exactly once.
CREATE TABLE IF NOT EXISTS strategy_chat_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    strategy_id INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_strategy_chat_sessions_user_strategy_updated
    ON strategy_chat_sessions (user_id, strategy_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS strategy_chat_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES strategy_chat_sessions (id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    proposal JSONB,
    proposal_status TEXT CHECK (proposal_status IN ('pending', 'applied', 'created', 'dismissed')),
    proposal_result JSONB,
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_chat_messages_session_id
    ON strategy_chat_messages (session_id, id);
