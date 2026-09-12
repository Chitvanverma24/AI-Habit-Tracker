-- ==========================================================
-- AI HABIT TRACKER SAAS - PASSWORD RESET REQUESTS MIGRATION
-- Run this script in the Supabase SQL Editor if needed.
-- ==========================================================

SET search_path = public, pg_catalog;

-- 1. Create table for password reset requests
CREATE TABLE IF NOT EXISTS public.password_reset_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'expired', 'rejected')),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    processed_at TIMESTAMPTZ,
    processed_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ
);

COMMENT ON TABLE public.password_reset_requests IS 'Stores manual password reset requests submitted by users for admin processing.';

-- 2. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_password_reset_requests_status ON public.password_reset_requests(status);
CREATE INDEX IF NOT EXISTS idx_password_reset_requests_email ON public.password_reset_requests(email);
CREATE INDEX IF NOT EXISTS idx_password_reset_requests_created_at ON public.password_reset_requests(created_at DESC);

-- 3. Row Level Security (RLS)
ALTER TABLE public.password_reset_requests ENABLE ROW LEVEL SECURITY;

-- Drop prior policies to avoid conflicts
DROP POLICY IF EXISTS "Admins can manage all password reset requests" ON public.password_reset_requests;
DROP POLICY IF EXISTS "Public can submit password reset requests" ON public.password_reset_requests;

-- Admin policy: full control (SELECT, INSERT, UPDATE, DELETE)
CREATE POLICY "Admins can manage all password reset requests" ON public.password_reset_requests
    FOR ALL
    USING (public.is_admin())
    WITH CHECK (public.is_admin());

-- Public policy: INSERT only (for unauthenticated users submitting a request)
CREATE POLICY "Public can submit password reset requests" ON public.password_reset_requests
    FOR INSERT
    WITH CHECK (true);
