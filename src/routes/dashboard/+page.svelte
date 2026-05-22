<script lang="ts">
	import { userState } from '$lib/userData.svelte';
	import { toast } from '$lib/toastQueue.svelte';
	import { onMount, onDestroy, tick } from 'svelte';
	import { animate } from 'animejs';
	import { goto } from '$app/navigation';
	import { getUsers, addUser, deleteUser, type UserRecord } from '$lib/userDatabase';
	import { supabase } from '$lib/supabaseClient';
	import { Editor } from '@tiptap/core';
	import StarterKit from '@tiptap/starter-kit';
	import { marked } from 'marked';
	import TurndownService from 'turndown';

	let sidebarNode = $state<HTMLElement | null>(null);
	let mainContentNode = $state<HTMLElement | null>(null);

	// 当前选中的文档索引
	let activeDocIndex = $state(0);

	// 动态文档列表
	let docs = $state<any[]>([]);
	let activeDoc = $derived(docs[activeDocIndex]);

	// Tiptap 绑定
	let editorNode = $state<HTMLElement | null>(null);
	let titleNode = $state<HTMLElement | null>(null);
	let editor = $state<Editor | null>(null);
	let editorShellNode = $state<HTMLElement | null>(null);
	let markdownContent = $state('');
	let editMode = $state<'rich' | 'markdown'>('rich');
	let blockHandleVisible = $state(false);
	let blockHandleTop = $state(0);
	let activeBlockElement = $state<HTMLElement | null>(null);
	let commandMenuOpen = $state(false);
	let commandMenuTop = $state(0);
	let commandMenuLeft = $state(0);
	let slashQuery = $state('');
	let blockHandleLocked = $state(false);
	let markdownPreviewHtml = $state('');

	// 同步状态与定时器
	let syncStatus = $state<'idle' | 'syncing' | 'saved'>('saved');
	let saveTimeout: ReturnType<typeof setTimeout>;

	const turndownService = new TurndownService({
		headingStyle: 'atx',
		bulletListMarker: '-',
		codeBlockStyle: 'fenced'
	});

	const slashCommands = [
		{
			id: 'paragraph',
			label: '正文',
			hint: '切换为普通段落',
			run: () => editor?.chain().focus().setParagraph().run()
		},
		{
			id: 'heading1',
			label: '一级标题',
			hint: '大标题',
			run: () => editor?.chain().focus().toggleHeading({ level: 1 }).run()
		},
		{
			id: 'heading2',
			label: '二级标题',
			hint: '章节标题',
			run: () => editor?.chain().focus().toggleHeading({ level: 2 }).run()
		},
		{
			id: 'heading3',
			label: '三级标题',
			hint: '小节标题',
			run: () => editor?.chain().focus().toggleHeading({ level: 3 }).run()
		},
		{
			id: 'bullet',
			label: '无序列表',
			hint: '项目符号列表',
			run: () => editor?.chain().focus().toggleBulletList().run()
		},
		{
			id: 'ordered',
			label: '有序列表',
			hint: '编号列表',
			run: () => editor?.chain().focus().toggleOrderedList().run()
		},
		{
			id: 'quote',
			label: '引用',
			hint: '强调引用块',
			run: () => editor?.chain().focus().toggleBlockquote().run()
		},
		{
			id: 'codeblock',
			label: '代码块',
			hint: '插入 fenced code block',
			run: () => editor?.chain().focus().toggleCodeBlock().run()
		},
		{
			id: 'divider',
			label: '分割线',
			hint: '插入横向分隔',
			run: () => editor?.chain().focus().setHorizontalRule().run()
		}
	];

	const filteredSlashCommands = $derived.by(() => {
		const query = slashQuery.trim().toLowerCase();
		if (!query) return slashCommands;
		return slashCommands.filter(
			(item) =>
				item.label.toLowerCase().includes(query) || item.hint.toLowerCase().includes(query)
		);
	});

	// 树形折叠状态
	let teamWorkspaceOpen = $state(true);
	let personalNotesOpen = $state(true);

	// 用户管理状态
	let showUserManagement = $state(false);
	let userList = $state<UserRecord[]>([]);
	let newUsername = $state('');
	let newPassword = $state('');
	let newRole = $state<'root' | '管理员' | '用户'>('用户');

	async function refreshUsers() {
		userList = await getUsers();
	}

	async function handleAddUser(e: Event) {
		e.preventDefault();
		if (!newUsername || !newPassword) {
			toast.warning('请输入完整的信息');
			return;
		}
		const res = await addUser({
			username: newUsername,
			password: newPassword,
			role: newRole
		});
		if (res.success) {
			toast.success(res.message);
			newUsername = '';
			newPassword = '';
			newRole = '用户';
			await refreshUsers();
		} else {
			toast.error(res.message);
		}
	}

	async function handleDeleteUser(username: string) {
		if (confirm(`确定要删除用户 "${username}" 吗？`)) {
			const res = await deleteUser(username);
			if (res.success) {
				toast.success(res.message);
				await refreshUsers();
			} else {
				toast.error(res.message);
			}
		}
	}

	// 触发云端自动防抖同步
	function triggerAutoSave() {
		syncStatus = 'syncing';
		clearTimeout(saveTimeout);
		saveTimeout = setTimeout(async () => {
			const currentDoc = docs[activeDocIndex];
			if (!currentDoc) return;

			const { error } = await supabase
				.from('amnesia_docs')
				.update({
					title: currentDoc.title,
					content: currentDoc.content
				})
				.eq('id', currentDoc.id);

			if (error) {
				console.error('Failed to sync doc to Supabase:', error);
				syncStatus = 'idle';
				toast.error('数据同步失败，请检查网络');
			} else {
				syncStatus = 'saved';
			}
		}, 1000);
	}

	function syncMarkdownFromHtml(html: string) {
		markdownContent = turndownService.turndown(html).trim();
		markdownPreviewHtml = html;
	}

	async function applyMarkdownToEditor(markdown: string) {
		if (!editor || !docs[activeDocIndex]) return;

		const parsed = await marked.parse(markdown);
		editor.commands.setContent(parsed, { emitUpdate: false });
		docs[activeDocIndex].content = editor.getHTML();
		markdownPreviewHtml = docs[activeDocIndex].content;
		triggerAutoSave();
	}

	async function handleMarkdownInput(e: Event) {
		const target = e.currentTarget as HTMLTextAreaElement;
		markdownContent = target.value;
		markdownPreviewHtml = await marked.parse(markdownContent);
	}

	function getTopLevelBlock(target: EventTarget | null) {
		if (!editorNode) return null;

		let current: HTMLElement | null =
			target instanceof HTMLElement
				? target
				: target instanceof Text
					? target.parentElement
					: null;
		while (current && current.parentElement) {
			if (current.parentElement === editorNode) {
				return current;
			}
			current = current.parentElement;
		}

		return null;
	}

	function hideBlockHandle() {
		if (blockHandleLocked) return;
		blockHandleVisible = false;
		activeBlockElement = null;
	}

	function updateBlockHandleFromPoint(clientX: number, clientY: number) {
		if (editMode !== 'rich' || !editorShellNode) {
			hideBlockHandle();
			return;
		}

		const hoveredNode = document.elementFromPoint(clientX, clientY);
		const block = getTopLevelBlock(hoveredNode);
		if (!block) {
			hideBlockHandle();
			return;
		}

		const shellRect = editorShellNode.getBoundingClientRect();
		const blockRect = block.getBoundingClientRect();
		blockHandleTop = blockRect.top - shellRect.top + Math.min(blockRect.height / 2, 24);
		activeBlockElement = block;
		blockHandleVisible = true;
	}

	function hideCommandMenu() {
		commandMenuOpen = false;
		slashQuery = '';
	}

	function releaseBlockHandle() {
		blockHandleLocked = false;
		hideBlockHandle();
	}

	function updateSlashMenu() {
		if (!editor || !editorShellNode || editMode !== 'rich') {
			hideCommandMenu();
			return;
		}

		const { state, view } = editor;
		const selectionFrom = state.selection.$from;
		if (!selectionFrom.parent.isTextblock) {
			hideCommandMenu();
			return;
		}

		const beforeCaret = selectionFrom.parent.textContent.slice(0, selectionFrom.parentOffset);
		const slashMatch = beforeCaret.match(/^\/([^\s]*)$/);
		if (!slashMatch) {
			hideCommandMenu();
			return;
		}

		const shellRect = editorShellNode.getBoundingClientRect();
		const caretRect = view.coordsAtPos(state.selection.from);
		commandMenuTop = caretRect.bottom - shellRect.top + 12;
		commandMenuLeft = Math.max(24, caretRect.left - shellRect.left - 12);
		slashQuery = slashMatch[1] ?? '';
		commandMenuOpen = true;
	}

	function clearSlashTrigger() {
		if (!editor) return;
		const { state } = editor;
		const selectionFrom = state.selection.$from;
		const from = selectionFrom.start();
		const to = from + selectionFrom.parentOffset;
		editor.chain().focus().deleteRange({ from, to }).run();
	}

	function runSlashCommand(command: (typeof slashCommands)[number]) {
		clearSlashTrigger();
		command.run();
		hideCommandMenu();
	}

	function openBlockCommandMenu() {
		if (!activeBlockElement || !editor || !editorShellNode) return;

		const shellRect = editorShellNode.getBoundingClientRect();
		const blockRect = activeBlockElement.getBoundingClientRect();
		commandMenuTop = blockRect.top - shellRect.top + blockRect.height / 2 - 12;
		commandMenuLeft = 44;
		slashQuery = '';
		commandMenuOpen = true;

		const pos = editor.view.posAtDOM(activeBlockElement, 0);
		editor.chain().focus().setTextSelection(pos).run();
	}

	function insertBlockBelow() {
		if (!activeBlockElement || !editor) return;

		const pos = editor.view.posAtDOM(activeBlockElement, 0);
		const node = editor.state.doc.nodeAt(pos);
		if (!node) return;

		editor
			.chain()
			.focus()
			.insertContentAt(pos + node.nodeSize, '<p></p>')
			.setTextSelection(pos + node.nodeSize + 1)
			.run();
	}

	async function toggleEditMode(mode: 'rich' | 'markdown') {
		if (mode === editMode) return;

		if (mode === 'markdown') {
			if (editor) {
				syncMarkdownFromHtml(editor.getHTML());
			}
			editMode = 'markdown';
			return;
		}

		await applyMarkdownToEditor(markdownContent);
		editMode = 'rich';
		hideCommandMenu();
		hideBlockHandle();
	}

	// 切换文档
	function handleDocClick(index: number, docTitle: string) {
		if (activeDocIndex === index) return;
		activeDocIndex = index;
		toast.info(`正在打开: ${docTitle}`);

		const currentDoc = docs[index];
		if (currentDoc) {
			// 同步更新大标题的 DOM，避免 Svelte 重绘丢失 contenteditable 的光标位置
			if (titleNode) {
				titleNode.innerText = currentDoc.title;
			}
			// 同步更新 Tiptap 内容
			if (editor) {
				editor.commands.setContent(currentDoc.content, { emitUpdate: false });
			}
			syncMarkdownFromHtml(currentDoc.content);
		}
	}

	// 标题输入响应
	function handleTitleInput(e: Event) {
		const target = e.currentTarget as HTMLElement;
		const newTitle = target.innerText;
		if (docs[activeDocIndex]) {
			docs[activeDocIndex].title = newTitle;
			triggerAutoSave();
		}
	}

	onMount(async () => {
		// 路由保护：如果未登录，自动去登录页
		userState.loadFromLocalStorage();
		if (!userState.session) {
			goto('/login');
			return;
		}

		// 1. 从 Supabase 拉取真正的文档
		const { data, error } = await supabase
			.from('amnesia_docs')
			.select('*')
			.order('id');

		if (error) {
			toast.error('拉取云端文档失败，请检查网络');
			console.error(error);
		} else if (data) {
			docs = data;
			await tick();
		}

		// 2. 初始化 Tiptap 编辑器
		const initialDoc = docs[activeDocIndex];
		if (initialDoc && editorNode) {
			if (titleNode) {
				titleNode.innerText = initialDoc.title;
			}
			syncMarkdownFromHtml(initialDoc.content);

			editor = new Editor({
				element: editorNode,
				extensions: [StarterKit],
				content: initialDoc.content,
				editorProps: {
					attributes: {
						class: 'tiptap'
					}
				},
				onUpdate: ({ editor }) => {
					if (docs[activeDocIndex]) {
						docs[activeDocIndex].content = editor.getHTML();
						if (editMode === 'rich') {
							syncMarkdownFromHtml(docs[activeDocIndex].content);
						}
						triggerAutoSave();
					}
				},
				onTransaction: () => {
					// 强制触发 Svelte5 响应以便刷新工具栏的高亮状态
					editor = editor;
					updateSlashMenu();
				}
			});
		}

		// 3. 首屏骨架滑入动画
		if (sidebarNode) {
			animate(sidebarNode, {
				translateX: [-260, 0],
				duration: 800,
				ease: 'outExpo'
			});
		}

		if (mainContentNode) {
			animate(mainContentNode, {
				opacity: [0, 1],
				translateY: [20, 0],
				duration: 1000,
				delay: 200,
				ease: 'outExpo'
			});
		}

		toast.success('工作台已加载完毕');
		await refreshUsers();
	});

	onDestroy(() => {
		if (editor) {
			editor.destroy();
		}
		clearTimeout(saveTimeout);
	});
