package models

import (
	"database/sql"
	"time"
)

// ==================== STRATEGY CHAT MODELS ====================

// Strategy chat roles and proposal states, mirrored by CHECK constraints in
// migration 000075.
const (
	StrategyChatRoleUser      = "user"
	StrategyChatRoleAssistant = "assistant"

	StrategyChatProposalPending   = "pending"
	StrategyChatProposalApplied   = "applied"
	StrategyChatProposalCreated   = "created"
	StrategyChatProposalDismissed = "dismissed"
)

// StrategyChatSession is one conversation of a user about one strategy.
type StrategyChatSession struct {
	ID         int64      `db:"id" json:"id"`
	UserID     int        `db:"user_id" json:"user_id"`
	StrategyID int        `db:"strategy_id" json:"strategy_id"`
	Title      string     `db:"title" json:"title"`
	CreatedAt  time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt  time.Time  `db:"updated_at" json:"updated_at"`
	ArchivedAt *time.Time `db:"archived_at" json:"archived_at"`
}

// StrategyChatMessage is one stored chat message. Proposal and ProposalResult
// hold JSON; ProposalStatus is set only on assistant messages with a proposal.
type StrategyChatMessage struct {
	ID             int64          `db:"id" json:"id"`
	SessionID      int64          `db:"session_id" json:"session_id"`
	Role           string         `db:"role" json:"role"`
	Content        string         `db:"content" json:"content"`
	Proposal       sql.NullString `db:"proposal" json:"proposal"`
	ProposalStatus sql.NullString `db:"proposal_status" json:"proposal_status"`
	ProposalResult sql.NullString `db:"proposal_result" json:"proposal_result"`
	Provider       string         `db:"provider" json:"provider"`
	Model          string         `db:"model" json:"model"`
	InputTokens    int            `db:"input_tokens" json:"input_tokens"`
	OutputTokens   int            `db:"output_tokens" json:"output_tokens"`
	CreatedAt      time.Time      `db:"created_at" json:"created_at"`
}
