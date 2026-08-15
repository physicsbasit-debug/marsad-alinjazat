import { useEffect, useMemo, useRef, useState, type ChangeEvent, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { getArchiveYears, searchGlobal } from '../lib/api';
import type { SearchResponse, SearchResult, SearchSection } from '../types';
import { Icon } from './Icon';

const sectionOptions: Array<{ value: SearchSection; label: string }> = [
  { value: 'all', label: 'كل الأقسام' },
  { value: 'teachers', label: 'المعلمون' },
  { value: 'planning', label: 'التخطيط والمنهج' },
  { value: 'achievement', label: 'التحصيل والنتائج' },
  { value: 'supervision', label: 'الإشراف والمتابعة' },
  { value: 'requests', label: 'طلبات الملفات' },
  { value: 'meetings', label: 'الاجتماعات والقرارات' },
  { value: 'events', label: 'الفعاليات والتوثيق' },
  { value: 'documents', label: 'الوثائق والمراجع' },
];

const sectionIcons: Record<Exclude<SearchSection, 'all'>, 'teachers' | 'planning' | 'chart' | 'supervision' | 'upload' | 'meeting' | 'spark' | 'document'> = {
  teachers: 'teachers', planning: 'planning', achievement: 'chart', supervision: 'supervision', requests: 'upload', meetings: 'meeting', events: 'spark', documents: 'document',
};

export function GlobalSearch({ currentAcademicYear, onNavigate }: { currentAcademicYear: string; onNavigate: (result: SearchResult) => void }) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [section, setSection] = useState<SearchSection>('all');
  const [academicYear, setAcademicYear] = useState('all');
  const [years, setYears] = useState<string[]>([currentAcademicYear]);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const cleanQuery = query.trim().replace(/\s+/g, ' ');

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen(true);
        requestAnimationFrame(() => inputRef.current?.focus());
      }
      if (event.key === 'Escape') setOpen(false);
    }
    function outside(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    window.addEventListener('keydown', shortcut);
    document.addEventListener('mousedown', outside);
    return () => { window.removeEventListener('keydown', shortcut); document.removeEventListener('mousedown', outside); };
  }, []);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void getArchiveYears().then((index) => {
      if (cancelled) return;
      const found = index.years.map((item) => item.academicYear);
      setYears(found.length ? found : [currentAcademicYear]);
    }).catch(() => { if (!cancelled) setYears([currentAcademicYear]); });
    return () => { cancelled = true; };
  }, [open, currentAcademicYear]);

  useEffect(() => {
    setActiveIndex(0);
    if (cleanQuery.length < 2) {
      setResponse(null); setError(''); setLoading(false); return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true); setError('');
      void searchGlobal({ q: cleanQuery, section, academicYear, limit: 40 })
        .then((result) => { if (!cancelled) setResponse(result); })
        .catch((reason: unknown) => { if (!cancelled) { setResponse(null); setError(reason instanceof Error ? reason.message : 'تعذر تنفيذ البحث.'); } })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, 180);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [cleanQuery, section, academicYear]);

  const grouped = useMemo(() => {
    const groups: Array<{ section: SearchResult['section']; label: string; items: SearchResult[] }> = [];
    for (const result of response?.results || []) {
      let group = groups.find((item) => item.section === result.section);
      if (!group) { group = { section: result.section, label: result.sectionLabel, items: [] }; groups.push(group); }
      group.items.push(result);
    }
    return groups;
  }, [response]);

  const flatResults = response?.results || [];

  function choose(result: SearchResult) {
    onNavigate(result);
    setOpen(false);
    setQuery('');
    setResponse(null);
  }

  function keyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (!flatResults.length) return;
    if (event.key === 'ArrowDown') { event.preventDefault(); setActiveIndex((value) => Math.min(value + 1, flatResults.length - 1)); }
    if (event.key === 'ArrowUp') { event.preventDefault(); setActiveIndex((value) => Math.max(value - 1, 0)); }
    if (event.key === 'Enter') { event.preventDefault(); choose(flatResults[activeIndex] || flatResults[0]); }
  }

  return (
    <div className="global-search-wrap" ref={rootRef}>
      <label className={`global-search ${open ? 'active' : ''}`}>
        <Icon name="search" />
        <input ref={inputRef} value={query} onFocus={() => setOpen(true)} onChange={(event: ChangeEvent<HTMLInputElement>) => { setQuery(event.target.value); setOpen(true); }} onKeyDown={keyDown} placeholder="ابحث في أعمال المادة..." autoComplete="off" aria-label="البحث الشامل" />
        {loading ? <span className="search-mini-spinner" aria-label="جاري البحث" /> : <kbd>⌘ K</kbd>}
      </label>

      {open && <section className="global-search-panel" aria-label="نتائج البحث الشامل">
        <div className="global-search-filters">
          <select value={section} onChange={(event: ChangeEvent<HTMLSelectElement>) => setSection(event.target.value as SearchSection)} aria-label="قسم البحث">
            {sectionOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <select value={academicYear} onChange={(event: ChangeEvent<HTMLSelectElement>) => setAcademicYear(event.target.value)} aria-label="العام الدراسي">
            <option value="all">كل الأعوام</option>
            {years.map((year) => <option key={year} value={year}>{year}{year === currentAcademicYear ? ' • الجاري' : ''}</option>)}
          </select>
        </div>

        {cleanQuery.length < 2 ? <div className="global-search-hint"><span className="search-hint-icon"><Icon name="search" size={22}/></span><div><strong>ابحث في ذاكرة المرصد كلها</strong><p>اكتب حرفين على الأقل. يمكنك البحث باسم معلم، خطة، درس، اختبار، زيارة، قرار، فعالية أو وثيقة.</p></div></div> : error ? <div className="global-search-error"><Icon name="alert" size={18}/>{error}</div> : !loading && response && response.total === 0 ? <div className="global-search-empty"><Icon name="search" size={24}/><strong>لا توجد نتائج مطابقة</strong><span>جرّب كلمة أقصر أو غيّر القسم أو العام الدراسي.</span></div> : <div className="global-search-results">
          {response && <div className="global-search-summary"><span>{response.total} نتيجة</span>{response.total > response.results.length && <small>نعرض أول {response.results.length} نتيجة بحسب الصلة</small>}</div>}
          {grouped.map((group) => <div className="search-result-group" key={group.section}>
            <div className="search-result-group-title"><span><Icon name={sectionIcons[group.section]} size={16}/>{group.label}</span><b>{response?.counts[group.section] || group.items.length}</b></div>
            {group.items.map((result) => {
              const index = flatResults.findIndex((item) => item.key === result.key);
              return <button key={result.key} className={`global-search-result ${index === activeIndex ? 'active' : ''}`} onMouseEnter={() => setActiveIndex(index)} onClick={() => choose(result)}>
                <span className="search-result-icon"><Icon name={sectionIcons[result.section]} size={18}/></span>
                <span className="search-result-copy"><strong>{result.title}</strong><small>{result.subtitle || result.sectionLabel}</small>{result.excerpt && <em>{result.excerpt}</em>}</span>
                <span className="search-result-meta">{result.academicYear && <small>{result.academicYear}</small>}{result.status && <b>{result.status}</b>}<Icon name="arrow" size={15}/></span>
              </button>;
            })}
          </div>)}
        </div>}
        <footer className="global-search-footer"><span><kbd>↑</kbd><kbd>↓</kbd> للتنقل</span><span><kbd>Enter</kbd> للفتح</span><span><kbd>Esc</kbd> للإغلاق</span></footer>
      </section>}
    </div>
  );
}
