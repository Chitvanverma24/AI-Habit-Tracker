-- ==========================================================
-- AI HABIT TRACKER SAAS - LICENSE MANAGEMENT SYSTEM MIGRATION
-- Run this script in the Supabase SQL Editor if needed.
-- ==========================================================

SET search_path = public, pg_catalog;

-- 1. Create or alter licenses table with full required schema
CREATE TABLE IF NOT EXISTS public.licenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unused' CHECK (status IN ('unused', 'active', 'revoked')),
    assigned_user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    activated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    assigned_email TEXT,
    activated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    revoked_at TIMESTAMPTZ,
    CONSTRAINT licenses_license_key_key UNIQUE (license_key)
);

-- Ensure all columns exist if table was partially created
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'licenses' AND column_name = 'assigned_user_id') THEN
        ALTER TABLE public.licenses ADD COLUMN assigned_user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'licenses' AND column_name = 'activated_by') THEN
        ALTER TABLE public.licenses ADD COLUMN activated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'licenses' AND column_name = 'assigned_email') THEN
        ALTER TABLE public.licenses ADD COLUMN assigned_email TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'licenses' AND column_name = 'revoked_at') THEN
        ALTER TABLE public.licenses ADD COLUMN revoked_at TIMESTAMPTZ;
    END IF;
END $$;

COMMENT ON TABLE public.licenses IS 'Stores Etsy purchase license keys and activation records.';

-- 2. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_licenses_license_key ON public.licenses(license_key);
CREATE INDEX IF NOT EXISTS idx_licenses_status ON public.licenses(status);
CREATE INDEX IF NOT EXISTS idx_licenses_assigned_user_id ON public.licenses(assigned_user_id);
CREATE INDEX IF NOT EXISTS idx_licenses_assigned_email ON public.licenses(assigned_email);

-- 3. Row Level Security (RLS)
ALTER TABLE public.licenses ENABLE ROW LEVEL SECURITY;

-- Drop prior policies to avoid conflicts
DROP POLICY IF EXISTS "Users can view own license" ON public.licenses;
DROP POLICY IF EXISTS "Admins can manage all licenses" ON public.licenses;
DROP POLICY IF EXISTS "Users view own license" ON public.licenses;

-- Admin policy: full control
CREATE POLICY "Admins can manage all licenses" ON public.licenses
    FOR ALL
    USING (public.is_admin())
    WITH CHECK (public.is_admin());

-- User policy: read own active license by assigned_user_id, activated_by, or assigned_email
CREATE POLICY "Users view own license" ON public.licenses
    FOR SELECT
    USING (
        (auth.uid() IS NOT NULL AND (assigned_user_id = auth.uid() OR activated_by = auth.uid()))
        OR
        (assigned_email IS NOT NULL AND LOWER(assigned_email) = LOWER(auth.jwt()->>'email'))
    );

-- 4. RPC Function for Purchase Activation (SECURITY DEFINER allows unauthenticated activation)
CREATE OR REPLACE FUNCTION public.activate_purchase(p_license_key TEXT, p_email TEXT)
RETURNS JSONB AS $$
DECLARE
    v_key TEXT;
    v_email TEXT;
    v_license RECORD;
    v_user_id UUID := auth.uid();
BEGIN
    v_key := UPPER(TRIM(p_license_key));
    v_email := LOWER(TRIM(p_email));

    IF v_key IS NULL OR v_key = '' THEN
        RETURN jsonb_build_object('success', false, 'error', 'Invalid license key.');
    END IF;

    IF v_email IS NULL OR v_email = '' OR position('@' in v_email) = 0 THEN
        RETURN jsonb_build_object('success', false, 'error', 'Invalid email address.');
    END IF;

    -- Search for license key
    SELECT * INTO v_license FROM public.licenses WHERE UPPER(TRIM(license_key)) = v_key;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error', 'Invalid license key.');
    END IF;

    IF v_license.status = 'revoked' THEN
        RETURN jsonb_build_object('success', false, 'error', 'This license has been revoked.');
    ELSIF v_license.status = 'active' THEN
        -- Allow re-linking if activated by the same email
        IF v_license.assigned_email IS NOT NULL AND LOWER(TRIM(v_license.assigned_email)) = v_email THEN
            IF v_user_id IS NOT NULL AND v_license.assigned_user_id IS NULL THEN
                UPDATE public.licenses
                SET assigned_user_id = v_user_id, activated_by = v_user_id
                WHERE id = v_license.id;
            END IF;
            RETURN jsonb_build_object('success', true, 'message', 'Purchase already activated for this email.');
        ELSE
            RETURN jsonb_build_object('success', false, 'error', 'This license has already been activated.');
        END IF;
    END IF;

    -- Activate unused license
    UPDATE public.licenses
    SET status = 'active',
        assigned_email = v_email,
        assigned_user_id = COALESCE(v_user_id, assigned_user_id),
        activated_by = COALESCE(v_user_id, activated_by),
        activated_at = NOW()
    WHERE id = v_license.id;

    RETURN jsonb_build_object('success', true, 'message', 'Purchase activated successfully.');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- 5. Backward Compatible Function: activate_license
CREATE OR REPLACE FUNCTION public.activate_license(p_license_key TEXT)
RETURNS JSONB AS $$
DECLARE
    v_user_email TEXT := auth.jwt()->>'email';
