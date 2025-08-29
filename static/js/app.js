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

	// 时间格式化：将 ISO 时间（可能含微秒）格式化为 "YYYY-MM-DD HH:MM:SS"，使用指定时区（默认 UTC+8）
	function formatTimestamp(ts, tzOffset = 8){
		// 空值处理
		if(!ts && ts !== 0) return '';
		// 如果是 Date 对象直接使用
		let d;
		if (ts instanceof Date) {
			d = ts;
		} else {
			// 处理字符串：去掉微秒部分再解析，保留末尾时区信息（如 Z 或 +08:00）
			try {
				let s = String(ts);
				const dotIdx = s.indexOf('.');
				if (dotIdx !== -1) {
					const tzMatch = s.match(/(Z|[+\-]\d{2}:\d{2})$/);
					const tz = tzMatch ? tzMatch[0] : '';
					s = s.slice(0, dotIdx) + tz;
				}
				d = new Date(s);
				if (isNaN(d)) {
					// 回退：把 T 换成空格并去掉微秒部分
					return String(ts).replace('T',' ').split('.')[0];
				}
			} catch (e) {
				return String(ts);
			}
		}
		// 将时间转换为目标时区的本地表示：通过在 UTC 毫秒上加上目标时区偏移（小时）
		const shiftMs = tzOffset * 3600000;
		const shifted = new Date(d.getTime() + shiftMs);
		// 使用 UTC getters 以避免受客户端本地时区影响
		const pad = n => String(n).padStart(2,'0');
		const Y = shifted.getUTCFullYear();
		const M = pad(shifted.getUTCMonth() + 1);
		const D = pad(shifted.getUTCDate());
		const hh = pad(shifted.getUTCHours());
		const mm = pad(shifted.getUTCMinutes());
		const ss = pad(shifted.getUTCSeconds());
		return `${Y}-${M}-${D} ${hh}:${mm}:${ss}`;
	}

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
			// 仅显示标题，不再以 "#id 标题" 的形式展示
			let title = (it.title && it.title.trim()) ? it.title : (it.filename || '(无标题)');

			if (type === 'threads' && String(it.id) === String(selectedThreadId) && selectedThreadTitle && selectedThreadTitle.trim()) {
				title = selectedThreadTitle;
			}

			const meta = (type === 'threads' ? (it.created_at ? formatTimestamp(it.created_at) : '') : `分段: ${it.segment_count || 0}${it.stored_at ? ' · ' + formatTimestamp(it.stored_at) : ''}`);
			const div = el('div', `${type === 'threads' ? 'thread-item' : 'doc-item'}${String(it.id) === String(selectedThreadId) ? ' active' : ''}`,
				`<div>${escapeHtml(title)}</div><div style="font-size:12px;color:#666">${escapeHtml(meta)}</div>`);
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

	// 加载文件（现在按当前选中会话过滤）
	function loadDocuments(){
		const div = document.getElementById('docList');
		div.textContent = '加载中...';
		const url = selectedThreadId ? `/my_documents?thread_id=${encodeURIComponent(selectedThreadId)}` : '/my_documents';
		reqJson(url).then(j => renderList('docList', j.items, 'docs'))
		.catch(e => { div.textContent = '加载失败'; console.error(e); });
	}

	// 选择会话
	function selectThread(id, title){
		drafts[draftKeyFor(selectedThreadId)] = document.getElementById('question').value;
		selectedThreadId = id;
		selectedThreadTitle = title || '';
		// 仅显示标题；如无标题则显示占位文本
		document.getElementById('currentThread').textContent = selectedThreadTitle ? selectedThreadTitle : '新会话';
		document.getElementById('question').value = drafts[draftKeyFor(selectedThreadId)] || '';

		// 清空文档分段预览
		document.getElementById('segments').innerHTML = '请选择左侧文件查看分段预览';

		loadThreads();
		loadDocuments();
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
				// 使用格式化时间显示
				const metaText = `${m.role} · ${formatTimestamp(m.created_at)}`;
				const meta = el('div', 'msg-meta', metaText);
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
			let url;
			if (type === 'threads') {
				url = `/threads/${encodeURIComponent(id)}`;
			} else {
				// 为文件删除携带当前会话 thread_id 以便后端强校验并在对应命名空间删除向量
				const tid = selectedThreadId ? encodeURIComponent(selectedThreadId) : '';
				url = `/my_documents/${encodeURIComponent(id)}${tid ? ('?thread_id=' + tid) : ''}`;
			}
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
	async function askQuestion(inputText) {
		const qElem = document.getElementById('question');
		const question = (typeof inputText === 'string' && inputText !== null) ? inputText.trim() : qElem.value.trim();
		if (!question) {
			alert('请输入问题');
			return;
		}

		// 确保有会话
		if (!selectedThreadId) {
			const resp = await fetch('/threads', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ title: '' }) // 新建会话时标题为空
			});
			const j = await resp.json();
			if (!j.thread_id) {
				alert('创建会话失败');
				return;
			}
			const oldDraft = drafts['__new__'] || '';
			selectedThreadId = j.thread_id;
			selectedThreadTitle = `对话#${j.thread_id}`; // 临时标题

			if (oldDraft) drafts[draftKeyFor(selectedThreadId)] = oldDraft;
			delete drafts['__new__'];

			document.getElementById('currentThread').textContent = selectedThreadTitle;
			loadThreads();
		}

		const streamThreadId = selectedThreadId;
		const msgDiv = document.getElementById('messages');

		// append user
		const userWrap = el('div', 'msg user');
		userWrap.appendChild(el('div', 'msg-meta', `user · ${formatTimestamp(new Date())}`));
		userWrap.appendChild(el('div', 'msg-body', escapeHtml(question)));
		msgDiv.appendChild(userWrap);

		// append assistant placeholder
		const assistantWrap = el('div', 'msg assistant');
		const assistantMeta = el('div', 'msg-meta', 'assistant · 正在回答...');
		const assistantBody = el('div', 'msg-body', '');
		assistantWrap.appendChild(assistantMeta);
		assistantWrap.appendChild(assistantBody);
		msgDiv.appendChild(assistantWrap);
		msgDiv.scrollTop = msgDiv.scrollHeight;

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
				assistantMeta.textContent = `assistant · ${formatTimestamp(new Date())}`;
				setTimeout(() => loadMessages(selectedThreadId), 300);

				// 仅当标题为“对话#xx”时才生成标题，且只生成一次
				if (selectedThreadTitle && selectedThreadTitle.startsWith('对话#')) {
					fetch('/generate_title', {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({ question })
					})
						.then(res => res.json())
						.then(data => {
							if (data.title) {
								selectedThreadTitle = data.title;
								document.getElementById('currentThread').textContent = selectedThreadTitle;
								
								loadThreads(); // 更新会话列表
							}
						})
						.catch(err => console.error('生成标题失败:', err));
				}

				return;
			}
			try {
				const data = JSON.parse(event.data);
				if (data.error) {
					assistantBody.textContent = `错误: ${String(data.error)}`;
					es.close();
					return;
				}
				if (data.content) {
					full += data.content;
					try {
						const rawHtml = marked.parse(full);
						assistantBody.innerHTML = DOMPurify.sanitize(rawHtml);
						assistantBody.querySelectorAll('pre code').forEach(b => {
							try {
								hljs.highlightElement(b);
							} catch (_) {}
						});
						msgDiv.scrollTop = msgDiv.scrollHeight;
					} catch (e) {
						assistantBody.textContent = full;
						msgDiv.scrollTop = msgDiv.scrollHeight;
					}
				}
			} catch (e) {
				console.error('解析 SSE 数据失败', e);
			}
		};
		es.onerror = () => {
			es.close();
			assistantBody.textContent = '连接出错，请重试';
		};
	}

	// 新增辅助函数：更新会话列表中的标题
	function updateThreadTitleInList(threadId, newTitle) {
		const threadItem = document.querySelector(`.thread-item[data-id="${threadId}"]`);
		if (threadItem) {
			const titleDiv = threadItem.querySelector('div:first-child');
			if (titleDiv) {
				titleDiv.textContent = newTitle;
			}
		}
	}

	// 新建会话（通过 POST /threads）
	async function createThreadPrompt(){
		try {
			const j = await reqJson('/threads', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({title: ''}) });
			if (j.thread_id) {
				selectedThreadId = j.thread_id;
				selectedThreadTitle = `对话#${j.thread_id}`;
				document.getElementById('currentThread').textContent = selectedThreadTitle;
				document.getElementById('question').value = drafts[draftKeyFor(selectedThreadId)] || '';
				loadThreads(); loadMessages(selectedThreadId);
			} else alert('创建失败');
		} catch (e) { alert('请求失败'); console.error(e); }
	}

	// 文件上传（尝试多个候选路径，优先使用页面上的 uploadPath）
	async function uploadFile(){
		const input = document.getElementById('fileInput');
		if (!input || !input.files || input.files.length === 0) { alert('请选择文件'); return; }
		const f = input.files[0];
		const form = new FormData();
		form.append('file', f);
		// 将当前会话 thread_id 一并附加（若存在）
		if (selectedThreadId) form.append('thread_id', String(selectedThreadId));
		const respDiv = document.getElementById('uploadResponse');
		if (respDiv) { respDiv.style.display = 'block'; respDiv.textContent = '准备上传...'; }

		// 解析响应（支持 JSON 或纯文本）
		async function parseResponse(res) {
			const ctype = (res.headers.get('content-type') || '').toLowerCase();
			if (ctype.includes('application/json')) {
				try { return await res.json(); } catch (e) { return { __raw_text_parse_error: true }; }
			} else {
				try { return await res.text(); } catch (e) { return null; }
			}
		}

		// 生成候选路径：仅使用后端专用上传接口，避免误传到其他路径
		const userPath = (document.getElementById('uploadPath') && document.getElementById('uploadPath').value) || '';
		const candidates = [];
		// 页面可自定义路径，但默认优先使用 /upload（knowledge_processor.upload）
		if (userPath) {
			// 允许用户自定义，但把 /upload 放在首位以保证按会话隔离逻辑走
			if (userPath !== '/upload') candidates.push('/upload');
			candidates.push(userPath);
		} else {
			candidates.push('/upload');
		}
		// 不再盲目尝试大量其他旧路径，减少误操作

		const tried = [];
		let lastResult = null;
		try {
			for (const path of candidates) {
				try {
					if (respDiv) respDiv.textContent = `上传到 ${path} ...`;
					const r = await fetch(path, { method: 'POST', body: form });
					const data = await parseResponse(r);
					tried.push({ path, status: r.status, body: typeof data === 'string' ? data.slice(0,1000) : data });

					if (r.ok) {
						// 成功
						if (typeof data === 'object' && data && data.success) {
							if (respDiv) respDiv.textContent = `上传成功（${path}）`;
						} else if (typeof data === 'string' && data.trim()) {
							if (respDiv) respDiv.textContent = `上传成功（响应文本）: ${data.slice(0,300)}`;
						} else {
							if (respDiv) respDiv.textContent = `上传成功（${path}，但返回非标准成功字段）`;
						}
						loadDocuments();
						return;
					} else {
						// 非 2xx，继续尝试下一个（除非是不可重试的严重错误）
						lastResult = { path, status: r.status, data };
						// 若是 404/405 等，继续尝试下一个候选
					}
				} catch (innerE) {
					tried.push({ path, status: 'network-error', body: String(innerE).slice(0,300) });
					lastResult = { path, status: 'network-error', data: String(innerE) };
				}
			}

			// 所有候选路径都尝试完毕仍未成功
			let msg = `上传失败，已尝试 ${candidates.length} 个路径。`;
			if (lastResult) {
				msg += ` 最终响应：HTTP ${lastResult.status}`;
				if (lastResult.data) {
					if (typeof lastResult.data === 'string') msg += ' · ' + lastResult.data.slice(0,1000);
					else msg += ' · ' + (lastResult.data.error || JSON.stringify(lastResult.data));
				}
			}
			msg += '\n建议：确认后端支持 POST Multipart 到上述路径之一；可修改左侧“上传路径”后重试。';
			console.error('上传尝试详情：', tried);
			if (respDiv) {
				// 格式化简短展示并保留候选路径列表
				let html = `<div style="white-space:pre-wrap;">${escapeHtml(msg)}</div><div style="margin-top:8px;font-size:13px;color:var(--muted);">已尝试路径：</div><ul style="font-size:13px;margin:6px 0 0 18px;color:var(--muted);">`;
				tried.forEach(t => {
					const b = typeof t.body === 'string' ? escapeHtml(t.body) : escapeHtml(JSON.stringify(t.body));
					html += `<li>${escapeHtml(t.path)} · ${escapeHtml(String(t.status))}${b ? ' · ' + b.slice(0,200) : ''}</li>`;
				});
				html += '</ul>';
				html += `<div style="margin-top:8px;"><button class="btn btn-ghost btn-sm" onclick="document.getElementById('uploadPath').focus()">编辑上传路径</button> <button class="btn btn-primary btn-sm" onclick="uploadFile()">重试上传</button></div>`;
				respDiv.innerHTML = html;
			}
		} catch (e) {
			console.error('上传请求异常：', e);
			if (respDiv) respDiv.textContent = '上传请求异常：' + (e && e.message ? e.message : String(e));
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
		loadThreads();
		loadDocuments();
	});

	// 暴露到全局供页面按钮调用
	window.loadThreads = loadThreads;
	window.loadDocuments = loadDocuments;
	window.createThreadPrompt = createThreadPrompt;
	window.askQuestion = askQuestion;
	window.uploadFile = uploadFile;

})();
	window.createThreadPrompt = createThreadPrompt;
	window.askQuestion = askQuestion;
	window.uploadFile = uploadFile;
