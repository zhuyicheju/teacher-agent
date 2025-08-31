(function () {
  function showMsg(el, text) {
    if (!el) return;
    el.textContent = text || '';
  }

  async function postJson(url, data) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
      body: JSON.stringify(data)
    });
    const json = await res.json().catch(() => ({}));
    return { res, json };
  }

  document.addEventListener('DOMContentLoaded', () => {
    const loginBtn = document.getElementById('login-btn');
    const registerBtn = document.getElementById('register-btn');

    if (loginBtn) {
      const form = loginBtn.closest('form') || document.querySelector('form.auth-form');
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = loginBtn;
        const msgEl = document.getElementById('msg');
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;

        showMsg(msgEl, '');
        if (!username || !password) {
          showMsg(msgEl, '请输入用户名和密码');
          return;
        }

        btn.disabled = true;
        const prev = btn.textContent;
        btn.textContent = '登录中...';

        try {
          const { res, json } = await postJson('/login', { username, password });
          if (res.ok && json && json.success) {
            window.location = '/';
          } else {
            showMsg(msgEl, '错误: ' + (json && json.error ? json.error : '用户名或密码错误'));
          }
        } catch (err) {
          showMsg(msgEl, '请求失败，请检查网络');
        } finally {
          btn.disabled = false;
          btn.textContent = prev;
        }
      });
    }

    if (registerBtn) {
      const form = registerBtn.closest('form') || document.querySelector('form.auth-form');
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = registerBtn;
        const msgEl = document.getElementById('msg');
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;

        showMsg(msgEl, '');
        if (!username || password.length < 6) {
          showMsg(msgEl, '请填写有效的用户名并确保密码至少6位');
          return;
        }

        btn.disabled = true;
        const prev = btn.textContent;
        btn.textContent = '注册中...';

        try {
          const { json } = await postJson('/register', { username, password });
          if (json && json.success) {
            window.location = '/';
          } else {
            showMsg(msgEl, '错误: ' + (json && json.error ? json.error : '注册失败，请重试'));
          }
        } catch (err) {
          showMsg(msgEl, '请求失败，请检查网络');
        } finally {
          btn.disabled = false;
          btn.textContent = prev;
        }
      });
    }
  });
})();
