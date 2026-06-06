CREATE TABLE IF NOT EXISTS partner_applications (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    applicant_user_id BIGINT NOT NULL,
    sponsor_user_id BIGINT,
    requested_role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    business_name TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    review_notes TEXT NOT NULL DEFAULT '',
    reviewed_by_user_id BIGINT,
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_partner_applications_applicant_user_id ON partner_applications(applicant_user_id);
CREATE INDEX IF NOT EXISTS idx_partner_applications_sponsor_user_id ON partner_applications(sponsor_user_id);
CREATE INDEX IF NOT EXISTS idx_partner_applications_status ON partner_applications(status);