BEGIN
    RETURN public.activate_purchase(p_license_key, COALESCE(v_user_email, ''));
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- 6. License Verification Function (SECURITY DEFINER allows unauthenticated signup check)
CREATE OR REPLACE FUNCTION public.verify_active_license(p_email TEXT, p_license_key TEXT DEFAULT NULL)
RETURNS JSONB AS $$
DECLARE
    v_email TEXT;
    v_key TEXT;
    v_license RECORD;
BEGIN
    v_email := LOWER(TRIM(COALESCE(p_email, '')));
    v_key := UPPER(TRIM(COALESCE(p_license_key, '')));

    IF v_email IS NULL OR v_email = '' THEN
        RETURN jsonb_build_object('valid', false, 'error', 'Invalid email address.');
    END IF;

    IF v_key IS NOT NULL AND v_key != '' THEN
        SELECT * INTO v_license FROM public.licenses WHERE UPPER(TRIM(license_key)) = v_key;
        IF NOT FOUND THEN
            RETURN jsonb_build_object('valid', false, 'error', 'Invalid license key.');
        END IF;

        IF v_license.status = 'revoked' THEN
            RETURN jsonb_build_object('valid', false, 'error', 'This license has been revoked.');
        ELSIF v_license.status = 'active' THEN
            IF v_license.assigned_email IS NOT NULL AND LOWER(TRIM(v_license.assigned_email)) != v_email THEN
                RETURN jsonb_build_object('valid', false, 'error', 'This license key is activated for a different email address.');
            END IF;
            RETURN jsonb_build_object(
                'valid', true,
                'id', v_license.id,
                'license_key', v_license.license_key,
                'status', v_license.status,
                'assigned_email', v_license.assigned_email,
                'assigned_user_id', v_license.assigned_user_id
            );
        ELSIF v_license.status = 'unused' THEN
            RETURN jsonb_build_object(
                'valid', true,
                'id', v_license.id,
                'license_key', v_license.license_key,
                'status', v_license.status,
                'assigned_email', v_email,
                'assigned_user_id', v_license.assigned_user_id
            );
        END IF;
    ELSE
        SELECT * INTO v_license FROM public.licenses
        WHERE LOWER(TRIM(assigned_email)) = v_email AND status = 'active'
        ORDER BY activated_at DESC LIMIT 1;

        IF NOT FOUND THEN
            RETURN jsonb_build_object('valid', false, 'error', 'No active Etsy purchase found for this email.');
        END IF;

        IF v_license.status = 'revoked' THEN
            RETURN jsonb_build_object('valid', false, 'error', 'This license has been revoked.');
        END IF;

        RETURN jsonb_build_object(
            'valid', true,
            'id', v_license.id,
            'license_key', v_license.license_key,
            'status', v_license.status,
            'assigned_email', v_license.assigned_email,
            'assigned_user_id', v_license.assigned_user_id
        );
    END IF;

    RETURN jsonb_build_object('valid', false, 'error', 'No valid active license found.');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- 7. Link User to License Function (SECURITY DEFINER)
CREATE OR REPLACE FUNCTION public.link_user_license(p_user_id UUID, p_email TEXT, p_license_key TEXT DEFAULT NULL)
RETURNS JSONB AS $$
DECLARE
    v_email TEXT;
    v_key TEXT;
    v_lic_id UUID;
BEGIN
    v_email := LOWER(TRIM(COALESCE(p_email, '')));
    v_key := UPPER(TRIM(COALESCE(p_license_key, '')));

    IF p_user_id IS NULL THEN
        RETURN jsonb_build_object('success', false, 'error', 'Invalid user ID.');
    END IF;

    IF v_key IS NOT NULL AND v_key != '' THEN
        UPDATE public.licenses
        SET assigned_user_id = p_user_id,
            activated_by = p_user_id,
            status = 'active',
            assigned_email = COALESCE(assigned_email, v_email),
            activated_at = COALESCE(activated_at, NOW())
        WHERE UPPER(license_key) = v_key AND status != 'revoked'
        RETURNING id INTO v_lic_id;
    END IF;

    IF v_lic_id IS NULL AND v_email IS NOT NULL AND v_email != '' THEN
        UPDATE public.licenses
        SET assigned_user_id = p_user_id,
            activated_by = p_user_id
        WHERE LOWER(assigned_email) = v_email AND status = 'active'
        RETURNING id INTO v_lic_id;
    END IF;

    IF v_lic_id IS NOT NULL THEN
        RETURN jsonb_build_object('success', true, 'license_id', v_lic_id);
    ELSE
        RETURN jsonb_build_object('success', false, 'error', 'License not found to link.');
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- 8. Admin Bulk License Generator Function (SECURITY DEFINER)
CREATE OR REPLACE FUNCTION public.generate_bulk_licenses(p_keys TEXT[])
RETURNS JSONB AS $$
DECLARE
    v_key TEXT;
    v_count INT := 0;
BEGIN
    IF NOT public.is_admin() THEN
        RETURN jsonb_build_object('success', false, 'error', 'Permission denied. Only admins can generate licenses.');
    END IF;

    FOREACH v_key IN ARRAY p_keys LOOP
        INSERT INTO public.licenses (license_key, status)
        VALUES (v_key, 'unused')
        ON CONFLICT (license_key) DO NOTHING;
        v_count := v_count + 1;
    END LOOP;

    RETURN jsonb_build_object('success', true, 'count', v_count);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;
