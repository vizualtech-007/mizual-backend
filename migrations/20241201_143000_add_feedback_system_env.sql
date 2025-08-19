-- Environment-aware migration for feedback system
-- This will be processed by migrate.py to target the correct schema

-- Create feedback table in the target schema
CREATE TABLE IF NOT EXISTS TARGET_SCHEMA.edit_feedback (
    id SERIAL PRIMARY KEY,
    edit_uuid VARCHAR NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    feedback_text TEXT,
    user_ip INET,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_feedback_per_edit_TARGET_SCHEMA UNIQUE(edit_uuid)
);

-- Add indexes for performance and analytics
CREATE INDEX IF NOT EXISTS idx_edit_feedback_edit_uuid_TARGET_SCHEMA ON TARGET_SCHEMA.edit_feedback(edit_uuid);
CREATE INDEX IF NOT EXISTS idx_edit_feedback_rating_TARGET_SCHEMA ON TARGET_SCHEMA.edit_feedback(rating);
CREATE INDEX IF NOT EXISTS idx_edit_feedback_created_at_TARGET_SCHEMA ON TARGET_SCHEMA.edit_feedback(created_at);