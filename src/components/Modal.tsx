import type { ReactNode } from 'react';
import { Icon } from './Icon';

export function Modal({ open, onClose, children, compact = false, wide = false }: { open: boolean; onClose: () => void; children: ReactNode; compact?: boolean; wide?: boolean }) {
  if (!open) return null;
  return (
    <div className="modal-layer" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className={`modal-card ${compact ? 'compact' : ''} ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true">
        <button className="icon-button modal-close" type="button" onClick={onClose} aria-label="إغلاق">
          <Icon name="close" size={19} />
        </button>
        {children}
      </section>
    </div>
  );
}
