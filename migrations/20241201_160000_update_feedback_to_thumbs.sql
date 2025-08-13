-- Migration to update feedback system from 1-5 rating to 0/1 (thumbs down/up)
-- This updates the existing edit_feedback table structure

-- For public schema
-- First, update existing data (if any) to new format
-- Ratings 4-5 become 1 (thumbs up), ratings 1-3 become 0 (thumbs down)
UPDATE public.edit_feedback 
SET rating = CASE 
    WHEN CAST(rating AS INTEGER) >= 4 THEN 1
    WHEN CAST(rating AS INTEGER) <= 3 THEN 0
    ELSE 1  -- Default fallback
END
WHERE rating ~ '^[1-5]$';  -- Only update numeric ratings

-- Column is already INTEGER, just need to update constraint
-- Drop old constraint and add new one
ALTER TABLE public.edit_feedback 
DROP CONSTRAINT IF EXISTS edit_feedback_rating_check;

ALTER TABLE public.edit_feedback 
ADD CONSTRAINT edit_feedback_rating_check CHECK (rating IN (0, 1));

-- For preview schema
-- First, update existing data (if any) to new format
UPDATE preview.edit_feedback 
SET rating = CASE 
    WHEN CAST(rating AS INTEGER) >= 4 THEN 1
    WHEN CAST(rating AS INTEGER) <= 3 THEN 0
    ELSE 1  -- Default fallback
END
WHERE rating ~ '^[1-5]$';  -- Only update numeric ratings

-- Column is already INTEGER, just need to update constraint
-- Drop old constraint and add new one
ALTER TABLE preview.edit_feedback 
DROP CONSTRAINT IF EXISTS edit_feedback_rating_check;

ALTER TABLE preview.edit_feedback 
ADD CONSTRAINT edit_feedback_rating_check CHECK (rating IN (0, 1));

-- Add comment for documentation
COMMENT ON COLUMN public.edit_feedback.rating IS 'User feedback: 0 for thumbs down, 1 for thumbs up';
COMMENT ON COLUMN preview.edit_feedback.rating IS 'User feedback: 0 for thumbs down, 1 for thumbs up';