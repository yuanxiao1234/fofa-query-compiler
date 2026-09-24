let csrfToken = null;
async function status() {
  const response = await fetch('/api/v1/status');
  const data = await response.json();
  csrfToken = data.csrf_token;
  return data;
}
async function poll() {
  try { await status(); } catch (_) { /* local service may be restarting */ }
}
status();
setInterval(poll, 2000);
document.querySelectorAll('[data-filter]').forEach((input) => {
  input.addEventListener('input', () => {
    document.querySelectorAll('[data-question]').forEach((row) => {
      row.hidden = !row.dataset.question.toLowerCase().includes(input.value.toLowerCase());
    });
  });
});
document.querySelectorAll('[data-json-form]').forEach((form) => {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(form));
    const response = await fetch(form.dataset.endpoint, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken}, body: JSON.stringify(payload)});
    document.querySelector('[data-feedback]').textContent = response.ok ? '保存成功' : '操作失败';
  });
});
document.querySelectorAll('[data-api-form]').forEach((form) => {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const response = await fetch(form.action, {method: 'POST', headers: {'X-CSRF-Token': csrfToken}, body: new FormData(form)});
    document.querySelector('[data-feedback]').textContent = response.ok ? '导入成功' : '导入失败';
  });
});
