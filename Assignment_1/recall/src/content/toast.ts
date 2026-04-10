/**
 * Tiny non-intrusive toast. Used once per page when an article is first
 * saved to Recall, then auto-dismisses. Shadow DOM so the host page can't
 * style us into oblivion.
 */
export function showSavedToast(): void {
  const host = document.createElement('div');
  host.id = 'recall-toast-host';
  host.style.position = 'fixed';
  host.style.bottom = '16px';
  host.style.right = '16px';
  host.style.zIndex = '2147483647';
  host.style.pointerEvents = 'none';
  document.documentElement.appendChild(host);

  const shadow = host.attachShadow({ mode: 'open' });
  shadow.innerHTML = `
    <style>
      :host { all: initial; }
      .toast {
        font: 12px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background: rgba(20, 24, 32, 0.92);
        color: #fff;
        padding: 8px 12px 8px 10px;
        border-radius: 8px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
        display: inline-flex;
        align-items: center;
        gap: 8px;
        opacity: 0;
        transform: translateY(8px);
        transition: opacity 180ms ease, transform 180ms ease;
        pointer-events: auto;
      }
      .toast.visible { opacity: 1; transform: translateY(0); }
      .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #4ade80;
        flex-shrink: 0;
      }
      .label { font-weight: 500; }
      .meta { color: #9ca3af; }
    </style>
    <div class="toast">
      <span class="dot"></span>
      <span class="label">Saved to Recall</span>
      <span class="meta">· searchable from the toolbar</span>
    </div>
  `;

  const toast = shadow.querySelector('.toast') as HTMLElement;
  // Force layout, then transition in.
  toast.getBoundingClientRect();
  toast.classList.add('visible');

  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => host.remove(), 250);
  }, 2200);
}
