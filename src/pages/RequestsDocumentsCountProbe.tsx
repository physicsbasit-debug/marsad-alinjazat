import { useEffect } from 'react';
import { loadTenantSessionContext, subscribeToAuthChanges } from '../lib/supabaseSession';
import { loadSupabaseOpenRequestCount } from '../lib/supabaseRequestsDocuments';
import { REQUESTS_DOCUMENTS_DATA_MODE } from './RequestsWorkspace';

export function RequestsDocumentsCountProbe({
  academicYear,
  currentAcademicYear,
  onCount,
}: {
  academicYear: string;
  currentAcademicYear: string;
  onCount: (count: number | null) => void;
}) {
  useEffect(() => {
    let active = true;
    async function refresh() {
      if (REQUESTS_DOCUMENTS_DATA_MODE !== 'supabase' || academicYear !== currentAcademicYear) {
        if (active) onCount(null);
        return;
      }
      try {
        const context = await loadTenantSessionContext();
        if (!context || context.academicYear !== academicYear) {
          if (active) onCount(null);
          return;
        }
        const count = await loadSupabaseOpenRequestCount(context);
        if (active) onCount(count);
      } catch {
        if (active) onCount(null);
      }
    }
    void refresh();
    const unsubscribe = subscribeToAuthChanges(() => { void refresh(); });
    return () => { active = false; unsubscribe(); };
  }, [academicYear, currentAcademicYear, onCount]);
  return null;
}
