// 通用：无内容则空函数
window.apiGet = function(url) {
  return fetch(url).then(function(r) { return r.json(); });
};
window.apiPost = function(url, data) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data || {})
  }).then(function(r) { return r.json(); });
};
window.apiDelete = function(url) {
  return fetch(url, { method: 'DELETE' }).then(function(r) { return r.json(); });
};
