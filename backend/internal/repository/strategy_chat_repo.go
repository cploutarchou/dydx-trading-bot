package repository

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// StrategyChatRepository stores strategy chat sessions and messages.
type StrategyChatRepository struct {
	db SQLRunner
	// base is the database itself, kept for starting transactions.
	base     *sql.DB
	dbDriver string
}

// NewStrategyChatRepository creates a strategy chat repository.
func NewStrategyChatRepository(db *sql.DB) *StrategyChatRepository {
	driver := os.Getenv("DB_TYPE")
	if driver == "" {
		driver = os.Getenv("DB_DRIVER")
	}
	if driver == "" {
		driver = "postgres"
	}
	return &StrategyChatRepository{db: db, base: db, dbDriver: driver}
}

// WithTx returns a copy of the repository that executes within tx.
func (r *StrategyChatRepository) WithTx(tx *sql.Tx) *StrategyChatRepository {
	return &StrategyChatRepository{db: tx, base: r.base, dbDriver: r.dbDriver}
}

// Begin starts a transaction on the database for callers that bind several
// repositories to it with WithTx.
func (r *StrategyChatRepository) Begin() (*sql.Tx, error) {
	tx, err := r.base.Begin()
	if err != nil {
		return nil, fmt.Errorf("failed to begin strategy chat transaction: %w", err)
	}
	return tx, nil
}

func (r *StrategyChatRepository) bindQuery(query string) string {
	return bindPlaceholders(r.dbDriver, query)
}

const strategyChatSessionColumns = `id, user_id, strategy_id, title, created_at, updated_at, archived_at`

const strategyChatMessageColumns = `id, session_id, role, content, proposal, proposal_status, proposal_result,
	provider, model, input_tokens, output_tokens, created_at`

type strategyChatRowScanner interface {
	Scan(dest ...any) error
}

func scanStrategyChatSession(row strategyChatRowScanner) (*models.StrategyChatSession, error) {
	session := &models.StrategyChatSession{}
	if err := row.Scan(
		&session.ID, &session.UserID, &session.StrategyID, &session.Title,
		&session.CreatedAt, &session.UpdatedAt, &session.ArchivedAt,
	); err != nil {
		return nil, err
	}
	return session, nil
}

func scanStrategyChatMessage(row strategyChatRowScanner) (*models.StrategyChatMessage, error) {
	message := &models.StrategyChatMessage{}
	if err := row.Scan(
		&message.ID, &message.SessionID, &message.Role, &message.Content,
		&message.Proposal, &message.ProposalStatus, &message.ProposalResult,
		&message.Provider, &message.Model, &message.InputTokens, &message.OutputTokens,
		&message.CreatedAt,
	); err != nil {
		return nil, err
	}
	return message, nil
}

// GetActiveSession returns the user's current (not archived) session for a
// strategy, or nil when there is none.
func (r *StrategyChatRepository) GetActiveSession(userID, strategyID int) (*models.StrategyChatSession, error) {
	query := `SELECT ` + strategyChatSessionColumns + `
		FROM strategy_chat_sessions
		WHERE user_id = ? AND strategy_id = ? AND archived_at IS NULL
		ORDER BY updated_at DESC, id DESC
		LIMIT 1`
	session, err := scanStrategyChatSession(r.db.QueryRow(r.bindQuery(query), userID, strategyID))
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get active strategy chat session: %w", err)
	}
	return session, nil
}

// GetSession returns a session by id, or nil when it does not exist.
func (r *StrategyChatRepository) GetSession(id int64) (*models.StrategyChatSession, error) {
	query := `SELECT ` + strategyChatSessionColumns + ` FROM strategy_chat_sessions WHERE id = ? LIMIT 1`
	session, err := scanStrategyChatSession(r.db.QueryRow(r.bindQuery(query), id))
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get strategy chat session: %w", err)
	}
	return session, nil
}

// StartSession archives the user's current session for the strategy and
// creates an empty one, in one transaction.
func (r *StrategyChatRepository) StartSession(userID, strategyID int) (*models.StrategyChatSession, error) {
	tx, err := r.base.Begin()
	if err != nil {
		return nil, fmt.Errorf("failed to begin strategy chat session transaction: %w", err)
	}
	defer rollbackStrategyChatTx(tx)

	now := time.Now().UTC()
	if _, err := tx.Exec(
		r.bindQuery(`UPDATE strategy_chat_sessions SET archived_at = ? WHERE user_id = ? AND strategy_id = ? AND archived_at IS NULL`),
		now, userID, strategyID,
	); err != nil {
		return nil, fmt.Errorf("failed to archive strategy chat sessions: %w", err)
	}
	session, err := r.insertSession(tx, userID, strategyID, "", now)
	if err != nil {
		return nil, err
	}
	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit strategy chat session: %w", err)
	}
	return session, nil
}

func (r *StrategyChatRepository) insertSession(tx *sql.Tx, userID, strategyID int, title string, now time.Time) (*models.StrategyChatSession, error) {
	session := &models.StrategyChatSession{
		UserID:     userID,
		StrategyID: strategyID,
		Title:      title,
		CreatedAt:  now,
		UpdatedAt:  now,
	}
	if err := tx.QueryRow(
		r.bindQuery(`INSERT INTO strategy_chat_sessions (user_id, strategy_id, title, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?)
			RETURNING id`),
		userID, strategyID, title, now, now,
	).Scan(&session.ID); err != nil {
		return nil, fmt.Errorf("failed to create strategy chat session: %w", err)
	}
	return session, nil
}

