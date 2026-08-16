import { useEffect, useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { getArchiveYear, getArchiveYears } from '../lib/api';
import type { ArchiveYearDetail, ArchiveYearSummary } from '../types';

export function Archive({ currentAcademicYear, onOpenYear }: { currentAcademicYear: string; onOpenYear?: (academicYear: string) => void }) {
  const [years, setYears] = useState<ArchiveYearSummary[]>([]);
  const [selectedYear, setSelectedYear] = useState(currentAcademicYear);
  const [detail, setDetail] = useState<ArchiveYearDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const selectedSummary = useMemo(
    () => years.find((item) => item.academicYear === selectedYear) || null,
    [years, selectedYear],
  );

  async function loadYear(academicYear: string) {
    setLoading(true);
    setError('');
    try {
      setDetail(await getArchiveYear(academicYear));
    } catch (e) {
      setDetail(null);
      setError(e instanceof Error ? e.message : 'تعذر فتح الأرشيف السنوي.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const index = await getArchiveYears();
        if (!active) return;
        setYears(index.years);
        const preferred = index.years.find((item) => item.academicYear === currentAcademicYear)?.academicYear
          || index.years[0]?.academicYear
          || currentAcademicYear;
        setSelectedYear(preferred);
        setDetail(await getArchiveYear(preferred));
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : 'تعذر تحميل الأرشيف التاريخي.');
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [currentAcademicYear]);

  function selectYear(academicYear: string) {
    setSelectedYear(academicYear);
    void loadYear(academicYear);
  }

  return (
    <div className="page archive-page">
      <header className="hero-block archive-hero no-print">
        <div>
          <span className="eyebrow">الأرشيف التاريخي</span>
          <h1>ذاكرة أعمال المادة عبر السنوات</h1>
          <p>استعرض سجلات كل عام دراسي من مصادرها الأصلية في وضع قراءة فقط، ثم اطبع حزمة تسليم موحدة عند الحاجة.</p>
        </div>
        <button className="primary-button" onClick={() => detail && window.print()} disabled={!detail || loading}>
          <Icon name="report" /> طباعة حزمة التسليم
        </button>
      </header>

      <section className="archive-year-strip no-print">
        {years.map((item) => (
          <button
            key={item.academicYear}
            className={`archive-year-card ${selectedYear === item.academicYear ? 'active' : ''}`}
            onClick={() => selectYear(item.academicYear)}
          >
            <span>{item.isCurrent ? 'العام الجاري' : 'عام محفوظ في السجلات'}</span>
            <strong>{item.academicYear}</strong>
            <small>{item.totalRecords} سجل رئيسي • {item.documentCount} وثيقة</small>
          </button>
        ))}
      </section>

      {selectedSummary && (
        <section className="archive-scope-note no-print">
          <Icon name="archive" size={18} />
          <div>
            <strong>{selectedSummary.isCurrent ? 'عرض العام الجاري' : 'عرض تاريخي للقراءة'}</strong>
            <span>{selectedSummary.isCurrent ? 'يتحدث هذا العرض تلقائيًا مع السجلات الحالية.' : 'الأرشيف نفسه للقراءة، ويمكن فتح العام في مساحة العمل لإضافة أو استكمال سجلاته من الوحدات الأصلية.'}</span>
          </div>
          {onOpenYear && <button className="ghost-button" onClick={() => onOpenYear(selectedYear)}>فتح هذا العام في مساحة العمل</button>}
        </section>
      )}

      {error && <div className="inline-error no-print"><Icon name="alert" size={18} />{error}</div>}
      {loading && <div className="archive-loading no-print"><span className="spinner"></span><p>جاري تجميع سجل العام...</p></div>}

      {detail && !loading && <ArchiveDocument detail={detail} />}
    </div>
  );
}

function ArchiveDocument({ detail }: { detail: ArchiveYearDetail }) {
  return (
    <article className="archive-document" id="archive-document">
      <header className="archive-document-header">
        <div className="official-report-brand"><span className="brand-mark">م</span><div><strong>مرصد الإنجازات</strong><small>الأرشيف التاريخي وحزمة التسليم</small></div></div>
        <div className="archive-document-meta"><span>{detail.academicYear}</span><span>{detail.isCurrent ? 'العام الجاري' : 'سجل تاريخي'}</span><span>{formatGenerated(detail.generatedAt)}</span></div>
      </header>

      <section className="archive-document-title">
        <span className="eyebrow">حزمة عام دراسي</span>
        <h1>أرشيف أعمال المادة</h1>
        <p>ملخص تشغيلي موحد للسجلات المرتبطة بالعام الدراسي {detail.academicYear}. الأرقام أدناه مشتقة من البيانات المسجلة ولا تُستكمل بالتخمين.</p>
      </section>

      <section className="archive-metrics">
        <ArchiveMetric label="السجلات الرئيسية" value={detail.totalRecords} detail="عبر الوحدات التشغيلية" />
        <ArchiveMetric label="المعلمون المرتبطون" value={detail.teacherCount} detail="بحسب علاقات السجلات" />
        <ArchiveMetric label="الوثائق" value={detail.sourceCounts.documents || 0} detail="ملفات مرتبطة بالعام" />
        <ArchiveMetric label="القرارات" value={detail.sourceCounts.decisions || 0} detail="قرارات الاجتماعات" />
      </section>

      <section className="archive-coverage-grid">
        {detail.coverage.map((item) => (
          <article key={item.id} className="archive-coverage-card">
            <span>{item.label}</span>
            <strong>{item.count}</strong>
            <small>{item.detail}</small>
          </article>
        ))}
      </section>

      <section className="archive-section archive-teachers-section">
        <div className="archive-section-title"><div><span className="eyebrow">الارتباط المهني</span><h2>المعلمون المرتبطون بسجلات العام</h2></div></div>
        {detail.teachers.length ? (
          <div className="archive-teacher-grid">
            {detail.teachers.map((teacher) => (
              <article key={teacher.id}>
                <span className="avatar">{teacher.name.trim().charAt(0) || 'م'}</span>
                <div><strong>{teacher.name}</strong><small>{teacher.subject}</small></div>
                <b>{teacher.linkedRecords} ارتباطات</b>
              </article>
            ))}
          </div>
        ) : <div className="report-empty-row">لا توجد روابط معلمين ضمن هذا العام.</div>}
      </section>

      {detail.sections.map((section) => (
        <section className="archive-section" key={section.id}>
          <div className="archive-section-title"><h2>{section.title}</h2>{section.description && <p>{section.description}</p>}</div>
          {section.rows.length ? (
            <div className="official-report-table-wrap">
              <table>
                <thead><tr>{section.columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
                <tbody>{section.rows.map((row, index) => <tr key={`${section.id}-${index}`}>{section.columns.map((column) => <td key={column.key}>{formatCell(row[column.key])}</td>)}</tr>)}</tbody>
              </table>
            </div>
          ) : <div className="report-empty-row">لا توجد سجلات ضمن هذا القسم في العام المحدد.</div>}
        </section>
      ))}

      <footer className="archive-document-footer">
        <div><strong>حدود الأرشيف</strong><span>المعلمون محسوبون من ارتباطهم بالسجلات، وليس باعتبار القائمة الحالية سجلًا تاريخيًا لطاقم كل سنة.</span></div>
        <div><strong>مصدر الحقيقة</strong><span>هذه الحزمة قراءة موحدة للسجلات الأصلية ولا تنشئ نسخة بيانات موازية.</span></div>
      </footer>
    </article>
  );
}

function ArchiveMetric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return <article><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
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
