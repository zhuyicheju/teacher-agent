(function(){
	// 状态
	let selectedThreadId = null;
	let selectedThreadTitle = '';
	let selectedDocumentId = null;
	const drafts = {};
	const draftKeyFor = id => id ? `t_${id}` : '__new__';

	// 简单请求包装（返回 JSON 或抛错）
	const reqJson = (url, opts) =>
		fetch(url, opts).then(r => {
			if (r.ok) return r.json();
			return r.text().then(t => { throw t || { error: '请求失败' }; });
		});

	// DOM 工具
	const el = (tag, cls, html) => { const d = document.createElement(tag); if (cls) d.className = cls; if (html!=null) d.innerHTML = html; return d; };
	const escapeHtml = s => String(s || '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

	// 渲染列表（会话 / 文档）
	function renderList(containerId, items, type) {
		const container = document.getElementById(containerId);
		container.innerHTML = '';
		if (!items || items.length === 0) {
			container.textContent = type === 'threads' ? '无会话，点击“新建会话”开始。' : '未上传文件';
			return;
		}
		const frag = document.createDocumentFragment();
		items.forEach(it => {
			const title = it.title || it.filename || '(无标题)';
			const meta = it.created_at || (`分段: ${it.segment_count || 0} · ${it.stored_at || ''}`);
			const div = el('div', `${type === 'threads' ? 'thread-item' : 'doc-item'}${String(it.id) === String(selectedThreadId) ? ' active' : ''}`,
				`<div><strong>#${it.id}</strong> ${escapeHtml(title)}</div><div style="font-size:12px;color:#666">${escapeHtml(meta)}</div>`);
			div.dataset.id = it.id;
			// 删除按钮（由事件委托处理，使用 data-action 标识）
			const delBtn = el('button', 'item-delete-btn', '删除');
			delBtn.title = type === 'threads' ? '删除会话' : '删除文件';
			delBtn.dataset.action = 'delete';
			div.appendChild(delBtn);
			frag.appendChild(div);
		});
		container.appendChild(frag);
	}

	// 加载会话
	function loadThreads(){
		const list = document.getElementById('threadList');
		list.textContent = '加载中...';
		reqJson('/threads').then(j => renderList('threadList', j.items, 'threads'))
		.catch(e => { list.textContent = '加载失败'; console.error(e); });
	}

	// 加载文件
	function loadDocuments(){
		const div = document.getElementById('docList');
		div.textContent = '加载中...';
		reqJson('/my_documents').then(j => renderList('docList', j.items, 'docs'))
		.catch(e => { div.textContent = '加载失败'; console.error(e); });
	}

	// 选择会话
	function selectThread(id, title){
		drafts[draftKeyFor(selectedThreadId)] = document.getElementById('question').value;
		selectedThreadId = id;
		selectedThreadTitle = title || '';
		document.getElementById('currentThread').textContent = `#${id} ${selectedThreadTitle}`;
		document.getElementById('question').value = drafts[draftKeyFor(selectedThreadId)] || '';
		loadThreads();
		loadMessages(id);
	}

	// 选择文档并展示分段
	async function selectDocument(docId){
		selectedDocumentId = docId;
		Array.from(document.getElementsByClassName('doc-item')).forEach(el => el.classList.toggle('active', String(el.dataset.id) === String(docId)));
		const segDiv = document.getElementById('segments');
		segDiv.textContent = '加载分段中...';
		try {
			const resp = await reqJson(`/my_documents/${encodeURIComponent(docId)}/segments`);
			const segs = resp.segments || [];
			if (!segs.length) { segDiv.textContent = '该文档无分段'; return; }
			segDiv.innerHTML = '';
			segs.forEach(s => {
				const item = el('div', 'segment');
				item.innerHTML = `<div style="font-size:12px;color:#666">#${s.index} · vec:${s.vector_id}</div><div>${escapeHtml(s.preview)}</div>`;
				segDiv.appendChild(item);
			});
		} catch (e) {
			console.error(e);
			segDiv.textContent = '加载分段失败';
		}
	}

	// 加载消息
	function loadMessages(threadId){
		const msgDiv = document.getElementById('messages');
		msgDiv.textContent = '加载消息中...';
		reqJson(`/threads/${encodeURIComponent(threadId)}/messages`).then(j => {
			if (j.error) { msgDiv.textContent = `错误: ${j.error}`; return; }
			const items = j.messages || [];
			if (!items.length) { msgDiv.innerHTML = '该会话暂无消息'; return; }
			msgDiv.innerHTML = '';
			items.forEach(m => {
				const wrapper = el('div', 'msg ' + (m.role === 'user' ? 'user' : 'assistant'));
				const meta = el('div', 'msg-meta', `${m.role} · ${m.created_at || ''}`);
				const body = el('div', 'msg-body');
				if (m.role === 'assistant') {
					try {
						const rawHtml = marked.parse(m.content || '');
						body.innerHTML = DOMPurify.sanitize(rawHtml);
						body.querySelectorAll('pre code').forEach(b => { try { hljs.highlightElement(b); } catch (_) {} });
					} catch (_) { body.textContent = m.content || ''; }
				} else {
					body.textContent = m.content || '';
				}
				wrapper.appendChild(meta); wrapper.appendChild(body); msgDiv.appendChild(wrapper);
			});
			msgDiv.scrollTop = msgDiv.scrollHeight;
		}).catch(err => { console.error(err); msgDiv.textContent = '加载消息失败'; });
	}

	// 统一删除处理（会话 / 文档）
	async function handleDelete(type, id, domNode){
		if (!confirm(`确认删除 ${type === 'threads' ? '会话' : '文件'} #${id}？此操作不可恢复。`)) return;
		try {
			const url = type === 'threads' ? `/threads/${encodeURIComponent(id)}` : `/my_documents/${encodeURIComponent(id)}`;
			const resp = await fetch(url, { method: 'DELETE' });
			const j = await resp.json();
			if (resp.ok && j.success) {
				if (domNode && domNode.parentNode) domNode.parentNode.removeChild(domNode);
				if (type === 'threads' && String(selectedThreadId) === String(id)) {
					selectedThreadId = null;
					document.getElementById('currentThread').textContent = '无（新建或选择会话）';
					document.getElementById('messages').innerHTML = '请选择或新建会话以查看消息';
				}
				if (type === 'docs' && String(selectedDocumentId) === String(id)) {
					selectedDocumentId = null;
					document.getElementById('segments').innerHTML = '请选择左侧文件查看分段预览';
				}
				if (type === 'threads') loadThreads(); else loadDocuments();
			} else {
				alert('删除失败：' + (j.error || JSON.stringify(j)));
			}
		} catch (e) { console.error(e); alert('删除请求失败'); }
	}

	// 提交问题并处理 SSE（支持回车传入 inputText）
	async function askQuestion(inputText){
		const qElem = document.getElementById('question');
		const question = (typeof inputText === 'string' && inputText !== null) ? inputText.trim() : qElem.value.trim();
		if (!question) { alert('请输入问题'); return; }

		// 确保有会话
		if (!selectedThreadId) {
			const resp = await fetch('/threads', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({title: ''}) });
			const j = await resp.json();
			if (!j.thread_id) { alert('创建会话失败'); return; }
			const oldDraft = drafts['__new__'] || '';
			selectedThreadId = j.thread_id; selectedThreadTitle = '';
			if (oldDraft) drafts[draftKeyFor(selectedThreadId)] = oldDraft;
			delete drafts['__new__'];
			document.getElementById('currentThread').textContent = `#${selectedThreadId}`;
			loadThreads();
		}

		const streamThreadId = selectedThreadId;
		const msgDiv = document.getElementById('messages');

		// append user
		const userWrap = el('div', 'msg user');
		userWrap.appendChild(el('div','msg-meta', `user · ${new Date().toLocaleString()}`));
		userWrap.appendChild(el('div','msg-body', escapeHtml(question)));
		msgDiv.appendChild(userWrap);

		// append assistant placeholder
		const assistantWrap = el('div', 'msg assistant');
		const assistantMeta = el('div','msg-meta','assistant · 正在回答...');
		const assistantBody = el('div','msg-body','');
		assistantWrap.appendChild(assistantMeta); assistantWrap.appendChild(assistantBody); msgDiv.appendChild(assistantWrap); msgDiv.scrollTop = msgDiv.scrollHeight;

		// 发起 SSE
		const url = `/ask?question=${encodeURIComponent(question)}&thread_id=${encodeURIComponent(streamThreadId)}`;
		const es = new EventSource(url);
		let full = '';
		es.onmessage = (event) => {
			if (event.data === '[DONE]') {
				es.close();
				delete drafts[draftKeyFor(streamThreadId)];
				qElem.value = '';
				loadThreads();
				assistantMeta.textContent = `assistant · ${new Date().toLocaleString()}`;
				setTimeout(()=>loadMessages(selectedThreadId), 300);
				return;
			}
			try {
				const data = JSON.parse(event.data);
				if (data.error) { assistantBody.textContent = `错误: ${String(data.error)}`; es.close(); return; }
				if (data.content) {
					full += data.content;
					try {
						const rawHtml = marked.parse(full);
						assistantBody.innerHTML = DOMPurify.sanitize(rawHtml);
						assistantBody.querySelectorAll('pre code').forEach(b => { try { hljs.highlightElement(b); } catch (_) {} });
						msgDiv.scrollTop = msgDiv.scrollHeight;
					} catch (e) { assistantBody.textContent = full; msgDiv.scrollTop = msgDiv.scrollHeight; }
				}
			} catch (e) { console.error('解析 SSE 数据失败', e); }
		};
		es.onerror = () => { es.close(); assistantBody.textContent = '连接出错，请重试'; };
	}

	// 新建会话（通过 POST /threads）
	async function createThreadPrompt(){
		const title = prompt('输入会话标题（可空）：', '');
		try {
			const j = await reqJson('/threads', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({title: title || ''}) });
			if (j.thread_id) {
				selectedThreadId = j.thread_id; selectedThreadTitle = title || '';
				document.getElementById('currentThread').textContent = `#${selectedThreadId} ${selectedThreadTitle}`;
				document.getElementById('question').value = drafts[draftKeyFor(selectedThreadId)] || '';
				loadThreads(); loadMessages(selectedThreadId);
			} else alert('创建失败');
		} catch (e) { alert('请求失败'); console.error(e); }
	}

	// 文件上传（尝试 POST 到 /my_documents）
	async function uploadFile(){
		const input = document.getElementById('fileInput');
		if (!input || !input.files || input.files.length === 0) { alert('请选择文件'); return; }
		const f = input.files[0];
		const form = new FormData();
		form.append('file', f);
		const respDiv = document.getElementById('uploadResponse');
		try {
			const r = await fetch('/my_documents', { method: 'POST', body: form });
			const j = await r.json();
			if (r.ok && j.success) {
				if (respDiv) { respDiv.style.display = 'block'; respDiv.textContent = '上传成功'; }
				loadDocuments();
			} else {
				if (respDiv) { respDiv.style.display = 'block'; respDiv.textContent = '上传失败: ' + (j.error || JSON.stringify(j)); }
			}
		} catch (e) {
			console.error(e);
			if (respDiv) { respDiv.style.display = 'block'; respDiv.textContent = '上传请求失败'; }
		}
	}

	// 事件委托：左侧选择与删除
	document.addEventListener('click', (e) => {
		const threadNode = e.target.closest('.thread-item');
		if (threadNode && document.getElementById('threadList').contains(threadNode)) {
			const id = threadNode.dataset.id;
			if (e.target.dataset.action === 'delete') return handleDelete('threads', id, threadNode);
			selectThread(id, threadNode.querySelector('div') ? threadNode.querySelector('div').textContent.replace(/^#\d+\s*/, '') : '');
		}
		const docNode = e.target.closest('.doc-item');
		if (docNode && document.getElementById('docList').contains(docNode)) {
			const id = docNode.dataset.id;
			if (e.target.dataset.action === 'delete') return handleDelete('docs', id, docNode);
			selectDocument(id);
		}
	});

	// 输入框回车行为（Shift+Enter 换行，Enter 提交且清空）
	document.addEventListener('DOMContentLoaded', () => {
		const q = document.getElementById('question');
		if (!q) return;
		q.value = drafts['__new__'] || '';
		q.addEventListener('input', (e) => drafts[draftKeyFor(selectedThreadId)] = e.target.value);
		q.addEventListener('keydown', (e) => {
			if (e.key === 'Enter' && !e.shiftKey) {
				e.preventDefault();
				const text = (e.target.value || '').trim();
				if (!text) return;
				drafts[draftKeyFor(selectedThreadId)] = '';
				e.target.value = '';
				askQuestion(text);
			}
		});
		// 初始加载
		loadThreads(); loadDocuments();
	});

	// 暴露到全局供页面按钮调用（保持原按钮可用性）
	window.loadThreads = loadThreads;
	window.loadDocuments = loadDocuments;
	window.createThreadPrompt = createThreadPrompt;
	window.askQuestion = askQuestion;
	window.uploadFile = uploadFile;

})();