// ListRecentMessages returns up to limit of the session's newest messages,
// oldest first.
func (r *StrategyChatRepository) ListRecentMessages(sessionID int64, limit int) ([]models.StrategyChatMessage, error) {
	if limit <= 0 {
		limit = 20
	}
	query := `SELECT ` + strategyChatMessageColumns + `
		FROM strategy_chat_messages
		WHERE session_id = ?
		ORDER BY id DESC
		LIMIT ?`
	rows, err := r.db.Query(r.bindQuery(query), sessionID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query strategy chat messages: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close strategy chat message rows: %v", closeErr)
		}
	}()

	messages := make([]models.StrategyChatMessage, 0)
	for rows.Next() {
		message, err := scanStrategyChatMessage(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan strategy chat message: %w", err)
		}
		messages = append(messages, *message)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("failed to read strategy chat messages: %w", err)
	}
	for left, right := 0, len(messages)-1; left < right; left, right = left+1, right-1 {
		messages[left], messages[right] = messages[right], messages[left]
	}
	return messages, nil
}

// GetMessage returns a message by id, or nil when it does not exist.
func (r *StrategyChatRepository) GetMessage(id int64) (*models.StrategyChatMessage, error) {
	query := `SELECT ` + strategyChatMessageColumns + ` FROM strategy_chat_messages WHERE id = ? LIMIT 1`
	message, err := scanStrategyChatMessage(r.db.QueryRow(r.bindQuery(query), id))
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get strategy chat message: %w", err)
	}
	return message, nil
}

// AppendTurn stores a user message and the assistant reply together. When
// session.ID is 0 the session is created in the same transaction; otherwise
// its updated_at (and an empty title) is refreshed. Nothing is stored unless
// every statement succeeds.
func (r *StrategyChatRepository) AppendTurn(session *models.StrategyChatSession, userMessage, assistantMessage *models.StrategyChatMessage) error {
	tx, err := r.base.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin strategy chat turn transaction: %w", err)
	}
	defer rollbackStrategyChatTx(tx)

	now := time.Now().UTC()
	if session.ID == 0 {
		created, err := r.insertSession(tx, session.UserID, session.StrategyID, session.Title, now)
		if err != nil {
			return err
		}
		*session = *created
	} else {
		if _, err := tx.Exec(
			r.bindQuery(`UPDATE strategy_chat_sessions
				SET updated_at = ?, title = CASE WHEN title = '' THEN ? ELSE title END
				WHERE id = ?`),
			now, session.Title, session.ID,
		); err != nil {
			return fmt.Errorf("failed to update strategy chat session: %w", err)
		}
		session.UpdatedAt = now
	}

	for _, message := range []*models.StrategyChatMessage{userMessage, assistantMessage} {
		message.SessionID = session.ID
		message.CreatedAt = now
		if err := tx.QueryRow(
			r.bindQuery(`INSERT INTO strategy_chat_messages (
					session_id, role, content, proposal, proposal_status, proposal_result,
					provider, model, input_tokens, output_tokens, created_at
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				RETURNING id`),
			message.SessionID, message.Role, message.Content,
			strategyChatNullValue(message.Proposal), strategyChatNullValue(message.ProposalStatus), strategyChatNullValue(message.ProposalResult),
			message.Provider, message.Model, message.InputTokens, message.OutputTokens, message.CreatedAt,
		).Scan(&message.ID); err != nil {
			return fmt.Errorf("failed to store strategy chat message: %w", err)
		}
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit strategy chat turn: %w", err)
	}
	return nil
}

// TransitionProposal moves a message's proposal from one status to another
// and stores result, only while the status is still from. It reports whether
// the row changed, so two concurrent actions cannot both claim a proposal.
func (r *StrategyChatRepository) TransitionProposal(messageID int64, from, to string, result sql.NullString) (bool, error) {
	outcome, err := r.db.Exec(
		r.bindQuery(`UPDATE strategy_chat_messages
			SET proposal_status = ?, proposal_result = ?
			WHERE id = ? AND proposal_status = ?`),
		to, strategyChatNullValue(result), messageID, from,
	)
	if err != nil {
		return false, fmt.Errorf("failed to update strategy chat proposal: %w", err)
	}
	affected, err := outcome.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("failed to read strategy chat proposal update: %w", err)
	}
	return affected > 0, nil
}

// SetProposalResult stores the result of a proposal that already has status
// and reports whether a row changed.
func (r *StrategyChatRepository) SetProposalResult(messageID int64, status string, result string) (bool, error) {
	outcome, err := r.db.Exec(
		r.bindQuery(`UPDATE strategy_chat_messages SET proposal_result = ? WHERE id = ? AND proposal_status = ?`),
		result, messageID, status,
	)
	if err != nil {
		return false, fmt.Errorf("failed to store strategy chat proposal result: %w", err)
	}
	affected, err := outcome.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("failed to read strategy chat proposal result update: %w", err)
	}
	return affected > 0, nil
}

func strategyChatNullValue(value sql.NullString) any {
	if !value.Valid {
		return nil
	}
	return value.String
}

func rollbackStrategyChatTx(tx *sql.Tx) {
	if err := tx.Rollback(); err != nil && err != sql.ErrTxDone {
		log.Printf("failed to roll back strategy chat transaction: %v", err)
	}
}
