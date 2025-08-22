-- Environment-aware migration for processing stage
-- This will be processed by migrate.py to target the correct schema

-- Add processing_stage column to edits table in target schema
ALTER TABLE TARGET_SCHEMA.edits ADD COLUMN IF NOT EXISTS processing_stage VARCHAR(50) DEFAULT 'pending';

-- Update existing records to have proper processing_stage based on current status
UPDATE TARGET_SCHEMA.edits 
SET processing_stage = CASE 
    WHEN status = 'completed' THEN 'completed'
    WHEN status = 'failed' THEN 'failed'
    WHEN status = 'processing' THEN 'processing_image'
    ELSE 'pending'
END
WHERE processing_stage IS NULL OR processing_stage = 'pending';

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_edits_processing_stage_TARGET_SCHEMA ON TARGET_SCHEMA.edits(processing_stage);