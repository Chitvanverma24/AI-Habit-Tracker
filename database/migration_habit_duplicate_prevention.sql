-- ==========================================================
-- AI HABIT TRACKER SAAS - HABIT DUPLICATE PREVENTION MIGRATION
-- Run this script in the Supabase SQL Editor if needed to enforce
-- unique habit titles per user (case-insensitive and trimmed).
-- ==========================================================

SET search_path = public, pg_catalog;

-- Add unique index on (user_id, LOWER(TRIM(title)))
-- This allows User A -> Gym and User B -> Gym,
-- but prevents User A from having duplicate habits such as Gym and gym/GYM.
CREATE UNIQUE INDEX IF NOT EXISTS idx_habits_user_id_normalized_title 
ON public.habits (user_id, LOWER(TRIM(title)));
