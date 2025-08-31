(function(){
	// 状态
	let selectedThreadId = null;
	let selectedThreadTitle = '';
	let selectedDocumentId = null;
	const drafts = {};
	const draftKeyFor = id => id ? `t_${id}` : '__new__';

	// 新增：跟踪正在生成答案的流（按 threadId），以及辅助函数控制输入禁用
	const activeStreams = {}; // threadId -> { es, wrapper, meta, body }

	function setSendingDisabled(disabled) {
		const q = document.getElementById('question');
		if (q) q.disabled = disabled;
		// 也尝试禁用常见的发送按钮（如果页面存在的话）
		document.querySelectorAll('.send-btn, button[data-action="send"], #sendBtn').forEach(b => b.disabled = disabled);
	}

	function getBackgroundStreamsContainer() {
		let bg = document.getElementById('backgroundStreams');
		if (!bg) {
			bg = document.createElement('div');
			bg.id = 'backgroundStreams';
			bg.style.display = 'none'; // 隐藏，保留 DOM 节点以免被垃圾回收
			document.body.appendChild(bg);
		}
		return bg;
	}

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
		// 解析为 Date 对象
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
		// 统一转换逻辑：先得到 UTC 毫秒，再加上目标时区偏移（小时）
		const utcMs = d.getTime() - (d.getTimezoneOffset() * 60000);
		const targetMs = utcMs + (tzOffset * 3600000);
		const shifted = new Date(targetMs);
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
			// 对于文档列表（type === 'docs'）始终显示后端的 filename（源文件名）
			let title;
			if (type === 'docs') {
				title = it.filename || '(无标题)';
			} else {
				// threads 使用 title 作为会话显示（若无则回退）
				title = (it.title && it.title.trim()) ? it.title : (it.filename || '(无标题)');
			}

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

		// 切换上传区域的显示状态
		toggleUploadSection();

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
			msgDiv.innerHTML = '';

			if (!items.length) { msgDiv.innerHTML = '该会话暂无消息'; 
				// 如果该会话有正在生成的流，确保将其放回可见位置
				const active = activeStreams[String(threadId)];
				if (active && active.wrapper && !msgDiv.contains(active.wrapper)) msgDiv.appendChild(active.wrapper);
				return;
			}
			items.forEach(m => {
				const wrapper = el('div', 'msg ' + (m.role === 'user' ? 'user' : 'assistant'));
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

			// 将当前会话的流（若存在）恢复到 messages 末尾
			const activeCurrent = activeStreams[String(threadId)];
			if (activeCurrent && activeCurrent.wrapper) {
				if (!msgDiv.contains(activeCurrent.wrapper)) msgDiv.appendChild(activeCurrent.wrapper);
			}

			// 将其它会话的流移动到后台容器以避免被清空，但保留 DOM 以继续生成
			const bg = getBackgroundStreamsContainer();
			Object.keys(activeStreams).forEach(k => {
				if (String(k) !== String(threadId)) {
					const a = activeStreams[k];
					if (a && a.wrapper && msgDiv.contains(a.wrapper)) bg.appendChild(a.wrapper);
				}
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
	// - 如果已有正在生成的答案，禁止再次发送
	// - 将正在生成的 assistant 占位保存到 activeStreams，切换会话时移动到后台容器，仍保持生成不中断
	async function askQuestion(inputText) {
		const qElem = document.getElementById('question');
		const question = (typeof inputText === 'string' && inputText !== null) ? inputText.trim() : qElem.value.trim();
		if (!question) {
			alert('请输入问题');
			return;
		}

		// 禁止在已有生成中再次发送问题（以保证单次生成期间 UI 禁用）
		if (Object.keys(activeStreams).length > 0) {
			alert('当前正在生成答案，请等待生成完成后再发送新问题。');
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

		// 记录为正在生成的流，禁用输入
		activeStreams[String(streamThreadId)] = { wrapper: assistantWrap, meta: assistantMeta, body: assistantBody, es: null };
		setSendingDisabled(true);

		// 发起 SSE（EventSource）
		const url = `/ask?question=${encodeURIComponent(question)}&thread_id=${encodeURIComponent(streamThreadId)}`;
		const es = new EventSource(url);
		activeStreams[String(streamThreadId)].es = es;
		let full = '';
		es.onmessage = (event) => {
			if (event.data === '[DONE]') {
				try { es.close(); } catch (_) {}
				// 清理 activeStreams 条目并恢复输入
				delete activeStreams[String(streamThreadId)];
				setSendingDisabled(false);
				delete drafts[draftKeyFor(streamThreadId)];
				if (qElem) qElem.value = '';
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
					try { es.close(); } catch (_) {}
					delete activeStreams[String(streamThreadId)];
					setSendingDisabled(false);
					return;
				}
				if (data.content) {
					full += data.content;
					try {
						const rawHtml = marked.parse(full);
						assistantBody.innerHTML = DOMPurify.sanitize(rawHtml);
						assistantBody.querySelectorAll('pre code').forEach(b => { try { hljs.highlightElement(b); } catch (_) {} });
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
			try { es.close(); } catch (_) {}
			assistantBody.textContent = '连接出错，请重试';
			delete activeStreams[String(streamThreadId)];
			setSendingDisabled(false);
		};
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
				
				// 显示上传区域
				toggleUploadSection();
				
				loadThreads(); 
				loadMessages(selectedThreadId);
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

	// 新增：控制上传区域显示/隐藏的函数
	function toggleUploadSection() {
		const uploadSection = document.querySelector('.file-picker');
		const uploadTitle = document.querySelector('.list-section:last-child h4');
		const uploadResponse = document.getElementById('uploadResponse');
		
		if (!selectedThreadId) {
			// 没有选择会话时隐藏上传区域
			if (uploadSection) uploadSection.style.display = 'none';
			if (uploadTitle) uploadTitle.style.display = 'none';
			if (uploadResponse) uploadResponse.style.display = 'none';
		} else {
			// 选择了会话时显示上传区域
			if (uploadSection) uploadSection.style.display = 'block';
			if (uploadTitle) uploadTitle.style.display = 'block';
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
		marked.setOptions({
			breaks: false, // 设置为 false，单个换行符不会转换为 <br>
			gfm: true,     // 使用 GitHub Flavored Markdown
			// 其他配置...
		});
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

		// 新增：当用户在文件选择器选中文件时，立即更新左侧显示的文件名并重置响应提示
		const fileInput = document.getElementById('fileInput');
		const fileNameSpan = document.getElementById('fileName');
		const uploadResponse = document.getElementById('uploadResponse');
		if (fileInput) {
			fileInput.addEventListener('change', (ev) => {
				const f = ev.target.files && ev.target.files[0];
				if (f) {
					if (fileNameSpan) fileNameSpan.textContent = f.name;
					// 清除之前的上传提示，避免误导
					if (uploadResponse) { uploadResponse.style.display = 'none'; uploadResponse.textContent = ''; }
				} else {
					if (fileNameSpan) fileNameSpan.textContent = '未选择文件';
				}
			});
		}

		// 已移除页面中始终显示的“管理员”按钮。
		// 管理员应通过专用的管理员登录页面 /admin_login 登录后进入管理员界面

		// 根据是否有对话决定是否显示上传区域
		toggleUploadSection();

		// 初始加载
		loadThreads();
		loadDocuments();
	});

	// 管理面板相关：在 /admin 页面会调用 openAdminPanel()
	window.openAdminPanel = function() {
		const root = document.getElementById('admin-root') || document.body;
		root.innerHTML = '';
		const container = el('div', 'admin-panel', '<h2>管理员界面</h2>');
		const controls = el('div', '', '<button id="reloadThreads" class="btn">刷新会话</button> <button id="reloadDocs" class="btn">刷新文档</button>');
		container.appendChild(controls);
		const threadsDiv = el('div', 'admin-threads', '<h3>会话列表</h3><div id="adminThreads">加载中...</div>');
		const docsDiv = el('div', 'admin-docs', '<h3>文档列表</h3><div id="adminDocs">加载中...</div>');
		container.appendChild(threadsDiv);
		container.appendChild(docsDiv);
		root.appendChild(container);

		document.getElementById('reloadThreads').onclick = loadAdminThreads;
		document.getElementById('reloadDocs').onclick = loadAdminDocuments;

		loadAdminThreads();
		loadAdminDocuments();
	};

	async function loadAdminThreads() {
		const wrap = document.getElementById('adminThreads');
		wrap.textContent = '加载中...';
		try {
			const j = await reqJson('/admin/api/threads');
			const items = j.items || [];
			if (!items.length) { wrap.textContent = '无会话'; return; }
			wrap.innerHTML = '';
			items.forEach(t => {
				// 使用 formatTimestamp 统一显示为 UTC+8
				const timeText = t.created_at ? formatTimestamp(t.created_at) : '';
				const div = el('div', 'admin-thread-item', `<strong>${escapeHtml(t.title||('(no title)'))}</strong> · ${escapeHtml(t.username)} · ${escapeHtml(timeText)}`);
				const del = el('button', 'btn btn-danger btn-sm', '删除');
				del.onclick = async () => {
					if (!confirm(`确认删除会话 ${t.id} 及其下所有知识？此操作不可恢复。`)) return;
					try {
						const r = await fetch(`/admin/api/threads/${encodeURIComponent(t.id)}`, { method: 'DELETE' });
						const res = await r.json();
						if (r.ok && res.success) {
							loadAdminThreads();
							loadAdminDocuments();
						} else {
							alert('删除失败：' + (res.error || JSON.stringify(res)));
						}
					} catch (e) { console.error(e); alert('请求失败'); }
				};
				div.appendChild(del);
				wrap.appendChild(div);
			});
		} catch (e) {
			console.error(e);
			wrap.textContent = '加载失败';
		}
	}

	async function loadAdminDocuments() {
		const wrap = document.getElementById('adminDocs');
		wrap.textContent = '加载中...';
		try {
			const j = await reqJson('/admin/api/documents');
			const items = j.items || [];
			if (!items.length) { wrap.textContent = '无文档'; return; }
			wrap.innerHTML = '';
			items.forEach(d => {
				const div = el('div', 'admin-doc-item', `${escapeHtml(d.filename||'(no name)')} · ${escapeHtml(d.username)} · 线程:${escapeHtml(String(d.thread_id||''))}`);
				const del = el('button', 'btn btn-danger btn-sm', '删除');
				del.onclick = async () => {
					if (!confirm(`确认删除文档 ${d.id}？此操作不可恢复。`)) return;
					try {
						const r = await fetch(`/admin/api/documents/${encodeURIComponent(d.id)}`, { method: 'DELETE' });
						const res = await r.json();
						if (r.ok && res.success) {
							loadAdminDocuments();
							loadAdminThreads();
						} else {
							alert('删除失败：' + (res.error || JSON.stringify(res)));
						}
					} catch (e) { console.error(e); alert('请求失败'); }
				};
				div.appendChild(del);
				wrap.appendChild(div);
			});
		} catch (e) {
			console.error(e);
			wrap.textContent = '加载失败';
		}
	}
	
	// 暴露到全局供页面按钮调用（确保页面可以调用这些函数）
	window.loadThreads = loadThreads;
	window.loadDocuments = loadDocuments;
	window.createThreadPrompt = createThreadPrompt;
	window.askQuestion = askQuestion;
	window.uploadFile = uploadFile;

})(); // 结束自执行函数

