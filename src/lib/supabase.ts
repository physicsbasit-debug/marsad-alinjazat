import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL || '').trim().replace(/\/+$/, '');
const SUPABASE_PUBLISHABLE_KEY = (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || '').trim();

export const SUPABASE_CONFIGURED = Boolean(SUPABASE_URL && SUPABASE_PUBLISHABLE_KEY);

let client: SupabaseClient | null = null;

/**
 * Returns the browser Supabase client once S1 is configured.
 *
 * S1 deliberately does not import this helper from the production data path yet.
 * The legacy FastAPI/SQLite implementation remains the runtime source of truth
 * until a domain passes its Supabase parity gate in a later phase.
 */
export function getSupabaseClient(): SupabaseClient {
  if (!SUPABASE_CONFIGURED) {
    throw new Error(
      'Supabase غير مهيأ بعد. اضبط VITE_SUPABASE_URL وVITE_SUPABASE_PUBLISHABLE_KEY.',
    );
  }

  if (!client) {
    client = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }

  return client;
}

export function getSupabaseConfigurationStatus(): {
  configured: boolean;
  projectUrl: string | null;
} {
  return {
    configured: SUPABASE_CONFIGURED,
    projectUrl: SUPABASE_URL || null,
  };
}
