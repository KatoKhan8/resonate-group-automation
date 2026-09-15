/* Progressive enhancement only. All permissions, data and verdicts are SSR.
   Mutations use native POST forms: never retry a write or infer its outcome. */
(() => {
  'use strict';
  document.documentElement.classList.add('enhanced');
  const status = document.getElementById('page-status');
  const setStatus = text => { if (status) status.textContent = text; };

  function filterTable(input) {
    const table = document.getElementById(input.dataset.filter);
    if (!table || !table.tBodies[0]) return;
    const q = input.value.trim().toLocaleLowerCase();
    const rows = Array.from(table.tBodies[0].rows);
    let shown = 0;
    rows.forEach(row => {
      row.hidden = !!q && !row.textContent.toLocaleLowerCase().includes(q);
      if (!row.hidden) shown++;
    });
    const count = document.getElementById(input.dataset.filter + '-count');
    if (count) count.textContent = `${shown} of ${rows.length} rows on this page`;
  }

  function setMenu(open) {
    const toggle = document.getElementById('nav-toggle');
    document.body.classList.toggle('nav-open', open);
    const main = document.querySelector('.main');
    if (main) main.inert = open;
    if (toggle) toggle.setAttribute('aria-expanded', String(open));
    if (!open && toggle) toggle.focus();
    if (open) document.querySelector('.nav-close')?.focus();
  }

  // Native navigation remains intact when JS is unavailable. No cached tenant
  // data or optimistic approval state is retained by this enhancement.
  function loading(form) {
    if (form.dataset.submitting === 'true') return false;
    form.dataset.submitting = 'true';
    form.setAttribute('aria-busy', 'true');
    const isRead = (form.method || 'get').toLowerCase() === 'get';
    setStatus(isRead ? 'Loading workspace data…' : 'Submitting. Waiting for the server…');
    document.body.classList.add('is-loading');
    // aria-disabled and the submission guard avoid dropping submitter values
    // from FormData, which native `disabled` would do before submission.
    form.querySelectorAll('button[type="submit"], button:not([type]), input[type="submit"]')
      .forEach(button => button.setAttribute('aria-disabled', 'true'));
    // A download or failed navigation may leave this document on screen.
    // Unlock the UI without asserting success or automatically repeating it.
    window.setTimeout(() => {
      if (form.dataset.submitting !== 'true') return;
      restore();
      setStatus('No new page received. Check the current record before repeating an action.');
    }, 30000);
    return true;
  }

  function restore() {
    document.body.classList.remove('is-loading');
    document.querySelectorAll('[data-submitting]').forEach(form => {
      delete form.dataset.submitting;
      form.removeAttribute('aria-busy');
      form.querySelectorAll('[aria-disabled="true"]').forEach(b => b.removeAttribute('aria-disabled'));
    });
    setStatus('');
  }

  document.addEventListener('submit', event => {
    if (!loading(event.target)) event.preventDefault();
  });
  document.addEventListener('input', event => {
    if (event.target.matches('[data-filter]')) filterTable(event.target);
  });
  document.addEventListener('change', event => {
    const input = event.target;
    if (input.matches('[data-autosubmit]') && input.form) input.form.requestSubmit();
    if (input.matches('[data-upload]')) {
      const label = document.getElementById('upload-filename');
      if (label) label.textContent = input.files.length ? input.files[0].name : 'Choose a CSV or Excel file';
    }
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-nav-toggle], [data-nav-close], [data-dismiss]');
    if (!button) return;
    if (button.matches('[data-nav-toggle]')) setMenu(!document.body.classList.contains('nav-open'));
    else if (button.matches('[data-nav-close]')) setMenu(false);
    else button.closest('[role="status"]')?.remove();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('nav-open')) setMenu(false);
    if (event.key === 'Tab' && document.body.classList.contains('nav-open')) {
      const targets = Array.from(document.querySelectorAll('.side button, .side summary, .side a'))
        .filter(element => element.getClientRects().length);
      const first = targets[0], last = targets[targets.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
      const search = document.getElementById('workspace-search');
      if (search) { event.preventDefault(); search.focus(); }
    }
  });
  const dropzone = document.querySelector('[data-dropzone]');
  if (dropzone) {
    ['dragenter', 'dragover'].forEach(type => dropzone.addEventListener(type, event => {
      event.preventDefault(); dropzone.classList.add('drag-over');
    }));
    ['dragleave', 'drop'].forEach(type => dropzone.addEventListener(type, event => {
      event.preventDefault(); dropzone.classList.remove('drag-over');
    }));
    dropzone.addEventListener('drop', event => {
      const input = dropzone.querySelector('input[type="file"]');
      const files = event.dataTransfer?.files;
      if (!input || !files?.length) return;
      if (files.length !== 1) { setStatus('Choose one file per batch.'); return; }
      input.files = files;
      input.dispatchEvent(new Event('change', {bubbles: true}));
    });
  }
  document.querySelectorAll('[data-filter]').forEach(filterTable);
  window.addEventListener('pageshow', event => {
    if (event.persisted) { window.location.reload(); return; }
    restore();
  });
  window.addEventListener('resize', () => {
    if (window.innerWidth > 1000 && document.body.classList.contains('nav-open')) setMenu(false);
  });
})();
