/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PREVIEW_MODE?: string;
  readonly VITE_BASE_PATH?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_SUPABASE_URL?: string;
  readonly VITE_SUPABASE_PUBLISHABLE_KEY?: string;
  readonly VITE_SUPABASE_SESSION_MODE?: string;
  readonly VITE_TEACHERS_DATA_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