</script>

<svelte:head>
	<title>工作台 - Amnesia</title>
</svelte:head>

<div class="flex h-[100dvh] max-h-[100dvh] w-full overflow-hidden bg-[#f7f6f3] text-black/80 text-sm font-sans">
	
	<!-- =================== 左侧 Notion 侧边栏 =================== -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div 
		bind:this={sidebarNode}
		class="w-64 h-full bg-[#f4f4f4] border-r border-black/5 flex flex-col justify-between shrink-0 select-none z-10"
	>
		<div class="flex flex-col overflow-y-auto p-3 space-y-4">
			
			<!-- 用户资料块 -->
			<div class="flex items-center gap-2 p-2 hover:bg-black/5 rounded-xl cursor-pointer transition-all duration-200">
				<div class="w-7 h-7 rounded-lg bg-neutral-900 flex items-center justify-center text-white text-xs font-bold font-mono overflow-hidden">
					{#if userState.avatarUrl}
						<img src={userState.avatarUrl} alt="Avatar" class="w-full h-full object-cover" />
					{:else}
						AM
					{/if}
				</div>
				<div class="flex-1 min-w-0">
					<p class="font-bold text-xs truncate text-black leading-none">
						{userState.session?.user?.username || '游客'}
					</p>
					<p class="text-[9px] text-black/40 font-mono tracking-wider mt-0.5 uppercase">
						{#if userState.session}
							已登录 ({userState.session.user.role})
						{:else}
							游客暂存态
						{/if}
					</p>
				</div>
			</div>

			<!-- 快速导航区 -->
			<div class="space-y-0.5">
				<button 
					type="button"
					onclick={() => toast.info('🔍 检索服务正在筹备中...')}
					class="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-black/5 rounded-lg text-left text-xs font-medium text-black/70 cursor-pointer"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="opacity-60"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0-14 0m18 11l-6-6"/></svg>
					快速检索
				</button>
				
				<button 
					type="button"
					onclick={() => toast.info('⚙️ 设置服务正在建设中...')}
					class="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-black/5 rounded-lg text-left text-xs font-medium text-black/70 cursor-pointer"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="opacity-60"><g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"><path d="M12 14a2 2 0 1 0 0-4a2 2 0 0 0 0 4"/><path d="M14.2 17.95a8.95 8.95 0 0 0 1.95-1.95m.1-5.1a8.95 8.95 0 0 0-1.95-1.95m-5.1-.1A8.95 8.95 0 0 0 7.25 11m-.1 5.1A8.95 8.95 0 0 0 9.1 18.05m6-1.1l2.3 2.3m-8.3-2.3l-2.3 2.3m8.3-8.3l2.3-2.3m-8.3 8.3l-2.3-2.3m2.3-6l-2.3-2.3"/></g></svg>
					设置与成员
				</button>

				{#if userState.session?.user?.role === 'root' || userState.session?.user?.role === '管理员'}
					<button 
						type="button"
						onclick={() => { showUserManagement = true; refreshUsers(); }}
						class="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-black/5 rounded-lg text-left text-xs font-medium text-black/70 cursor-pointer"
					>
						<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="opacity-60"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2m8-10a4 4 0 1 0 0-8a4 4 0 0 0 0 8m14 10v-2a4 4 0 0 0-3-3.87m-4-12a4 4 0 0 1 0 7.75"/></svg>
						用户管理
					</button>
				{/if}
			</div>

			<!-- 文档大分类 - 团队工作区 -->
			<div class="space-y-1">
				<button 
					type="button" 
					class="w-full flex items-center justify-between px-2 py-1 text-[11px] font-bold text-black/40 tracking-wider hover:text-black/60 cursor-pointer"
					onclick={() => { teamWorkspaceOpen = !teamWorkspaceOpen; }}
				>
					<span>👥 团队工作区</span>
					<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" class="transition-transform duration-200 {teamWorkspaceOpen ? 'rotate-90' : ''}"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m9 18l6-6l-6-6"/></svg>
				</button>

				{#if teamWorkspaceOpen}
					<div class="space-y-0.5 pl-1.5">
						{#each docs.filter(d => d.category === '团队工作区') as doc}
							{@const index = docs.findIndex(d => d.id === doc.id)}
							<button 
								type="button"
								class="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-black/5 rounded-lg text-left text-xs font-semibold cursor-pointer truncate transition-all duration-200 {activeDocIndex === index ? 'bg-black/5 text-black font-bold' : 'text-black/70'}"
								onclick={() => handleDocClick(index, doc.title)}
							>
								<span>{doc.emoji}</span>
								<span class="truncate">{doc.title}</span>
							</button>
						{/each}
					</div>
				{/if}
			</div>

			<!-- 文档大分类 - 个人笔记 -->
			<div class="space-y-1">
				<button 
					type="button" 
					class="w-full flex items-center justify-between px-2 py-1 text-[11px] font-bold text-black/40 tracking-wider hover:text-black/60 cursor-pointer"
					onclick={() => { personalNotesOpen = !personalNotesOpen; }}
				>
					<span>📝 个人笔记</span>
					<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" class="transition-transform duration-200 {personalNotesOpen ? 'rotate-90' : ''}"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m9 18l6-6l-6-6"/></svg>
				</button>

				{#if personalNotesOpen}
					<div class="space-y-0.5 pl-1.5">
						{#each docs.filter(d => d.category === '个人笔记') as doc}
							{@const index = docs.findIndex(d => d.id === doc.id)}
							<button 
								type="button"
								class="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-black/5 rounded-lg text-left text-xs font-semibold cursor-pointer truncate transition-all duration-200 {activeDocIndex === index ? 'bg-black/5 text-black font-bold' : 'text-black/70'}"
								onclick={() => handleDocClick(index, doc.title)}
							>
								<span>{doc.emoji}</span>
								<span class="truncate">{doc.title}</span>
							</button>
						{/each}
					</div>
				{/if}
			</div>

		</div>

		<!-- 侧边栏底部操作区 -->
		<div class="p-3 border-t border-black/5 bg-[#eeeeee]/50 space-y-1">
			<a 
				href="/logout" 
				class="flex items-center gap-2 p-2 hover:bg-black/5 rounded-lg text-xs font-bold text-error cursor-pointer transition-all duration-200"
			>
				<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 8V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2m7-2H9m11-3l3 3l-3 3"/></svg>
				登出
			</a>
		</div>
	</div>

	<!-- =================== 右侧主文档画布 =================== -->
	<div 
		bind:this={mainContentNode}
		class="relative flex-1 h-full min-h-0 overflow-y-auto overflow-x-hidden bg-[#fbfbfa] opacity-0"
	>
		
		<!-- 顶部面包屑与在线协作组 -->
		<div class="w-full h-11 border-b border-black/5 px-6 flex items-center justify-between shrink-0 bg-white/80 backdrop-blur-sm sticky top-0 z-20">
			<div class="flex items-center gap-3 text-xs text-black/50 font-medium">
				<span>工作台</span>
				<span>/</span>
				<span>{activeDoc?.category || ''}</span>
				<span>/</span>
				<span class="text-black font-semibold flex items-center gap-1">
					<span>{activeDoc?.emoji || ''}</span>
					<span>{activeDoc?.title || ''}</span>
				</span>

				<!-- 云端自动保存指示器 -->
				<div class="h-4 w-px bg-black/10 mx-1"></div>
				<div class="flex items-center gap-1.5 text-xs text-black/40 font-medium font-sans">
					{#if syncStatus === 'syncing'}
						<span class="inline-block w-2 h-2 rounded-full bg-yellow-400 animate-pulse"></span>
						<span>数据自动云同步中...</span>
					{:else if syncStatus === 'saved'}
						<span class="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
						<span class="text-emerald-600 font-semibold">云端已同步</span>
					{:else}
						<span class="inline-block w-2 h-2 rounded-full bg-neutral-400"></span>
						<span>已离线，等待编辑...</span>
					{/if}
				</div>
			</div>

			<!-- 在线协作用户头像 -->
			<div class="flex items-center gap-4">
				<div class="flex items-center">
					<div class="avatar-group -space-x-3 rtl:space-x-reverse">
						<div class="avatar border-white tooltip cursor-pointer" data-tip="Alice 正在编辑 35 行">
							<div class="w-6 h-6 rounded-full bg-pink-500 text-[10px] font-bold text-white flex items-center justify-center font-mono">A</div>
						</div>
						<div class="avatar border-white tooltip cursor-pointer" data-tip="Bob 正在查看">
							<div class="w-6 h-6 rounded-full bg-blue-500 text-[10px] font-bold text-white flex items-center justify-center font-mono">B</div>
						</div>
						<div class="avatar border-white tooltip cursor-pointer" data-tip="Charlie 5分钟前活跃">
							<div class="w-6 h-6 rounded-full bg-green-500 text-[10px] font-bold text-white flex items-center justify-center font-mono">C</div>
						</div>
					</div>
					<span class="text-[10px] text-black/40 font-mono font-bold ml-2">2 人在线</span>
				</div>

				<div class="h-4 w-px bg-black/10"></div>
				<button 
					type="button" 
					class="btn btn-xs btn-neutral rounded-full font-bold px-3 cursor-pointer"
					onclick={() => toast.success('🔗 已生成共享链接！已复制到剪贴板。')}
				>
					实时共享
				</button>
			</div>
		</div>

		<!-- 高对比度封面 -->
		<div class="w-full h-44 bg-neutral-900 relative group overflow-hidden shrink-0">
			<div class="grid-bg absolute inset-0 opacity-60"></div>
			<!-- 科幻淡雅的线性渐变 -->
			<div class="absolute inset-0 bg-gradient-to-tr from-black/80 via-transparent to-white/10"></div>
			<div class="absolute bottom-4 right-6 flex gap-2 opacity-0 group-hover:opacity-100 transition-all duration-300">
				<button type="button" class="btn btn-xs bg-white/15 text-white border-none hover:bg-white/30 rounded-md font-bold cursor-pointer">🎨 更改封面</button>
				<button type="button" class="btn btn-xs bg-white/15 text-white border-none hover:bg-white/30 rounded-md font-bold cursor-pointer">📍 调整位置</button>
			</div>
		</div>

		<!-- 动态内容骨架屏与 Tiptap 富文本核心画布 -->
		{#if docs.length === 0}
			<div class="max-w-3xl w-full px-12 pt-24 space-y-6">
				<div class="skeleton h-20 w-20 rounded-2xl"></div>
				<div class="skeleton h-12 w-3/4"></div>
				<div class="skeleton h-6 w-full mt-12"></div>
				<div class="skeleton h-6 w-5/6"></div>
				<div class="skeleton h-6 w-4/5"></div>
			</div>
		{:else}
			<div class="mx-auto w-full max-w-4xl px-12 pt-3 pb-16 relative">
				
				<!-- 超大 Emoji -->
				<div class="text-6xl mb-6 relative z-10 w-20 h-20 rounded-2xl bg-white border border-black/5 shadow-md flex items-center justify-center cursor-pointer hover:scale-105 transition-transform duration-200">
					{activeDoc?.emoji || '📝'}
				</div>

				<!-- svelte-ignore a11y_missing_content -->
				<!-- 交互式超大标题 -->
				<h1 
					bind:this={titleNode}
					class="text-5xl font-black text-black tracking-tight mb-3 outline-none leading-[1.05]" 
					contenteditable="true" 
					spellcheck="false"
					oninput={handleTitleInput}
				>
				</h1>

				<div class="mb-5 flex items-center gap-3 text-xs text-black/45">
					<span class="rounded-full bg-black/5 px-2.5 py-1 font-semibold">/{activeDoc?.category || '未分类'}</span>
					<span>{editMode === 'rich' ? '所见即所得编辑' : 'Markdown 结构编辑'}</span>
				</div>

				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					bind:this={editorShellNode}
					class="editor-shell"
					onmousemove={(e) => updateBlockHandleFromPoint(e.clientX, e.clientY)}
					onmouseleave={releaseBlockHandle}
				>
					<div
						bind:this={editorNode}
						class="tiptap-editor-container font-sans text-black/90 {editMode === 'markdown' ? 'hidden-editor' : ''}"
						onclick={hideCommandMenu}
					></div>

					{#if editMode === 'markdown'}
						<div class="markdown-split-view">
							<textarea
								class="markdown-editor"
								bind:value={markdownContent}
								oninput={handleMarkdownInput}
								spellcheck="false"
							></textarea>
							<div class="markdown-preview">
								<div class="markdown-preview-label">Preview</div>
								<div class="markdown-preview-body">
									{@html markdownPreviewHtml}
								</div>
							</div>
						</div>
					{/if}

					{#if editMode === 'rich' && blockHandleVisible}
						<div
							class="block-handle"
							style={`top:${blockHandleTop}px;`}
							onmouseenter={() => {
								blockHandleLocked = true;
								blockHandleVisible = true;
							}}
							onmouseleave={releaseBlockHandle}
						>
							<button type="button" class="handle-button" onclick={insertBlockBelow} title="插入新块">
								+
							</button>
							<button type="button" class="handle-button handle-drag" onclick={openBlockCommandMenu} title="块操作">
								⋮⋮
							</button>
						</div>
					{/if}

					{#if commandMenuOpen}
						<div
							class="command-menu"
							style={`top:${commandMenuTop}px; left:${commandMenuLeft}px;`}
						>
							<div class="command-menu-header">输入 `/` 快速插入块</div>
							{#each filteredSlashCommands as item}
								<button type="button" class="command-item" onclick={() => runSlashCommand(item)}>
									<span class="command-item-title">{item.label}</span>
									<span class="command-item-hint">{item.hint}</span>
								</button>
							{/each}
							{#if filteredSlashCommands.length === 0}
								<div class="command-empty">没有匹配的命令</div>
							{/if}
						</div>
					{/if}

					{#if editor}
						<div class="editor-toolbar-sticky">
							<div class="editor-toolbar-overlay">
							<button
								type="button"
								onclick={() => toggleEditMode('rich')}
								class="btn btn-xs rounded-full border-none px-3 {editMode === 'rich' ? 'bg-black text-white hover:bg-black' : 'bg-black/5 text-black/65 hover:bg-black/10'}"
							>
								可视化
							</button>
							<button
								type="button"
								onclick={() => toggleEditMode('markdown')}
								class="btn btn-xs rounded-full border-none px-3 font-mono {editMode === 'markdown' ? 'bg-black text-white hover:bg-black' : 'bg-black/5 text-black/65 hover:bg-black/10'}"
							>
								Markdown
							</button>

							<div class="mx-1 h-4 w-px bg-black/10"></div>

							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleBold().run()}
								class="btn btn-xs btn-ghost px-2.5 font-bold transition-all {editor.isActive('bold') ? 'bg-black/10 text-black' : 'text-black/60'}"
								title="加粗"
							>
								B
							</button>
							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleItalic().run()}
								class="btn btn-xs btn-ghost px-2.5 italic transition-all {editor.isActive('italic') ? 'bg-black/10 text-black' : 'text-black/60'}"
								title="斜体"
							>
								I
							</button>
							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleStrike().run()}
								class="btn btn-xs btn-ghost px-2.5 line-through transition-all {editor.isActive('strike') ? 'bg-black/10 text-black' : 'text-black/60'}"
								title="删除线"
							>
								S
							</button>
							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleCode().run()}
								class="btn btn-xs btn-ghost px-2 font-mono transition-all {editor.isActive('code') ? 'bg-black/10 text-black' : 'text-black/60'}"
								title="行内代码"
							>
								&lt;/&gt;
							</button>

							<div class="mx-1 h-4 w-px bg-black/10"></div>

							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
								class="btn btn-xs btn-ghost px-1.5 transition-all {editor.isActive('heading', { level: 1 }) ? 'bg-black/10 text-black font-bold' : 'text-black/60'}"
								title="一级标题"
							>
								H1
							</button>
							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
								class="btn btn-xs btn-ghost px-1.5 transition-all {editor.isActive('heading', { level: 2 }) ? 'bg-black/10 text-black font-bold' : 'text-black/60'}"
								title="二级标题"
							>
								H2
							</button>
							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
								class="btn btn-xs btn-ghost px-1.5 transition-all {editor.isActive('heading', { level: 3 }) ? 'bg-black/10 text-black font-bold' : 'text-black/60'}"
								title="三级标题"
							>
								H3
							</button>

							<div class="mx-1 h-4 w-px bg-black/10"></div>

							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleBulletList().run()}
								class="btn btn-xs btn-ghost px-2 transition-all {editor.isActive('bulletList') ? 'bg-black/10 text-black' : 'text-black/60'}"
								title="无序列表"
							>
								• 无序
							</button>
							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleOrderedList().run()}
								class="btn btn-xs btn-ghost px-2 transition-all {editor.isActive('orderedList') ? 'bg-black/10 text-black' : 'text-black/60'}"
								title="有序列表"
							>
								1. 有序
							</button>
							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleBlockquote().run()}
								class="btn btn-xs btn-ghost px-2 transition-all {editor.isActive('blockquote') ? 'bg-black/10 text-black' : 'text-black/60'}"
								title="引用块"
							>
								“ 引用
							</button>
							<button 
								type="button"
								onclick={() => editor?.chain().focus().toggleCodeBlock().run()}
								class="btn btn-xs btn-ghost px-2 transition-all {editor.isActive('codeBlock') ? 'bg-black/10 text-black font-mono' : 'text-black/60'}"
								title="代码块"
							>
								代码块
							</button>

							<div class="mx-1 h-4 w-px bg-black/10"></div>

							<button 
								type="button"
								onclick={() => editor?.chain().focus().undo().run()}
								disabled={!editor.can().chain().focus().undo().run()}
								class="btn btn-xs btn-ghost px-1.5 text-black/60 hover:text-black disabled:opacity-30"
								title="撤销"
							>
								↩
							</button>
							<button 
								type="button"
								onclick={() => editor?.chain().focus().redo().run()}
								disabled={!editor.can().chain().focus().redo().run()}
								class="btn btn-xs btn-ghost px-1.5 text-black/60 hover:text-black disabled:opacity-30"
								title="重做"
							>
								↪
							</button>
							</div>
						</div>
					{/if}
				</div>

			</div>
		{/if}

	</div>

</div>

<!-- 用户管理弹窗组件 -->
{#if showUserManagement}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div 
		class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4"
		onclick={() => showUserManagement = false}
	>
		<div 
			class="bg-white border border-black/10 rounded-3xl shadow-2xl p-6 max-w-2xl w-full max-h-[85vh] overflow-y-auto flex flex-col space-y-6"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="flex justify-between items-center border-b border-black/5 pb-3">
				<h3 class="text-lg font-bold text-black flex items-center gap-2">
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" class="text-black/60"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2m8-10a4 4 0 1 0 0-8a4 4 0 0 0 0 8m14 10v-2a4 4 0 0 0-3-3.87m-4-12a4 4 0 0 1 0 7.75"/></svg>
					用户管理
				</h3>
				<button 
					type="button" 
					class="btn btn-sm btn-ghost btn-circle text-black/50 hover:text-black font-bold"
					onclick={() => showUserManagement = false}
				>✕</button>
			</div>

			<!-- 用户列表表格 -->
			<div class="space-y-2">
				<h4 class="text-xs font-bold text-black/40 tracking-wider uppercase">当前用户列表</h4>
				<div class="border border-black/5 rounded-2xl overflow-hidden bg-neutral-50/50">
					<table class="table table-xs w-full text-black">
						<thead>
							<tr class="bg-black/5 border-b border-black/5 text-black/50 font-bold">
								<th class="py-2.5 px-4 text-left">用户名</th>
								<th class="py-2.5 px-4 text-left">权限角色</th>
								<th class="py-2.5 px-4 text-center">操作</th>
							</tr>
						</thead>
						<tbody>
							{#each userList as user}
								<tr class="border-b border-black/5">
									<td class="py-2.5 px-4 font-medium">{user.username}</td>
									<td class="py-2.5 px-4">
										<span class="badge badge-sm badge-neutral font-medium">{user.role}</span>
									</td>
									<td class="py-2.5 px-4 text-center">
										{#if user.username === 'sout'}
											<span class="text-xs text-black/30 font-semibold select-none">系统内置</span>
										{:else}
											<button 
												type="button" 
												class="btn btn-xs btn-error text-white font-bold rounded-md px-2"
												onclick={() => handleDeleteUser(user.username)}
											>
												删除
											</button>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>

			<!-- 添加新用户表单 -->
			<form onsubmit={handleAddUser} class="space-y-4 border-t border-black/5 pt-4">
				<h4 class="text-xs font-bold text-black/40 tracking-wider uppercase">添加新用户</h4>
				<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
					<div class="space-y-1">
						<label for="new-username" class="text-[11px] font-bold text-black/50 tracking-wider">用户名</label>
						<input 
							id="new-username"
							type="text" 
							placeholder="请输入用户名" 
							bind:value={newUsername}
							required
							class="w-full bg-neutral-50 border border-black/10 text-xs rounded-xl px-3 py-2 outline-none focus:border-black focus:bg-white transition-all"
						/>
					</div>
					<div class="space-y-1">
						<label for="new-password" class="text-[11px] font-bold text-black/50 tracking-wider">密码</label>
						<input 
							id="new-password"
							type="password" 
							placeholder="请输入密码" 
							bind:value={newPassword}
							required
							class="w-full bg-neutral-50 border border-black/10 text-xs rounded-xl px-3 py-2 outline-none focus:border-black focus:bg-white transition-all"
						/>
					</div>
					<div class="space-y-1">
						<label for="new-role" class="text-[11px] font-bold text-black/50 tracking-wider">选择权限</label>
						<select 
							id="new-role"
							bind:value={newRole}
							class="w-full bg-neutral-50 border border-black/10 text-xs rounded-xl px-3 py-2 outline-none focus:border-black focus:bg-white transition-all"
						>
							<option value="root">root</option>
							<option value="管理员">管理员</option>
							<option value="用户">用户</option>
						</select>
					</div>
				</div>
				<button 
					type="submit" 
					class="btn btn-sm btn-neutral w-full rounded-xl font-bold py-2 mt-2"
				>
					添加用户
				</button>
			</form>
		</div>
	</div>
{/if}

<style>
	/* 隐藏浏览器原装选区，让协作光标显得更加纯粹 */
	::selection {
		background: rgba(0, 0, 0, 0.08);
	}

	/* Tiptap 内部排版样式：Notion 极简、高保真质感 */
	:global(.tiptap) {
		outline: none;
		min-height: 480px;
		font-size: 16px;
		line-height: 1.75;
		color: rgba(17, 24, 39, 0.92);
		font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
	}

	:global(.tiptap > *) {
		position: relative;
		margin-inline: -0.75rem;
		border-radius: 0.9rem;
		padding: 0.14rem 0.75rem;
		transition: background-color 180ms ease, transform 180ms ease;
	}

	:global(.tiptap > :not(pre):not(hr):hover) {
		background: rgba(15, 23, 42, 0.04);
	}

	:global(.tiptap p) {
		margin-bottom: 0.9em;
	}

	:global(.tiptap h1) {
		font-size: 1.9rem;
		font-weight: 800;
		margin-top: 1.75em;
		margin-bottom: 0.65em;
		color: #111827;
		letter-spacing: -0.03em;
	}

	:global(.tiptap h2) {
		font-size: 1.45rem;
		font-weight: 750;
		margin-top: 1.55em;
		margin-bottom: 0.6em;
		color: #111827;
		letter-spacing: -0.02em;
	}

	:global(.tiptap h3) {
		font-size: 1.18rem;
		font-weight: 600;
		margin-top: 1.4em;
		margin-bottom: 0.5em;
		color: #1f2937;
		letter-spacing: -0.01em;
	}

	:global(.tiptap ul) {
		list-style-type: disc;
		padding-left: 1.8rem;
		margin-bottom: 0.8em;
	}

	:global(.tiptap ol) {
		list-style-type: decimal;
		padding-left: 1.6rem;
		margin-bottom: 0.8em;
	}

	:global(.tiptap li) {
		margin-bottom: 0.3em;
	}

	:global(.tiptap blockquote) {
		border-left: 3px solid rgba(17, 24, 39, 0.16);
		padding: 0.7rem 0.3rem 0.7rem 1.15rem;
		font-style: italic;
		color: rgba(17, 24, 39, 0.72);
		margin: 1.5em 0;
		background:
			linear-gradient(90deg, rgba(15, 23, 42, 0.04), rgba(15, 23, 42, 0.015));
		border-radius: 0 0.9rem 0.9rem 0;
	}

	:global(.tiptap pre) {
		background-color: #111827;
		color: #f3f4f6;
		padding: 1.25rem;
		border-radius: 1rem;
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		font-size: 0.85em;
		overflow-x: auto;
		margin: 1.5em 0;
		box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
	}

	:global(.tiptap pre:hover) {
		background-color: #111827;
	}

	:global(.tiptap code) {
		background-color: rgba(15, 23, 42, 0.06);
		padding: 0.15em 0.3em;
		border-radius: 0.25em;
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		font-size: 0.9em;
		color: #111;
	}

	:global(.tiptap pre code) {
		background-color: transparent;
		padding: 0;
		border-radius: 0;
		font-size: inherit;
		color: inherit;
	}

	:global(.tiptap hr) {
		border: 0;
		border-top: 1px solid rgba(0, 0, 0, 0.1);
		margin: 2em 0;
	}

	.tiptap-editor-container {
		min-height: 480px;
		padding: 0.25rem 0 5.5rem;
	}

	.hidden-editor {
		position: absolute;
		inset: 0;
		opacity: 0;
		pointer-events: none;
	}

	.markdown-editor {
		min-height: 480px;
		width: 100%;
		resize: none;
		border: none;
		outline: none;
		background: transparent;
		color: #111827;
		font: 500 14px/1.85 "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
		white-space: pre-wrap;
		tab-size: 2;
	}

	.markdown-editor::selection {
		background: rgba(15, 23, 42, 0.12);
	}

	.editor-shell {
		position: relative;
		padding: 0.35rem 0 1.25rem 3rem;
	}

	.editor-toolbar-sticky {
		position: sticky;
		bottom: 1rem;
		z-index: 30;
		margin-top: -4.7rem;
		display: flex;
		justify-content: center;
		pointer-events: none;
	}

	.editor-toolbar-overlay {
		position: relative;
		left: 50%;
		pointer-events: auto;
		display: flex;
		max-width: calc(100% - 3rem);
		flex-wrap: wrap;
		align-items: center;
		gap: 0.375rem;
		transform: translateX(-50%);
		border: 1px solid rgba(15, 23, 42, 0.08);
		border-radius: 1.25rem;
		background: rgba(255, 255, 255, 0.95);
		padding: 0.7rem 0.85rem;
		box-shadow: 0 16px 40px rgba(15, 23, 42, 0.12);
		backdrop-filter: blur(14px);
	}

	.block-handle {
		position: absolute;
		left: 0;
		z-index: 25;
		display: flex;
		gap: 0.35rem;
		transform: translateY(-50%);
	}

	.handle-button {
		display: flex;
		height: 1.7rem;
		width: 1.7rem;
		align-items: center;
		justify-content: center;
		border: 1px solid rgba(15, 23, 42, 0.08);
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.95);
		color: rgba(15, 23, 42, 0.7);
		font-weight: 700;
		box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
		cursor: pointer;
		transition: all 160ms ease;
	}

	.handle-button:hover {
		background: #111827;
		color: white;
	}

	.handle-drag {
		font-size: 0.75rem;
		letter-spacing: -0.1em;
	}

	.command-menu {
		position: absolute;
		z-index: 35;
		width: 18rem;
		border: 1px solid rgba(15, 23, 42, 0.08);
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.98);
		padding: 0.55rem;
		box-shadow: 0 24px 48px rgba(15, 23, 42, 0.15);
		backdrop-filter: blur(18px);
	}

	.command-menu-header {
		padding: 0.4rem 0.55rem 0.55rem;
		color: rgba(15, 23, 42, 0.45);
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	.command-item {
		display: flex;
		width: 100%;
		align-items: center;
		justify-content: space-between;
		border: none;
		border-radius: 0.8rem;
		background: transparent;
		padding: 0.65rem 0.7rem;
		text-align: left;
		cursor: pointer;
		transition: background-color 160ms ease;
	}

	.command-item:hover {
		background: rgba(15, 23, 42, 0.05);
	}

	.command-item-title {
		color: #111827;
		font-size: 0.86rem;
		font-weight: 700;
	}

	.command-item-hint {
		color: rgba(15, 23, 42, 0.45);
		font-size: 0.75rem;
	}

	.command-empty {
		padding: 0.7rem;
		color: rgba(15, 23, 42, 0.45);
		font-size: 0.82rem;
	}

	.markdown-split-view {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
		gap: 2rem;
		min-height: 480px;
		padding-bottom: 5.5rem;
	}

	.markdown-preview {
		min-width: 0;
		padding-left: 2rem;
	}

	.markdown-preview-label {
		margin-bottom: 0.9rem;
		color: rgba(15, 23, 42, 0.45);
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	.markdown-preview-body {
		color: rgba(17, 24, 39, 0.92);
		font-size: 16px;
		line-height: 1.75;
	}

	.markdown-preview-body :global(h1) {
		font-size: 1.9rem;
		font-weight: 800;
		letter-spacing: -0.03em;
		margin: 1.75em 0 0.65em;
	}

	.markdown-preview-body :global(h2) {
		font-size: 1.45rem;
		font-weight: 750;
		letter-spacing: -0.02em;
		margin: 1.55em 0 0.6em;
	}

	.markdown-preview-body :global(h3) {
		font-size: 1.18rem;
		font-weight: 600;
		letter-spacing: -0.01em;
		margin: 1.4em 0 0.5em;
	}

	.markdown-preview-body :global(p),
	.markdown-preview-body :global(ul),
	.markdown-preview-body :global(ol),
	.markdown-preview-body :global(blockquote),
	.markdown-preview-body :global(pre) {
		margin-bottom: 1rem;
	}

	.markdown-preview-body :global(ul) {
		list-style-type: disc;
		padding-left: 1.8rem;
	}

	.markdown-preview-body :global(ol) {
		list-style-type: decimal;
		padding-left: 1.6rem;
	}

	.markdown-preview-body :global(blockquote) {
		border-left: 3px solid rgba(17, 24, 39, 0.16);
		padding: 0.7rem 0.3rem 0.7rem 1.15rem;
		font-style: italic;
		color: rgba(17, 24, 39, 0.72);
		background:
			linear-gradient(90deg, rgba(15, 23, 42, 0.04), rgba(15, 23, 42, 0.015));
		border-radius: 0 0.9rem 0.9rem 0;
	}

	.markdown-preview-body :global(pre) {
		overflow-x: auto;
		border-radius: 1rem;
		background: #111827;
		padding: 1rem 1.15rem;
		color: #f3f4f6;
	}

	.markdown-preview-body :global(code) {
		border-radius: 0.35rem;
		background: rgba(15, 23, 42, 0.06);
		padding: 0.15rem 0.32rem;
	}
</style>
