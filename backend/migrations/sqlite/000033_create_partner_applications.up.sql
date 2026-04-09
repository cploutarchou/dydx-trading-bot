CREATE TABLE IF NOT EXISTS partner_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_user_id INTEGER NOT NULL,
    sponsor_user_id INTEGER,
    requested_role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    business_name TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    review_notes TEXT NOT NULL DEFAULT '',
    reviewed_by_user_id INTEGER,
    reviewed_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (applicant_user_id) REFERENCES users(id),
    FOREIGN KEY (sponsor_user_id) REFERENCES users(id),
    FOREIGN KEY (reviewed_by_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_partner_applications_applicant_user_id ON partner_applications(applicant_user_id);
CREATE INDEX IF NOT EXISTS idx_partner_applications_sponsor_user_id ON partner_applications(sponsor_user_id);
CREATE INDEX IF NOT EXISTS idx_partner_applications_status ON partner_applications(status);
