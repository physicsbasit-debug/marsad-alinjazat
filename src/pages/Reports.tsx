import { useEffect, useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { getOfficialReport } from '../lib/api';
import type { OfficialReport, OfficialReportQuery, OfficialReportType, Teacher } from '../types';

const reportCards: Array<{ id: OfficialReportType; title: string; detail: string; icon: 'report' | 'teachers' | 'planning' | 'chart' | 'supervision' | 'meeting' | 'spark' }> = [
  { id: 'department', title: 'تقرير القسم الشامل', detail: 'صورة مؤسسية موحدة لأعمال القسم', icon: 'report' },
  { id: 'teacher', title: 'تقرير المعلم', detail: 'ملف مهني وتشغيلي للمعلم', icon: 'teachers' },
  { id: 'planning', title: 'تقرير التخطيط', detail: 'تقدم الخطط والوحدات المتأخرة', icon: 'planning' },
  { id: 'achievement', title: 'تقرير التحصيل', detail: 'التقويمات والإتقان والتدخلات', icon: 'chart' },
  { id: 'supervision', title: 'تقرير الإشراف', detail: 'الزيارات وحالات المتابعة', icon: 'supervision' },
  { id: 'meetings', title: 'تقرير الاجتماعات', detail: 'الاجتماعات والقرارات والتنفيذ', icon: 'meeting' },
  { id: 'events', title: 'تقرير الفعاليات', detail: 'الفعاليات والمشاركة والأدلة', icon: 'spark' },
];

export function Reports({ teachers, academicYear, term }: { teachers: Teacher[]; academicYear: string; term: string }) {
  const [query, setQuery] = useState<OfficialReportQuery>({ reportType: 'department', academicYear, term, teacherId: teachers[0]?.id ?? null });
  const [report, setReport] = useState<OfficialReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const selected = useMemo(() => reportCards.find((item) => item.id === query.reportType) || reportCards[0], [query.reportType]);

  async function loadReport(nextQuery = query) {
    setLoading(true);
    setError('');
    try {
      setReport(await getOfficialReport(nextQuery));
    } catch (e) {
      setReport(null);
      setError(e instanceof Error ? e.message : 'تعذر إنشاء التقرير.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadReport(); /* initial official report */ }, []);

  function chooseType(reportType: OfficialReportType) {
    const next = { ...query, reportType };
    setQuery(next);
    void loadReport(next);
  }

  return (
    <div className="page reports-page">
      <header className="hero-block reports-hero no-print">
        <div>
          <span className="eyebrow">مركز التقارير الرسمي</span>
          <h1>تقارير موحدة من البيانات الفعلية</h1>
          <p>اختر نوع التقرير والنطاق، وسيبني المرصد وثيقة قابلة للطباعة من السجلات الموجودة دون نسخ البيانات أو إنشاء حسابات موازية.</p>
        </div>
        <button className="primary-button" onClick={() => report && window.print()} disabled={!report || loading}><Icon name="report" /> طباعة التقرير</button>
      </header>

      <section className="report-type-grid no-print">
        {reportCards.map((card) => (
          <button key={card.id} className={`report-type-card ${query.reportType === card.id ? 'active' : ''}`} onClick={() => chooseType(card.id)}>
            <span><Icon name={card.icon} /></span>
            <strong>{card.title}</strong>
            <small>{card.detail}</small>
          </button>
        ))}
      </section>

      <section className="panel report-filter-panel no-print">
        <div className="panel-heading"><div><span className="eyebrow">نطاق التقرير</span><h2>{selected.title}</h2></div><span className="report-contract-chip">عقد موحد</span></div>
        <div className="report-filter-grid">
          <label>العام الدراسي<input value={query.academicYear} onChange={(e) => setQuery({ ...query, academicYear: e.target.value })} placeholder="2026/2027" /></label>
          <label>الفصل<select value={query.term} onChange={(e) => setQuery({ ...query, term: e.target.value })}><option>الفصل الأول</option><option>الفصل الثاني</option><option>العام كاملًا</option></select></label>
          {query.reportType === 'teacher' && <label>المعلم<select value={query.teacherId || ''} onChange={(e) => setQuery({ ...query, teacherId: Number(e.target.value) || null })}><option value="">اختر المعلم</option>{teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name} — {teacher.subject}</option>)}</select></label>}
          <button className="primary-button report-build-button" onClick={() => void loadReport()} disabled={loading}>{loading ? 'جاري بناء التقرير...' : 'تحديث التقرير'}</button>
        </div>
        <p className="report-filter-note">التقرير قراءة لحالة البيانات عند لحظة الإنشاء. لا يغيّر أي سجل، ولا يفسر المؤشرات خارج ما هو موثق في النظام.</p>
      </section>

      {error && <div className="inline-error no-print"><Icon name="alert" size={18} />{error}</div>}
      {loading && <div className="report-loading no-print"><span className="spinner"></span><p>جاري تجميع التقرير من مصادره...</p></div>}
      {report && !loading && <OfficialReportDocument report={report} />}
    </div>
  );
}

function OfficialReportDocument({ report }: { report: OfficialReport }) {
  return (
    <article className="official-report" id="official-report">
      <header className="official-report-header">
        <div className="official-report-brand"><span className="brand-mark">م</span><div><strong>مرصد الإنجازات</strong><small>تقرير رسمي من السجلات المؤسسية</small></div></div>
        <div className="official-report-meta"><span>{report.academicYear}</span><span>{report.term}</span><span>{formatGenerated(report.generatedAt)}</span></div>
      </header>

      <section className="official-report-title">
        <span className="eyebrow">وثيقة تقرير</span>
        <h1>{report.title}</h1>
        <p>{report.subtitle}</p>
        {report.teacher && <div className="report-teacher-line"><strong>{report.teacher.name}</strong><span>{report.teacher.subject}</span></div>}
      </section>

      <section className="official-report-summary"><h2>الخلاصة التنفيذية</h2><p>{report.summary}</p></section>

      <section className="official-report-metrics">
        {report.metrics.map((metric) => <div key={`${metric.label}-${metric.value}`}><span>{metric.label}</span><strong>{metric.value}</strong>{metric.detail && <small>{metric.detail}</small>}</div>)}
      </section>

      {report.sections.map((section) => (
        <section className="official-report-section" key={section.id}>
          <div className="official-report-section-title"><h2>{section.title}</h2>{section.description && <p>{section.description}</p>}</div>
          {section.rows.length ? <div className="official-report-table-wrap"><table><thead><tr>{section.columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{section.rows.map((row, index) => <tr key={`${section.id}-${index}`}>{section.columns.map((column) => <td key={column.key}>{formatCell(row[column.key])}</td>)}</tr>)}</tbody></table></div> : <div className="report-empty-row">لا توجد سجلات ضمن النطاق المحدد.</div>}
        </section>
      ))}

      <footer className="official-report-footer">
        <div><strong>مصادر التقرير</strong><span>{Object.entries(report.sourceCounts).map(([key, value]) => `${sourceLabel(key)}: ${value}`).join(' • ') || 'لا بيانات'}</span></div>
        <div><strong>مرصد الإنجازات</strong><span>تقرير مشتق من السجلات كما هي عند وقت الإنشاء.</span></div>
      </footer>
    </article>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'نعم' : 'لا';
  return String(value);
}

function formatGenerated(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ar-OM', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function sourceLabel(key: string): string {
  const labels: Record<string, string> = { teachers: 'المعلمون', plans: 'الخطط', assessments: 'التقويمات', visits: 'الزيارات', meetings: 'الاجتماعات', decisions: 'القرارات', events: 'الفعاليات', documents: 'الوثائق', requests: 'الطلبات' };
  return labels[key] || key;
}
