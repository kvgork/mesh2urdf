export function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}

export function addLinkToSidebar(name) {
  const list = document.getElementById('links-list');
  const hint = list.querySelector('.empty-hint');
  if (hint) hint.remove();

  const item = document.createElement('div');
  item.className = 'link-item';
  item.dataset.name = name;
  item.textContent = name;
  list.appendChild(item);
  updateExportButton();
}

export function updateExportButton() {
  const list = document.getElementById('links-list');
  const hasLinks = list.querySelectorAll('.link-item').length > 0;
  document.getElementById('export-btn').disabled = !hasLinks;
}

export function setUploadLoading(loading) {
  const btn = document.getElementById('upload-btn');
  btn.disabled = loading;
  btn.textContent = loading ? 'Uploading...' : 'Upload';
}

export function init() {
  // Static UI event bindings handled in app.js
  document.getElementById('export-btn').addEventListener('click', () => {
    showToast('Export not yet implemented', 'info');
  });
}
