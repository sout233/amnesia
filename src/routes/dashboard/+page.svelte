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
	import Link from '@tiptap/extension-link';
	import Image from '@tiptap/extension-image';
	import { TextStyle } from '@tiptap/extension-text-style';
	import Color from '@tiptap/extension-color';
	import Highlight from '@tiptap/extension-highlight';
	import { marked } from 'marked';
	import TurndownService from 'turndown';
	import DOMPurify from 'dompurify';
	import { EditorState } from '@codemirror/state';
	import { EditorView, lineNumbers, highlightActiveLineGutter } from '@codemirror/view';
	import { markdown as markdownLanguage } from '@codemirror/lang-markdown';

	type DocRecord = {
		id: number;
		emoji: string;
		title: string;
		category: string;
		content: string;
		created_at?: string;
		updated_at?: string;
		author?: string;
	};

	let sidebarNode = $state<HTMLElement | null>(null);
	let mainContentNode = $state<HTMLElement | null>(null);

	// 当前选中的文档索引
	let activeDocIndex = $state(0);

	// 动态文档列表
	let docs = $state<DocRecord[]>([]);
	let activeDoc = $derived(docs[activeDocIndex]);

	// Tiptap 绑定
	let editorNode = $state<HTMLElement | null>(null);
	let titleNode = $state<HTMLElement | null>(null);
	let editor = $state<Editor | null>(null);
	let editorShellNode = $state<HTMLElement | null>(null);
	let markdownEditorNode = $state<HTMLElement | null>(null);
	let markdownEditorView: EditorView | null = null;
	let markdownContent = $state('');
	let editMode = $state<'rich' | 'markdown'>('rich');
	let blockHandleVisible = $state(false);
	let blockHandleTop = $state(0);
	let blockHandleLeft = $state(0);
	let activeBlockElement = $state<HTMLElement | null>(null);
	let commandMenuOpen = $state(false);
	let commandMenuTop = $state(0);
	let commandMenuLeft = $state(0);
	let slashQuery = $state('');
	let blockHandleLocked = $state(false);
	let markdownPreviewHtml = $state('');
	let showGlobalSettingsModal = $state(false);
	let showPageSettingsModal = $state(false);
	let showPropertiesModal = $state(false);
	let showEmojiPickerModal = $state(false);
	let lockPage = $state(false);
	let theme = $state('cupcake');
	let pagePaddingX = $state(48);
	let docFontSize = $state(16);
	let docFontFamily = $state('Noto Sans SC');
	let globalUiFont = $state('Noto Sans SC');
	let globalSettingsSection = $state<'appearance' | 'editor' | 'shortcuts' | 'advanced'>('appearance');
	let customEmojiInput = $state('');
	let activeDocMenuId = $state<number | null>(null);
	let selectedTextColor = $state('#111827');
	let selectedHighlightColor = $state('#fef08a');
	let docMenuPosition = $state({ top: 0, left: 0 });
	let showTextColorModal = $state(false);
	let showHighlightColorModal = $state(false);
	let textColorControls = $state({ l: 24, c: 0.03, h: 258, a: 1 });
	let highlightColorControls = $state({ l: 92, c: 0.08, h: 95, a: 1 });

	type ThemePreset = 'cupcake' | 'shadcn' | 'ibm' | 'macos';

	type ThemeConfig = {
		name: ThemePreset;
		radius: number;
		shadow: number;
		padding: number;
		gap: number;
		uiFont: string;
		foreground: string;
		background: string;
		panel: string;
		sidebar: string;
		accent: string;
		gradientFrom: string;
		gradientTo: string;
	};

	function oklchString(controls: { l: number; c: number; h: number; a: number }) {
		return `oklch(${(controls.l / 100).toFixed(3)} ${controls.c.toFixed(3)} ${controls.h.toFixed(1)} / ${controls.a.toFixed(2)})`;
	}

	function applyCurrentTextColor() {
		selectedTextColor = oklchString(textColorControls);
		applyTextColor(selectedTextColor);
	}

	function applyCurrentHighlightColor() {
		selectedHighlightColor = oklchString(highlightColorControls);
		applyHighlightColor(selectedHighlightColor);
	}

	// 同步状态与定时器
	let syncStatus = $state<'idle' | 'syncing' | 'saved'>('saved');
	let saveTimeout: ReturnType<typeof setTimeout>;

	const turndownService = new TurndownService({
		headingStyle: 'atx',
		bulletListMarker: '-',
		codeBlockStyle: 'fenced'
	});

	function isEditorActive(type: string, attrs?: Record<string, unknown>) {
		return !!editor && editor.isFocused && editor.isActive(type, attrs);
	}

	function getActiveTextColor() {
		return (editor?.getAttributes('textStyle')?.color as string | undefined) ?? '';
	}

	function getActiveHighlightColor() {
		return (editor?.getAttributes('highlight')?.color as string | undefined) ?? '';
	}

	const themeOptions: ThemeConfig[] = [
		{
			name: 'cupcake',
			radius: 22,
			shadow: 16,
			padding: 16,
			gap: 12,
			uiFont: 'Outfit',
			foreground: 'oklch(0.24 0.03 258)',
			background: 'oklch(0.98 0.01 95)',
			panel: 'oklch(0.995 0.005 95)',
			sidebar: 'oklch(0.96 0.015 95)',
			accent: 'oklch(0.62 0.16 48)',
			gradientFrom: 'oklch(0.99 0.015 95)',
			gradientTo: 'oklch(0.95 0.02 75)'
		},
		{
			name: 'shadcn',
			radius: 10,
			shadow: 8,
			padding: 14,
			gap: 10,
			uiFont: 'Outfit',
			foreground: 'oklch(0.97 0 0)',
			background: 'oklch(0 0 0)',
			panel: 'oklch(0.12 0 0 / 0.98)',
			sidebar: 'oklch(0 0 0 / 1)',
			accent: 'oklch(0.78 0.03 255)',
			gradientFrom: 'oklch(0 0 0)',
			gradientTo: 'oklch(0.03 0 0)'
		},
		{
			name: 'ibm',
			radius: 4,
			shadow: 6,
			padding: 14,
			gap: 8,
			uiFont: 'Outfit',
			foreground: 'oklch(0.21 0.01 255)',
			background: 'oklch(0.985 0.002 240)',
			panel: 'oklch(1 0 0)',
			sidebar: 'oklch(0.96 0.004 240)',
			accent: 'oklch(0.56 0.19 257)',
			gradientFrom: 'oklch(0.99 0.002 240)',
			gradientTo: 'oklch(0.96 0.004 240)'
		},
		{
			name: 'macos',
			radius: 24,
			shadow: 22,
			padding: 18,
			gap: 14,
			uiFont: 'Outfit',
			foreground: 'oklch(0.26 0.02 255)',
			background: 'oklch(0.97 0.01 260)',
			panel: 'oklch(0.99 0.01 260 / 0.88)',
			sidebar: 'oklch(0.95 0.015 260 / 0.9)',
			accent: 'oklch(0.67 0.17 265)',
			gradientFrom: 'oklch(0.99 0.02 260)',
			gradientTo: 'oklch(0.92 0.04 310)'
		}
	];

	const fontOptions = [
		{ value: 'JetBrains Mono', label: 'JetBrains Mono' },
		{ value: 'Noto Serif SC', label: 'Noto Serif SC' },
		{ value: 'Noto Sans SC', label: 'Noto Sans SC' },
		{ value: 'Maple Mono', label: 'Maple Mono' }
	];

	function applyTheme() {
		if (typeof document === 'undefined') return;
		const config = themeOptions.find((option) => option.name === theme) ?? themeOptions[0];
		const root = document.documentElement;
		root.setAttribute('data-theme', config.name === 'cupcake' ? 'cupcake' : config.name === 'shadcn' ? 'dark' : config.name === 'ibm' ? 'light' : 'cupcake');
		root.style.setProperty('--dashboard-fg', config.foreground);
		root.style.setProperty('--dashboard-bg', config.background);
		root.style.setProperty('--dashboard-panel', config.panel);
		root.style.setProperty('--dashboard-sidebar', config.sidebar);
		root.style.setProperty('--dashboard-accent', config.accent);
		root.style.setProperty('--dashboard-gradient-from', config.gradientFrom);
		root.style.setProperty('--dashboard-gradient-to', config.gradientTo);
		root.style.setProperty('--dashboard-radius', `${config.radius}px`);
		root.style.setProperty('--dashboard-shadow', `${config.shadow}px`);
		root.style.setProperty('--dashboard-padding', `${config.padding}px`);
		root.style.setProperty('--dashboard-gap', `${config.gap}px`);
		root.style.setProperty('--dashboard-ui-font', globalUiFont || config.uiFont);
		root.style.setProperty('--dashboard-doc-font', docFontFamily || 'Noto Sans SC');
		root.style.setProperty('--dashboard-doc-size', `${docFontSize}px`);
		root.style.setProperty('--app-ui-font', globalUiFont || config.uiFont);
	}

	function persistDashboardSettings() {
		if (typeof localStorage === 'undefined') return;
		localStorage.setItem(
			'amnesia_dashboard_settings',
			JSON.stringify({
				theme,
				pagePaddingX,
				docFontSize,
				docFontFamily,
				globalUiFont,
				lockPage
			})
		);
	}

	function loadDashboardSettings() {
		if (typeof localStorage === 'undefined') return;
		const raw = localStorage.getItem('amnesia_dashboard_settings');
		if (!raw) return;
		try {
			const parsed = JSON.parse(raw);
			theme = parsed.theme ?? theme;
			pagePaddingX = parsed.pagePaddingX ?? pagePaddingX;
			docFontSize = parsed.docFontSize ?? docFontSize;
			docFontFamily = parsed.docFontFamily ?? docFontFamily;
			globalUiFont = parsed.globalUiFont ?? globalUiFont;
			lockPage = parsed.lockPage ?? lockPage;
		} catch {
			// ignore malformed local settings
		}
	}

	function sanitizeHtml(html: string) {
		return DOMPurify.sanitize(html, {
			USE_PROFILES: { html: true },
			ADD_TAGS: ['iframe'],
			ADD_ATTR: ['allow', 'allowfullscreen', 'frameborder', 'scrolling', 'target']
		});
	}

	function initMarkdownEditor() {
		if (!markdownEditorNode) return;
		if (markdownEditorView) {
			markdownEditorView.destroy();
			markdownEditorView = null;
		}

		markdownEditorView = new EditorView({
			parent: markdownEditorNode,
			state: EditorState.create({
				doc: markdownContent,
				extensions: [
					lineNumbers(),
					highlightActiveLineGutter(),
					markdownLanguage(),
					EditorView.lineWrapping,
					EditorView.updateListener.of(async (update) => {
						if (!update.docChanged) return;
						markdownContent = update.state.doc.toString();
						markdownPreviewHtml = await marked.parse(markdownContent);
					})
				]
			})
		});
	}

	function syncMarkdownEditorDoc() {
		if (!markdownEditorView) return;
		const current = markdownEditorView.state.doc.toString();
		if (current === markdownContent) return;
		markdownEditorView.dispatch({
			changes: { from: 0, to: current.length, insert: markdownContent }
		});
	}

	async function renameActiveDoc() {
		const currentDoc = docs[activeDocIndex];
		if (!currentDoc) return;
		const nextTitle = prompt('输入新的文档标题', currentDoc.title)?.trim();
		if (!nextTitle || nextTitle === currentDoc.title) return;
		currentDoc.title = nextTitle;
		if (titleNode) {
			titleNode.innerText = nextTitle;
		}
		activeDocMenuId = null;
		triggerAutoSave();
	}

	function openDocMenu(id: number) {
		const target = document.getElementById(`doc-menu-trigger-${id}`);
		if (!target) {
			activeDocMenuId = activeDocMenuId === id ? null : id;
			return;
		}
		const rect = target.getBoundingClientRect();
		docMenuPosition = {
			top: rect.bottom + 6,
			left: Math.max(12, rect.right - 168)
		};
		activeDocMenuId = activeDocMenuId === id ? null : id;
	}

	async function duplicateActiveDoc() {
		const currentDoc = docs[activeDocIndex];
		if (!currentDoc) return;
		const payload = {
			emoji: currentDoc.emoji,
			title: `${currentDoc.title} 副本`,
			category: currentDoc.category,
			content: currentDoc.content
		};
		const { data, error } = await supabase.from('amnesia_docs').insert(payload).select().single();
		if (error || !data) {
			toast.error('创建副本失败');
			return;
		}
		docs = [...docs, data as DocRecord];
		activeDocIndex = docs.findIndex((doc) => doc.id === data.id);
		await tick();
		handleDocClick(activeDocIndex, data.title);
		activeDocMenuId = null;
		toast.success('已创建文档副本');
	}

	async function deleteActiveDoc() {
		const currentDoc = docs[activeDocIndex];
		if (!currentDoc) return;
		if (!confirm(`确定删除「${currentDoc.title}」吗？`)) return;

		const { error } = await supabase.from('amnesia_docs').delete().eq('id', currentDoc.id);
		if (error) {
			toast.error('删除文档失败');
			return;
		}

		docs = docs.filter((doc) => doc.id !== currentDoc.id);
		activeDocIndex = Math.max(0, Math.min(activeDocIndex, docs.length - 1));
		await tick();
		if (docs[activeDocIndex]) {
			handleDocClick(activeDocIndex, docs[activeDocIndex].title);
		}
		activeDocMenuId = null;
		toast.success('文档已删除');
	}

	async function updateDocEmoji() {
		const currentDoc = docs[activeDocIndex];
		if (!currentDoc || !customEmojiInput.trim()) return;
		currentDoc.emoji = customEmojiInput.trim();
		customEmojiInput = '';
		showEmojiPickerModal = false;
		triggerAutoSave();
	}

	function insertLink() {
		if (!editor) return;
		const href = prompt('输入链接地址');
		if (!href) return;
		editor.chain().focus().setLink({ href, target: '_blank' }).run();
	}

	function insertImage() {
		if (!editor) return;
		const src = prompt('输入图片 URL');
		if (!src) return;
		editor.chain().focus().setImage({ src, alt: 'image' }).run();
	}

	function insertSafeHtml() {
		if (!editor) return;
		const html = prompt('输入要嵌入的 HTML（会先经过安全过滤）');
		if (!html) return;
		editor.chain().focus().insertContent(sanitizeHtml(html)).run();
	}

	function applyTextColor(color: string) {
		if (lockPage) return;
		editor?.chain().focus().setColor(color).run();
	}

	function applyHighlightColor(color: string) {
		if (lockPage) return;
		editor?.chain().focus().setHighlight({ color }).run();
	}

	function resetTextColor() {
		if (lockPage) return;
		selectedTextColor = '';
		editor?.chain().focus().unsetColor().run();
	}

	function resetHighlightColor() {
		if (lockPage) return;
		selectedHighlightColor = '';
		editor?.chain().focus().unsetHighlight().run();
	}

	function toggleTextColorPicker() {
		const activeColor = getActiveTextColor();
		if (activeColor) {
			resetTextColor();
			showTextColorModal = false;
			return;
		}
		showTextColorModal = !showTextColorModal;
		if (showTextColorModal) showHighlightColorModal = false;
	}

	function toggleHighlightColorPicker() {
		const activeColor = getActiveHighlightColor();
		if (activeColor) {
			resetHighlightColor();
			showHighlightColorModal = false;
			return;
		}
		showHighlightColorModal = !showHighlightColorModal;
		if (showHighlightColorModal) showTextColorModal = false;
	}

	function syncActiveFormattingState() {
		const activeTextColor = getActiveTextColor();
		const activeHighlightColor = getActiveHighlightColor();
		selectedTextColor = activeTextColor || '#111827';
		selectedHighlightColor = activeHighlightColor || '#fef08a';
	}

	async function exportMarkdown() {
		const currentDoc = docs[activeDocIndex];
		if (!currentDoc) return;
		const blob = new Blob([markdownContent], { type: 'text/markdown;charset=utf-8' });
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement('a');
		anchor.href = url;
		anchor.download = `${currentDoc.title}.md`;
		anchor.click();
		URL.revokeObjectURL(url);
	}

	async function importMarkdownFile(e: Event) {
		const file = (e.currentTarget as HTMLInputElement).files?.[0];
		if (!file) return;
		markdownContent = await file.text();
		markdownPreviewHtml = await marked.parse(markdownContent);
		if (editMode === 'rich') {
			await applyMarkdownToEditor(markdownContent);
		} else {
			syncMarkdownEditorDoc();
		}
	}

	async function copyPageContent() {
		const currentDoc = docs[activeDocIndex];
		if (!currentDoc) return;
		await navigator.clipboard.writeText(markdownContent || currentDoc.content);
		toast.success('页面内容已复制');
	}

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
		markdownContent = html;
		markdownPreviewHtml = html;
	}

	async function applyMarkdownToEditor(markdown: string) {
		if (!editor || !docs[activeDocIndex]) return;

		editor.commands.setContent(markdown, { emitUpdate: false });
		docs[activeDocIndex].content = editor.getHTML();
		markdownPreviewHtml = docs[activeDocIndex].content;
		syncActiveFormattingState();
		triggerAutoSave();
	}

	async function handleMarkdownInput(e: Event) {
		const target = e.currentTarget as HTMLTextAreaElement;
		markdownContent = target.value;
		markdownPreviewHtml = markdownContent;
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
		if (editMode !== 'rich' || !editorShellNode || !editor || !editorNode) {
			hideBlockHandle();
			return;
		}

		const coords = editor.view.posAtCoords({ left: clientX, top: clientY });
		if (!coords) {
			hideBlockHandle();
			return;
		}

		const resolved = editor.state.doc.resolve(coords.pos);
		const topLevelIndex = resolved.index(0);
		const block = editorNode.children.item(topLevelIndex) as HTMLElement | null;
		if (!block) {
			hideBlockHandle();
			return;
		}

		const shellRect = editorShellNode.getBoundingClientRect();
		const blockRect = block.getBoundingClientRect();
		blockHandleTop = blockRect.top - shellRect.top + Math.min(blockRect.height / 2, 24);
		blockHandleLeft = blockRect.left - shellRect.left - 42;
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
				markdownContent = docs[activeDocIndex]?.content || editor.getHTML();
				markdownPreviewHtml = markdownContent;
			}
			editMode = 'markdown';
			await tick();
			initMarkdownEditor();
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
				syncActiveFormattingState();
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
		loadDashboardSettings();
		applyTheme();
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
				extensions: [
					StarterKit.configure({
						heading: {
							levels: [1, 2, 3]
						}
					}),
					TextStyle,
					Color,
					Highlight.configure({ multicolor: true }),
					Link.configure({ openOnClick: false }),
					Image
				],
				content: initialDoc.content,
				editorProps: {
					attributes: {
						class: 'tiptap',
						style: `font-size:${docFontSize}px; --dashboard-doc-font:${docFontFamily};`
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
					syncActiveFormattingState();
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
		if (markdownEditorView) {
			markdownEditorView.destroy();
			markdownEditorView = null;
		}
		clearTimeout(saveTimeout);
	});
</script>

<svelte:head>
	<title>工作台 - Amnesia</title>
</svelte:head>

<div class="dashboard-shell flex h-[100dvh] max-h-[100dvh] w-full overflow-hidden text-sm">

	<!-- =================== 左侧 Notion 侧边栏 =================== -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		bind:this={sidebarNode}
		class="dashboard-sidebar w-60 h-full flex flex-col justify-between shrink-0 select-none z-10"
	>
		<div class="flex flex-col overflow-y-auto overflow-x-visible p-2.5 space-y-3">

			<!-- 用户资料块 -->
			<div class="dashboard-list-row dashboard-sidebar-card flex items-center gap-2 p-1.5 rounded-xl cursor-pointer transition-all duration-200">
				<div class="dashboard-avatar w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold font-mono overflow-hidden">
					{#if userState.avatarUrl}
						<img src={userState.avatarUrl} alt="Avatar" class="w-full h-full object-cover" />
					{:else}
						AM
					{/if}
				</div>
				<div class="flex-1 min-w-0">
					<p class="dashboard-strong font-bold text-xs truncate leading-none">
						{userState.session?.user?.username || '游客'}
					</p>
					<!-- <p class="dashboard-muted text-[9px] tracking-wider mt-0.5 uppercase">
						{#if userState.session}
							已登录 ({userState.session.user.role})
						{:else}
							游客暂存态
						{/if}
					</p> -->
				</div>
			</div>

			<!-- 快速导航区 -->
			<div class="space-y-0.5">
				<button
					type="button"
					onclick={() => toast.info('🔍 检索服务正在筹备中...')}
					class="dashboard-list-row dashboard-sidebar-entry dashboard-muted w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-xs font-medium cursor-pointer"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="opacity-60"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0-14 0m18 11l-6-6"/></svg>
					快速检索
				</button>

				<button
					type="button"
					onclick={() => toast.info('⚙️ 设置服务正在建设中...')}
					class="dashboard-list-row dashboard-sidebar-entry dashboard-muted w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-xs font-medium cursor-pointer"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="opacity-60"><g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"><path d="M12 14a2 2 0 1 0 0-4a2 2 0 0 0 0 4"/><path d="M14.2 17.95a8.95 8.95 0 0 0 1.95-1.95m.1-5.1a8.95 8.95 0 0 0-1.95-1.95m-5.1-.1A8.95 8.95 0 0 0 7.25 11m-.1 5.1A8.95 8.95 0 0 0 9.1 18.05m6-1.1l2.3 2.3m-8.3-2.3l-2.3 2.3m8.3-8.3l2.3-2.3m-8.3 8.3l-2.3-2.3m2.3-6l-2.3-2.3"/></g></svg>
					设置与成员
				</button>

				{#if userState.session?.user?.role === 'root' || userState.session?.user?.role === '管理员'}
					<button
						type="button"
						onclick={() => { showUserManagement = true; refreshUsers(); }}
						class="dashboard-list-row dashboard-sidebar-entry dashboard-muted w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-xs font-medium cursor-pointer"
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
					class="dashboard-muted dashboard-sidebar-section w-full flex items-center justify-between px-2 py-0.5 text-[10px] font-bold tracking-wider cursor-pointer"
					onclick={() => { teamWorkspaceOpen = !teamWorkspaceOpen; }}
				>
					<span>👥 团队工作区</span>
					<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" class="transition-transform duration-200 {teamWorkspaceOpen ? 'rotate-90' : ''}"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m9 18l6-6l-6-6"/></svg>
				</button>

				{#if teamWorkspaceOpen}
					<div class="space-y-0.5 pl-1">
						{#each docs.filter(d => d.category === '团队工作区') as doc}
							{@const index = docs.findIndex(d => d.id === doc.id)}
							<div class="dashboard-doc-row dashboard-sidebar-doc relative flex items-center gap-1 pr-1 rounded-lg transition-all duration-200 {activeDocIndex === index ? 'is-active font-bold' : ''}">
								<button
									type="button"
									class="flex-1 flex items-center gap-2 px-2 py-1.5 text-left text-[12px] font-semibold cursor-pointer truncate"
									onclick={() => handleDocClick(index, doc.title)}
								>
									<span>{doc.emoji}</span>
									<span class="truncate">{doc.title}</span>
								</button>
								<button id={`doc-menu-trigger-${doc.id}`} type="button" class="dashboard-icon-btn" onclick={() => openDocMenu(doc.id)}>⋯</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- 文档大分类 - 个人笔记 -->
			<div class="space-y-1">
				<button
					type="button"
					class="dashboard-muted dashboard-sidebar-section w-full flex items-center justify-between px-2 py-0.5 text-[10px] font-bold tracking-wider cursor-pointer"
					onclick={() => { personalNotesOpen = !personalNotesOpen; }}
				>
					<span>📝 个人笔记</span>
					<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" class="transition-transform duration-200 {personalNotesOpen ? 'rotate-90' : ''}"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m9 18l6-6l-6-6"/></svg>
				</button>

				{#if personalNotesOpen}
					<div class="space-y-0.5 pl-1">
						{#each docs.filter(d => d.category === '个人笔记') as doc}
							{@const index = docs.findIndex(d => d.id === doc.id)}
							<div class="dashboard-doc-row dashboard-sidebar-doc relative flex items-center gap-1 pr-1 rounded-lg transition-all duration-200 {activeDocIndex === index ? 'is-active font-bold' : ''}">
								<button
									type="button"
									class="flex-1 flex items-center gap-2 px-2 py-1.5 text-left text-[12px] font-semibold cursor-pointer truncate"
									onclick={() => handleDocClick(index, doc.title)}
								>
									<span>{doc.emoji}</span>
									<span class="truncate">{doc.title}</span>
								</button>
								<button id={`doc-menu-trigger-${doc.id}`} type="button" class="dashboard-icon-btn" onclick={() => openDocMenu(doc.id)}>⋯</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>

		</div>

		<!-- 侧边栏底部操作区 -->
		<div class="dashboard-sidebar-footer p-2.5 space-y-1">
			<button
				type="button"
				class="dashboard-list-row dashboard-sidebar-entry dashboard-muted w-full flex items-center gap-2 p-2 rounded-lg text-xs font-bold cursor-pointer transition-all duration-200"
				onclick={() => showGlobalSettingsModal = true}
			>
				<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15a3 3 0 1 0 0-6a3 3 0 0 0 0 6m7.94-2a8.99 8.99 0 0 0 .06-1a8.99 8.99 0 0 0-.06-1l2.12-1.65l-2-3.46l-2.49 1a9.2 9.2 0 0 0-1.73-1l-.38-2.65h-4l-.38 2.65a9.2 9.2 0 0 0-1.73 1l-2.49-1l-2 3.46L4.06 11a8.99 8.99 0 0 0-.06 1a8.99 8.99 0 0 0 .06 1l-2.12 1.65l2 3.46l2.49-1c.53.42 1.11.76 1.73 1l.38 2.65h4l.38-2.65c.62-.24 1.2-.58 1.73-1l2.49 1l2-3.46z"/></svg>
				全局设置
			</button>
			<a
				href="/logout"
				class="dashboard-list-row dashboard-sidebar-entry w-full flex items-center gap-2 p-2 rounded-lg text-xs font-bold cursor-pointer transition-all duration-200"
			>
				<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 8V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2m7-2H9m11-3l3 3l-3 3"/></svg>
				登出
			</a>
		</div>
	</div>

	<!-- =================== 右侧主文档画布 =================== -->
	<div
		bind:this={mainContentNode}
		class="dashboard-main relative flex-1 h-full min-h-0 overflow-y-auto overflow-x-hidden opacity-0"
	>

		<!-- 顶部面包屑与在线协作组 -->
		<div class="dashboard-topbar w-full h-11 px-6 flex items-center justify-between shrink-0 sticky top-0 z-20">
			<div class="flex items-center gap-3 text-xs dashboard-muted font-medium min-w-0">
				<span>工作台</span>
				<span>/</span>
				<span>{activeDoc?.category || ''}</span>
				<span>/</span>
				<span class="dashboard-strong font-semibold flex items-center gap-1 truncate">
					<span>{activeDoc?.emoji || ''}</span>
					<span>{activeDoc?.title || ''}</span>
				</span>
			</div>
			<div class="flex items-center gap-1.5 text-xs dashboard-muted font-medium font-sans shrink-0">
				{#if syncStatus === 'syncing'}
					<span>同步中...</span>
				{:else if syncStatus === 'saved'}
					<span class="status-dot is-saved"></span>
					<span class="status-text is-saved">已同步</span>
				{:else}
					<span class="status-dot is-idle"></span>
					<span>已离线，等待编辑...</span>
				{/if}
			</div>
		</div>

		<!-- 高对比度封面 -->
		<div class="dashboard-cover w-full h-44 relative group overflow-hidden shrink-0">
			<div class="grid-bg absolute inset-0 opacity-60"></div>
			<!-- 科幻淡雅的线性渐变 -->
			<div class="absolute inset-0 bg-gradient-to-tr from-black/20 via-transparent to-white/10"></div>
			<div class="absolute bottom-4 right-6 flex gap-2 opacity-0 group-hover:opacity-100 transition-all duration-300">
				<button type="button" class="dashboard-overlay-btn">🎨 更改封面</button>
				<button type="button" class="dashboard-overlay-btn">📍 调整位置</button>
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
			<div class="mx-auto w-full max-w-4xl -translate-y-10 pb-16 relative" style={`padding-left:${pagePaddingX}px; padding-right:${pagePaddingX}px;`}>

				<!-- 超大 Emoji -->
				<div class="mb-6 flex items-center gap-4">
					<button type="button" class="dashboard-surface dashboard-emoji-trigger" onclick={() => showEmojiPickerModal = true}>
						{activeDoc?.emoji || '📝'}
					</button>
				</div>

				<!-- svelte-ignore a11y_missing_content -->
				<!-- 交互式超大标题 -->
				<h1
					bind:this={titleNode}
					class="dashboard-page-title text-5xl font-black dashboard-strong tracking-tight mb-3 outline-none leading-[1.05]"
					contenteditable={!lockPage}
					spellcheck="false"
					oninput={handleTitleInput}
				>
				</h1>

				<div class="mb-5 flex items-center gap-3 text-xs dashboard-muted">
					<span class="dashboard-chip px-2.5 py-1 font-semibold">/{activeDoc?.category || '未分类'}</span>
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
						class="tiptap-editor-container {editMode === 'markdown' ? 'hidden-editor' : ''}"
						style={`font-size:${docFontSize}px; --dashboard-doc-font:${docFontFamily};`}
						onclick={hideCommandMenu}
					></div>

					{#if editMode === 'markdown'}
						<div class="markdown-split-view">
							<div bind:this={markdownEditorNode} class="markdown-editor-host"></div>
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
							style={`top:${blockHandleTop}px; left:${blockHandleLeft}px;`}
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
								class="dashboard-mode-toggle {editMode === 'rich' ? 'dashboard-btn-primary' : 'dashboard-btn-subtle'}"
							>
								可视化
							</button>
							<button
								type="button"
								onclick={() => toggleEditMode('markdown')}
								class="dashboard-mode-toggle dashboard-mode-toggle-mono {editMode === 'markdown' ? 'dashboard-btn-primary' : 'dashboard-btn-subtle'}"
							>
								Markdown
							</button>

							<div class="toolbar-divider mx-1 h-4 w-px"></div>

							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleBold().run()}
								class="dashboard-toolbar-btn font-bold {editor.isActive('bold') ? 'is-active' : ''}"
								title="加粗"
							>
								B
							</button>
							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleItalic().run()}
								class="dashboard-toolbar-btn italic {editor.isActive('italic') ? 'is-active' : ''}"
								title="斜体"
							>
								I
							</button>
							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleStrike().run()}
								class="dashboard-toolbar-btn line-through {editor.isActive('strike') ? 'is-active' : ''}"
								title="删除线"
							>
								S
							</button>
							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleCode().run()}
								class="dashboard-toolbar-btn font-mono {editor.isActive('code') ? 'is-active' : ''}"
								title="行内代码"
							>
								&lt;/&gt;
							</button>
							<button type="button" onclick={insertLink} class="dashboard-toolbar-btn" title="插入链接" aria-label="插入链接">
								<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10a5 5 0 0 1 7.54.54l.92.93a5 5 0 0 1 0 7.07l-3 3a5 5 0 0 1-7.07 0l-1-1m1.61-8.69a5 5 0 0 1-7.07 0l-1-1a5 5 0 0 1 0-7.07l3-3a5 5 0 0 1 7.07 0l.92.93A5 5 0 0 1 11 14"/></svg>
							</button>
							<button type="button" onclick={insertImage} class="dashboard-toolbar-btn" title="插入图片" aria-label="插入图片">
								<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2m3 6h.01M21 15l-5-5L5 21"/></svg>
							</button>
							<button type="button" onclick={insertSafeHtml} class="dashboard-toolbar-btn">HTML</button>

							<div class="toolbar-divider mx-1 h-4 w-px"></div>

							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
								class="dashboard-toolbar-btn {isEditorActive('heading', { level: 1 }) ? 'is-active font-bold' : ''}"
								title="一级标题"
							>
								H1
							</button>
							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
								class="dashboard-toolbar-btn {isEditorActive('heading', { level: 2 }) ? 'is-active font-bold' : ''}"
								title="二级标题"
							>
								H2
							</button>
							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
								class="dashboard-toolbar-btn {isEditorActive('heading', { level: 3 }) ? 'is-active font-bold' : ''}"
								title="三级标题"
							>
								H3
							</button>

							<div class="toolbar-divider mx-1 h-4 w-px"></div>

							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleBulletList().run()}
								class="dashboard-toolbar-btn {editor.isActive('bulletList') ? 'is-active' : ''}"
								title="无序列表"
							>
								• 无序
							</button>
							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleOrderedList().run()}
								class="dashboard-toolbar-btn {editor.isActive('orderedList') ? 'is-active' : ''}"
								title="有序列表"
							>
								1. 有序
							</button>
							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleBlockquote().run()}
								class="dashboard-toolbar-btn {editor.isActive('blockquote') ? 'is-active' : ''}"
								title="引用块"
							>
								“ 引用
							</button>
							<button
								type="button"
								onclick={() => editor?.chain().focus().toggleCodeBlock().run()}
								class="dashboard-toolbar-btn {editor.isActive('codeBlock') ? 'is-active font-mono' : ''}"
								title="代码块"
							>
								代码块
							</button>

							<div class="toolbar-divider mx-1 h-4 w-px"></div>

							<div
								class="toolbar-popover-wrap"
								onmouseenter={() => {
									showTextColorModal = true;
									showHighlightColorModal = false;
								}}
								onmouseleave={() => showTextColorModal = false}
							>
								<button
									type="button"
									class="dashboard-toolbar-btn font-black {getActiveTextColor() ? 'is-active' : ''}"
									onclick={toggleTextColorPicker}
									title="文本颜色"
								>A</button>
								{#if showTextColorModal}
									<div class="toolbar-color-popover">
										<div class="color-preview h-10" style={`background:${selectedTextColor || '#111827'};`}></div>
										<div class="grid grid-cols-6 gap-2">
											{#each ['oklch(0.22 0.03 258)', 'oklch(0.32 0.12 260)', 'oklch(0.55 0.18 25)', 'oklch(0.62 0.17 145)', 'oklch(0.68 0.15 330)', 'oklch(0.8 0.08 95)', 'oklch(0.92 0.01 250)', 'oklch(0.45 0.2 15)', 'oklch(0.35 0.11 220)', 'oklch(0.72 0.16 80)', 'oklch(0.58 0.22 345)', 'oklch(0.28 0.02 260)'] as color}
												<button type="button" class="preset-swatch" style={`background:${color};`} onclick={() => { selectedTextColor = color; applyTextColor(color); }} aria-label={`文本颜色 ${color}`} title={`文本颜色 ${color}`}></button>
											{/each}
										</div>
										<label class="color-control"><span>Lightness</span><input type="range" min="0" max="100" bind:value={textColorControls.l} oninput={applyCurrentTextColor} class="range theme-range" /></label>
										<label class="color-control"><span>Chroma</span><input type="range" min="0" max="0.37" step="0.005" bind:value={textColorControls.c} oninput={applyCurrentTextColor} class="range theme-range hue-range" /></label>
										<label class="color-control"><span>Hue</span><input type="range" min="0" max="360" bind:value={textColorControls.h} oninput={applyCurrentTextColor} class="range theme-range rainbow-range" /></label>
									</div>
								{/if}
							</div>

							<div
								class="toolbar-popover-wrap"
								onmouseenter={() => {
									showHighlightColorModal = true;
									showTextColorModal = false;
								}}
								onmouseleave={() => showHighlightColorModal = false}
							>
								<button
									type="button"
									class="dashboard-toolbar-btn font-black {getActiveHighlightColor() ? 'is-active' : ''}"
									onclick={toggleHighlightColorPicker}
									title="文字背景色"
								><span class="dashboard-highlight-chip">A</span></button>
								{#if showHighlightColorModal}
									<div class="toolbar-color-popover">
										<div class="color-preview h-10" style={`background:${selectedHighlightColor || '#fef08a'};`}></div>
										<div class="grid grid-cols-6 gap-2">
											{#each ['oklch(0.96 0.08 95)', 'oklch(0.95 0.09 50)', 'oklch(0.92 0.08 145)', 'oklch(0.93 0.08 250)', 'oklch(0.9 0.11 330)', 'oklch(0.87 0.13 20)', 'oklch(0.84 0.1 80)', 'oklch(0.91 0.06 220)', 'oklch(0.89 0.05 20)', 'oklch(0.97 0.03 260)', 'oklch(0.88 0.12 300)', 'oklch(0.82 0.1 170)'] as color}
												<button type="button" class="preset-swatch" style={`background:${color};`} onclick={() => { selectedHighlightColor = color; applyHighlightColor(color); }} aria-label={`背景颜色 ${color}`} title={`背景颜色 ${color}`}></button>
											{/each}
										</div>
										<label class="color-control"><span>Lightness</span><input type="range" min="0" max="100" bind:value={highlightColorControls.l} oninput={applyCurrentHighlightColor} class="range theme-range" /></label>
										<label class="color-control"><span>Chroma</span><input type="range" min="0" max="0.37" step="0.005" bind:value={highlightColorControls.c} oninput={applyCurrentHighlightColor} class="range theme-range hue-range" /></label>
										<label class="color-control"><span>Hue</span><input type="range" min="0" max="360" bind:value={highlightColorControls.h} oninput={applyCurrentHighlightColor} class="range theme-range rainbow-range" /></label>
									</div>
								{/if}
							</div>

							<div class="toolbar-divider mx-1 h-4 w-px"></div>

							<button
								type="button"
								onclick={() => editor?.chain().focus().undo().run()}
								disabled={!editor.can().chain().focus().undo().run()}
								class="dashboard-toolbar-btn"
								title="撤销"
							>
								↩
							</button>
							<button
								type="button"
								onclick={() => editor?.chain().focus().redo().run()}
								disabled={!editor.can().chain().focus().redo().run()}
								class="dashboard-toolbar-btn"
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

	<button type="button" class="page-settings-fab" onclick={() => showPageSettingsModal = true} title="页面设置">
		<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 20h9M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1l1-4z"/></svg>
	</button>

</div>

{#if activeDocMenuId !== null}
	<div class="doc-menu doc-menu-floating" style={`top:${docMenuPosition.top}px; left:${docMenuPosition.left}px;`}>
		<button type="button" onclick={renameActiveDoc}>重命名</button>
		<button type="button" onclick={duplicateActiveDoc}>复制文章</button>
		<button type="button" onclick={() => { showPropertiesModal = true; activeDocMenuId = null; }}>属性</button>
		<button type="button" class="text-error" onclick={deleteActiveDoc}>删除</button>
	</div>
{/if}

{#if showEmojiPickerModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box dashboard-modal-medium">
			<h3 class="dashboard-modal-title">修改文章图标</h3>
			<div class="dashboard-emoji-grid">
				{#each ['📝', '📚', '🚀', '🎨', '📅', '💡', '🔥', '🧠', '📌', '✅', '🧪', '📎', '📘', '📙', '📗', '📕', '📓', '📒', '🗂️', '🗒️', '📋', '🗓️', '💼', '📈', '📊', '📣', '📍', '⭐', '🌙', '☁️', '🍀', '🌱', '🧩', '🛠️', '🖋️', '📰'] as emoji}
					<button type="button" class="dashboard-emoji-option" onclick={() => { customEmojiInput = emoji; updateDocEmoji(); }}>{emoji}</button>
				{/each}
			</div>
			<div class="dashboard-form-row">
				<input type="text" maxlength="4" bind:value={customEmojiInput} class="dashboard-input w-full" placeholder="或自定义输入 emoji" />
				<button type="button" class="dashboard-btn dashboard-btn-primary w-24" onclick={updateDocEmoji}>保存</button>
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showEmojiPickerModal = false}>关闭</button>
			</div>
		</div>
	</div>
{/if}


{#if showPropertiesModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box">
			<h3 class="dashboard-modal-title">页面属性</h3>
			<div class="dashboard-properties-grid">
				<div class="dashboard-property-row"><span class="dashboard-muted">作者</span><span>{activeDoc?.author || userState.session?.user?.username || '未知'}</span></div>
				<div class="dashboard-property-row"><span class="dashboard-muted">创建时间</span><span>{activeDoc?.created_at || '未记录'}</span></div>
				<div class="dashboard-property-row"><span class="dashboard-muted">最后编辑</span><span>{activeDoc?.updated_at || '未记录'}</span></div>
				<div class="dashboard-property-row"><span class="dashboard-muted">分类</span><span>{activeDoc?.category || '未分类'}</span></div>
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showPropertiesModal = false}>关闭</button>
			</div>
		</div>
	</div>
{/if}

{#if showGlobalSettingsModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box dashboard-modal-xlarge">
			<div class="dashboard-global-settings-layout">
				<aside class="dashboard-settings-sidebar">
					<h3 class="dashboard-modal-title">全局设置</h3>
					<div class="dashboard-settings-nav">
						<button type="button" class="dashboard-settings-tab {globalSettingsSection === 'appearance' ? 'is-active' : ''}" onclick={() => globalSettingsSection = 'appearance'}>外观</button>
						<button type="button" class="dashboard-settings-tab {globalSettingsSection === 'editor' ? 'is-active' : ''}" onclick={() => globalSettingsSection = 'editor'}>编辑器</button>
						<button type="button" class="dashboard-settings-tab {globalSettingsSection === 'shortcuts' ? 'is-active' : ''}" onclick={() => globalSettingsSection = 'shortcuts'}>快捷键</button>
						<button type="button" class="dashboard-settings-tab {globalSettingsSection === 'advanced' ? 'is-active' : ''}" onclick={() => globalSettingsSection = 'advanced'}>高级</button>
					</div>
				</aside>
				<div class="dashboard-settings-panel">
					{#if globalSettingsSection === 'appearance'}
						<div class="dashboard-field">
							<span class="dashboard-field-label">主题</span>
							<select bind:value={theme} onchange={() => { applyTheme(); persistDashboardSettings(); }} class="dashboard-select w-full">
								{#each themeOptions as option}
									<option value={option.name}>{option.name}</option>
								{/each}
							</select>
						</div>
						<div class="dashboard-field">
							<span class="dashboard-field-label">全局界面字体</span>
							<select
								bind:value={globalUiFont}
								onchange={() => { applyTheme(); persistDashboardSettings(); }}
								class="dashboard-select w-full"
							>
								{#each fontOptions as option}
									<option value={option.value}>{option.label}</option>
								{/each}
							</select>
						</div>
						<div class="dashboard-placeholder-grid">
							<div class="dashboard-placeholder-card">
								<div class="dashboard-section-label">圆角</div>
								<div class="dashboard-placeholder-line"></div>
								<div class="dashboard-placeholder-line short"></div>
							</div>
							<div class="dashboard-placeholder-card">
								<div class="dashboard-section-label">阴影</div>
								<div class="dashboard-placeholder-line"></div>
								<div class="dashboard-placeholder-line short"></div>
							</div>
						</div>
					{:else if globalSettingsSection === 'editor'}
						<div class="dashboard-placeholder-stack">
							<div class="dashboard-placeholder-card">
								<div class="dashboard-section-label">编辑体验</div>
								<div class="dashboard-placeholder-line"></div>
								<div class="dashboard-placeholder-line"></div>
								<div class="dashboard-placeholder-line short"></div>
							</div>
							<div class="dashboard-placeholder-card">
								<div class="dashboard-section-label">自动化行为</div>
								<div class="dashboard-placeholder-line"></div>
								<div class="dashboard-placeholder-line short"></div>
							</div>
						</div>
					{:else if globalSettingsSection === 'shortcuts'}
						<div class="dashboard-placeholder-stack">
							<div class="dashboard-placeholder-card">
								<div class="dashboard-section-label">键盘快捷键</div>
								<div class="dashboard-placeholder-line"></div>
								<div class="dashboard-placeholder-line"></div>
								<div class="dashboard-placeholder-line"></div>
							</div>
						</div>
					{:else}
						<div class="dashboard-placeholder-stack">
							<div class="dashboard-placeholder-card">
								<div class="dashboard-section-label">高级选项</div>
								<div class="dashboard-placeholder-line"></div>
								<div class="dashboard-placeholder-line"></div>
								<div class="dashboard-placeholder-line short"></div>
							</div>
						</div>
					{/if}
				</div>
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showGlobalSettingsModal = false}>关闭</button>
			</div>
		</div>
	</div>
{/if}

{#if showPageSettingsModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box dashboard-modal-large">
			<h3 class="dashboard-modal-title">页面设置</h3>
			<div class="dashboard-settings-grid">
				<div class="w-full">
					<div class="dashboard-field-label">左右边距</div>
					<input type="range" min="24" max="96" bind:value={pagePaddingX} oninput={persistDashboardSettings} class="theme-range dashboard-range" step="18" />
					<div class="dashboard-range-ticks"><span>|</span><span>|</span><span>|</span><span>|</span><span>|</span></div>
					<div class="dashboard-range-labels"><span>窄</span><span></span><span>中</span><span></span><span>宽</span></div>
				</div>
				<div class="w-full">
					<div class="dashboard-field-label">字体大小</div>
					<input type="range" min="14" max="22" bind:value={docFontSize} oninput={() => { applyTheme(); persistDashboardSettings(); }} class="theme-range dashboard-range" step="2" />
					<div class="dashboard-range-ticks"><span>|</span><span>|</span><span>|</span><span>|</span><span>|</span></div>
					<div class="dashboard-range-labels"><span>14</span><span>16</span><span>18</span><span>20</span><span>22</span></div>
				</div>
				<label class="dashboard-field">
					<span class="dashboard-field-label">字体</span>
					<select bind:value={docFontFamily} onchange={() => { applyTheme(); persistDashboardSettings(); }} class="dashboard-select w-full">
						{#each fontOptions as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</label>
				<label class="dashboard-checkbox-row">
					<input type="checkbox" class="dashboard-checkbox" bind:checked={lockPage} onchange={persistDashboardSettings} />
					<span>锁定页面，防止修改</span>
				</label>
				<div class="dashboard-field">
					<div class="dashboard-field-label">页面操作</div>
					<div class="dashboard-action-row">
						<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={copyPageContent}>复制页面内容</button>
						<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={exportMarkdown}>导出 Markdown</button>
						<label class="dashboard-btn dashboard-btn-subtle">
							导入 Markdown
							<input type="file" accept=".md,text/markdown" class="hidden" onchange={importMarkdownFile} />
						</label>
					</div>
				</div>
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showPageSettingsModal = false}>关闭</button>
			</div>
		</div>
	</div>
{/if}

<!-- 用户管理弹窗组件 -->
{#if showUserManagement}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="dashboard-modal-backdrop"
		onclick={() => showUserManagement = false}
	>
		<div
			class="dashboard-modal-box dashboard-modal-large"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="dashboard-modal-header">
				<h3 class="dashboard-modal-title dashboard-modal-title-inline">
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" class="dashboard-muted"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2m8-10a4 4 0 1 0 0-8a4 4 0 0 0 0 8m14 10v-2a4 4 0 0 0-3-3.87m-4-12a4 4 0 0 1 0 7.75"/></svg>
					用户管理
				</h3>
				<button
					type="button"
					class="dashboard-icon-btn"
					onclick={() => showUserManagement = false}
				>✕</button>
			</div>

			<!-- 用户列表表格 -->
			<div class="space-y-2">
				<h4 class="dashboard-section-label">当前用户列表</h4>
				<div class="dashboard-table-wrap">
					<table class="dashboard-table">
						<thead>
							<tr>
								<th class="py-2.5 px-4 text-left">用户名</th>
								<th class="py-2.5 px-4 text-left">权限角色</th>
								<th class="py-2.5 px-4 text-center">操作</th>
							</tr>
						</thead>
						<tbody>
							{#each userList as user}
								<tr>
									<td class="py-2.5 px-4 font-medium">{user.username}</td>
									<td class="py-2.5 px-4">
										<span class="dashboard-badge">{user.role}</span>
									</td>
									<td class="py-2.5 px-4 text-center">
										{#if user.username === 'sout'}
											<span class="dashboard-helper-text">系统内置</span>
										{:else}
											<button
												type="button"
												class="dashboard-btn dashboard-btn-danger"
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
			<form onsubmit={handleAddUser} class="dashboard-form-section">
				<h4 class="dashboard-section-label">添加新用户</h4>
				<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
					<div class="space-y-1">
						<label for="new-username" class="dashboard-input-label">用户名</label>
						<input
							id="new-username"
							type="text"
							placeholder="请输入用户名"
							bind:value={newUsername}
							required
							class="dashboard-input"
						/>
					</div>
					<div class="space-y-1">
						<label for="new-password" class="dashboard-input-label">密码</label>
						<input
							id="new-password"
							type="password"
							placeholder="请输入密码"
							bind:value={newPassword}
							required
							class="dashboard-input"
						/>
					</div>
					<div class="space-y-1">
						<label for="new-role" class="dashboard-input-label">选择权限</label>
						<select
							id="new-role"
							bind:value={newRole}
							class="dashboard-select"
						>
							<option value="root">root</option>
							<option value="管理员">管理员</option>
							<option value="用户">用户</option>
						</select>
					</div>
				</div>
				<button
					type="submit"
					class="dashboard-btn dashboard-btn-primary w-full justify-center mt-2"
				>
					添加用户
				</button>
			</form>
		</div>
	</div>
{/if}

<style>
	:global(:root) {
		--dashboard-fg: oklch(0.24 0.03 258);
		--dashboard-bg: oklch(0.98 0.01 95);
		--dashboard-panel: oklch(0.995 0.005 95);
		--dashboard-sidebar: oklch(0.96 0.015 95);
		--dashboard-accent: oklch(0.72 0.13 20);
		--dashboard-gradient-from: oklch(0.99 0.015 95);
		--dashboard-gradient-to: oklch(0.95 0.02 75);
		--dashboard-radius: 22px;
		--dashboard-shadow: 16px;
		--dashboard-padding: 16px;
		--dashboard-gap: 12px;
		--dashboard-ui-font: Outfit;
		--dashboard-doc-font: 'Noto Sans SC';
		--dashboard-muted-fg: color-mix(in oklab, var(--dashboard-fg) 62%, transparent);
		--dashboard-soft-fg: color-mix(in oklab, var(--dashboard-fg) 44%, transparent);
		--dashboard-border: color-mix(in oklab, var(--dashboard-fg) 10%, transparent);
		--dashboard-border-strong: color-mix(in oklab, var(--dashboard-fg) 16%, transparent);
		--dashboard-soft-bg: color-mix(in oklab, var(--dashboard-fg) 5%, transparent);
		--dashboard-hover-bg: color-mix(in oklab, var(--dashboard-fg) 8%, transparent);
		--dashboard-active-bg: color-mix(in oklab, var(--dashboard-accent) 18%, var(--dashboard-panel));
		--dashboard-shadow-color: color-mix(in oklab, var(--dashboard-fg) 14%, transparent);
		--dashboard-code-bg: color-mix(in oklab, var(--dashboard-fg) 88%, var(--dashboard-bg));
		--dashboard-code-fg: color-mix(in oklab, var(--dashboard-bg) 88%, white);
		--dashboard-inline-code-bg: color-mix(in oklab, var(--dashboard-fg) 8%, transparent);
		--dashboard-quote-bg: color-mix(in oklab, var(--dashboard-accent) 8%, var(--dashboard-panel));
		--dashboard-modal-backdrop: color-mix(in oklab, black 32%, transparent);
	}

	.dashboard-shell {
		background:
			linear-gradient(135deg, var(--dashboard-gradient-from), var(--dashboard-gradient-to));
		color: var(--dashboard-fg);
		font-family: var(--dashboard-ui-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	.dashboard-sidebar {
		background: var(--dashboard-sidebar);
		border-right: 1px solid var(--dashboard-border);
	}

	.dashboard-main {
		background: var(--dashboard-bg);
	}

	.dashboard-topbar {
		border-bottom: 1px solid color-mix(in oklab, var(--dashboard-fg) 8%, transparent);
		background: color-mix(in oklab, var(--dashboard-panel) 86%, transparent);
		backdrop-filter: blur(18px);
	}

	.dashboard-muted {
		color: var(--dashboard-muted-fg);
	}

	.dashboard-strong {
		color: var(--dashboard-fg);
	}

	.dashboard-surface {
		background: var(--dashboard-panel);
		border: 1px solid var(--dashboard-border);
	}

	.dashboard-chip {
		display: inline-flex;
		align-items: center;
		border-radius: calc(var(--dashboard-radius) * 0.55);
		background: color-mix(in oklab, var(--dashboard-fg) 6%, transparent);
		color: var(--dashboard-fg);
	}

	.dashboard-btn-primary {
		background: var(--dashboard-fg);
		color: var(--dashboard-bg);
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 14%, transparent);
	}

	.dashboard-btn-subtle {
		background: var(--dashboard-soft-bg);
		color: color-mix(in oklab, var(--dashboard-fg) 78%, transparent);
		border: 1px solid var(--dashboard-border);
	}

	.dashboard-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.45rem;
		min-height: 2.35rem;
		border-radius: calc(var(--dashboard-radius) * 0.48);
		padding: 0.58rem 0.9rem;
		font-size: 0.82rem;
		font-weight: 700;
		line-height: 1;
		cursor: pointer;
		transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
	}

	.dashboard-btn:hover {
		transform: translateY(-1px);
	}

	.dashboard-btn-danger {
		background: color-mix(in oklab, oklch(0.62 0.24 24) 82%, var(--dashboard-panel));
		color: white;
		border: 1px solid color-mix(in oklab, oklch(0.62 0.24 24) 40%, transparent);
	}

	.dashboard-btn-danger:hover {
		background: color-mix(in oklab, oklch(0.62 0.24 24) 92%, var(--dashboard-panel));
	}

	.dashboard-mode-toggle {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: 1px solid transparent;
		border-radius: 999px;
		padding: 0.42rem 0.82rem;
		font-size: 0.75rem;
		font-weight: 700;
		cursor: pointer;
		transition: all 160ms ease;
	}

	.dashboard-mode-toggle-mono {
		font-family: "JetBrains Mono", monospace;
	}

	.dashboard-list-row {
		color: color-mix(in oklab, var(--dashboard-fg) 96%, transparent);
		transition: background-color 160ms ease, color 160ms ease;
	}

	.dashboard-list-row:hover {
		background: var(--dashboard-hover-bg);
	}

	.dashboard-sidebar-card {
		padding-block: 0.45rem;
	}

	.dashboard-sidebar-entry {
		min-height: 2rem;
	}

	.dashboard-sidebar-section {
		color: var(--dashboard-soft-fg);
	}

	.dashboard-doc-row {
		color: var(--dashboard-fg);
	}

	.dashboard-doc-row:hover {
		background: var(--dashboard-hover-bg);
	}

	.dashboard-doc-row.is-active {
		background: var(--dashboard-active-bg);
	}

	.dashboard-sidebar-doc button {
		min-height: 2rem;
	}

	.dashboard-icon-btn {
		display: inline-flex;
		height: 1.9rem;
		width: 1.9rem;
		align-items: center;
		justify-content: center;
		border: 1px solid transparent;
		border-radius: 999px;
		background: transparent;
		color: var(--dashboard-muted-fg);
		font-size: 0.95rem;
		font-weight: 700;
		cursor: pointer;
		transition: all 160ms ease;
	}

	.dashboard-icon-btn:hover {
		background: var(--dashboard-hover-bg);
		color: var(--dashboard-fg);
		border-color: var(--dashboard-border);
	}

	.dashboard-sidebar-footer {
		border-top: 1px solid var(--dashboard-border);
	}

	.dashboard-avatar {
		background: color-mix(in oklab, var(--dashboard-accent) 22%, var(--dashboard-panel));
		color: var(--dashboard-fg);
		border: 1px solid var(--dashboard-border);
	}

	.status-dot {
		display: inline-block;
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 999px;
	}

	.status-dot.is-syncing {
		background: oklch(0.82 0.13 88);
		animation: pulse 1.4s infinite;
	}

	.status-dot.is-saved {
		background: oklch(0.72 0.17 150);
	}

	.status-dot.is-idle {
		background: color-mix(in oklab, var(--dashboard-fg) 28%, transparent);
	}

	.status-text.is-saved {
		color: color-mix(in oklab, oklch(0.72 0.17 150) 72%, var(--dashboard-fg));
		font-weight: 700;
	}

	.dashboard-cover {
		border-bottom: 1px solid var(--dashboard-border);
		background:
			radial-gradient(circle at top left, color-mix(in oklab, var(--dashboard-accent) 30%, transparent), transparent 32%),
			linear-gradient(
				135deg,
				color-mix(in oklab, var(--dashboard-fg) 6%, var(--dashboard-bg)),
				color-mix(in oklab, var(--dashboard-accent) 12%, var(--dashboard-bg))
			);
	}

	.dashboard-page-title {
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	.dashboard-overlay-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: 1px solid color-mix(in oklab, white 16%, transparent);
		border-radius: calc(var(--dashboard-radius) * 0.42);
		background: color-mix(in oklab, var(--dashboard-panel) 68%, transparent);
		color: var(--dashboard-fg);
		padding: 0.45rem 0.7rem;
		font-size: 0.72rem;
		font-weight: 700;
		backdrop-filter: blur(14px);
		cursor: pointer;
	}

	.dashboard-overlay-btn:hover {
		background: color-mix(in oklab, var(--dashboard-panel) 86%, transparent);
	}

	.dashboard-emoji-trigger {
		position: relative;
		z-index: 10;
		display: flex;
		height: 5rem;
		width: 5rem;
		align-items: center;
		justify-content: center;
		border-radius: calc(var(--dashboard-radius) * 1.05);
		box-shadow: 0 10px 28px var(--dashboard-shadow-color);
		font-size: 3.5rem;
		cursor: pointer;
		transition: transform 160ms ease;
	}

	.dashboard-emoji-trigger:hover {
		transform: scale(1.04);
	}

	.dashboard-modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 50;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		background: var(--dashboard-modal-backdrop);
		backdrop-filter: blur(14px);
	}

	.dashboard-modal-box {
		width: min(100%, 36rem);
		max-height: 85vh;
		overflow-y: auto;
		border: 1px solid var(--dashboard-border-strong);
		border-radius: calc(var(--dashboard-radius) * 1.1);
		background: color-mix(in oklab, var(--dashboard-panel) 96%, transparent);
		padding: 1.4rem;
		box-shadow: 0 28px 64px var(--dashboard-shadow-color);
		color: var(--dashboard-fg);
	}

	.dashboard-modal-medium {
		width: min(100%, 42rem);
	}

	.dashboard-modal-large {
		width: min(100%, 52rem);
	}

	.dashboard-modal-xlarge {
		width: min(100%, 64rem);
	}

	.dashboard-modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-bottom: 0.8rem;
		margin-bottom: 1rem;
		border-bottom: 1px solid var(--dashboard-border);
	}

	.dashboard-modal-title {
		font-size: 1.05rem;
		font-weight: 800;
		color: var(--dashboard-fg);
	}

	.dashboard-modal-title-inline {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
	}

	.dashboard-modal-body {
		margin-top: 1rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.dashboard-modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
		margin-top: 1.15rem;
	}

	.dashboard-global-settings-layout {
		display: grid;
		grid-template-columns: 13rem minmax(0, 1fr);
		gap: 1.25rem;
	}

	.dashboard-settings-sidebar {
		padding-right: 1rem;
		border-right: 1px solid var(--dashboard-border);
	}

	.dashboard-settings-nav {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		margin-top: 1rem;
	}

	.dashboard-settings-tab {
		display: flex;
		align-items: center;
		width: 100%;
		min-height: 2.35rem;
		border: 1px solid transparent;
		border-radius: calc(var(--dashboard-radius) * 0.45);
		background: transparent;
		padding: 0.55rem 0.75rem;
		color: var(--dashboard-muted-fg);
		font-size: 0.82rem;
		font-weight: 700;
		text-align: left;
		cursor: pointer;
		transition: all 160ms ease;
	}

	.dashboard-settings-tab:hover {
		background: var(--dashboard-hover-bg);
		color: var(--dashboard-fg);
	}

	.dashboard-settings-tab.is-active {
		background: var(--dashboard-active-bg);
		color: var(--dashboard-fg);
		border-color: color-mix(in oklab, var(--dashboard-accent) 24%, transparent);
	}

	.dashboard-settings-panel {
		min-width: 0;
	}

	.dashboard-placeholder-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1rem;
		margin-top: 1rem;
	}

	.dashboard-placeholder-stack {
		display: grid;
		gap: 1rem;
		margin-top: 0.5rem;
	}

	.dashboard-placeholder-card {
		border: 1px solid var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.7);
		background: color-mix(in oklab, var(--dashboard-panel) 90%, var(--dashboard-bg));
		padding: 1rem;
	}

	.dashboard-placeholder-line {
		height: 0.7rem;
		margin-top: 0.75rem;
		border-radius: 999px;
		background: color-mix(in oklab, var(--dashboard-fg) 10%, transparent);
	}

	.dashboard-placeholder-line.short {
		width: 68%;
	}

	.dashboard-emoji-grid {
		margin-top: 1rem;
		display: grid;
		grid-template-columns: repeat(6, minmax(0, 1fr));
		gap: 0.65rem;
		max-height: 18rem;
		overflow-y: auto;
	}

	.dashboard-emoji-option {
		display: inline-flex;
		height: 3rem;
		align-items: center;
		justify-content: center;
		border: 1px solid transparent;
		border-radius: calc(var(--dashboard-radius) * 0.45);
		background: transparent;
		font-size: 1.6rem;
		cursor: pointer;
		transition: background-color 160ms ease, border-color 160ms ease, transform 160ms ease;
	}

	.dashboard-emoji-option:hover {
		background: var(--dashboard-hover-bg);
		border-color: var(--dashboard-border);
		transform: translateY(-1px);
	}

	.dashboard-form-row {
		margin-top: 1rem;
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.dashboard-field {
		margin-top: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.dashboard-field-label {
		font-size: 0.84rem;
		font-weight: 700;
		color: var(--dashboard-muted-fg);
	}

	.dashboard-input-label {
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.04em;
		color: var(--dashboard-soft-fg);
	}

	.dashboard-input,
	.dashboard-select {
		width: 100%;
		min-height: 2.6rem;
		border: 1px solid var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.55);
		background: color-mix(in oklab, var(--dashboard-panel) 88%, var(--dashboard-bg));
		padding: 0.65rem 0.85rem;
		color: var(--dashboard-fg);
		font-size: 0.8rem;
		outline: none;
		transition: border-color 160ms ease, background-color 160ms ease, box-shadow 160ms ease;
	}

	.dashboard-input:focus,
	.dashboard-select:focus {
		border-color: color-mix(in oklab, var(--dashboard-accent) 46%, var(--dashboard-fg));
		box-shadow: 0 0 0 3px color-mix(in oklab, var(--dashboard-accent) 14%, transparent);
	}

	.dashboard-checkbox-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		font-size: 0.9rem;
	}

	.dashboard-checkbox {
		width: 1rem;
		height: 1rem;
		accent-color: color-mix(in oklab, var(--dashboard-accent) 75%, var(--dashboard-fg));
	}

	.dashboard-settings-grid {
		margin-top: 1.25rem;
		display: grid;
		gap: 1.5rem;
	}

	@media (min-width: 768px) {
		.dashboard-settings-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	.dashboard-action-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.65rem;
	}

	.dashboard-range {
		width: 100%;
	}

	.dashboard-range-ticks,
	.dashboard-range-labels {
		display: flex;
		justify-content: space-between;
		padding-inline: 0.625rem;
		margin-top: 0.5rem;
		font-size: 0.75rem;
		color: var(--dashboard-muted-fg);
	}

	:global([data-theme='dark']) .dashboard-sidebar {
		background: oklch(0 0 0);
	}

	:global([data-theme='dark']) .dashboard-sidebar .dashboard-list-row,
	:global([data-theme='dark']) .dashboard-sidebar .dashboard-strong,
	:global([data-theme='dark']) .dashboard-sidebar .dashboard-doc-row {
		color: oklch(0.97 0 0);
	}

	:global([data-theme='dark']) .dashboard-sidebar .dashboard-muted,
	:global([data-theme='dark']) .dashboard-sidebar .dashboard-sidebar-section {
		color: color-mix(in oklab, white 70%, transparent);
	}

	:global([data-theme='dark']) .dashboard-sidebar .dashboard-list-row:hover,
	:global([data-theme='dark']) .dashboard-sidebar .dashboard-doc-row:hover,
	:global([data-theme='dark']) .dashboard-sidebar .dashboard-doc-row.is-active {
		background: color-mix(in oklab, white 8%, transparent);
	}

	:global([data-theme='dark']) .dashboard-sidebar .dashboard-icon-btn {
		color: color-mix(in oklab, white 72%, transparent);
	}

	:global([data-theme='dark']) .dashboard-sidebar .dashboard-icon-btn:hover {
		color: white;
		border-color: color-mix(in oklab, white 12%, transparent);
	}

	@media (max-width: 900px) {
		.dashboard-global-settings-layout {
			grid-template-columns: 1fr;
		}

		.dashboard-settings-sidebar {
			padding-right: 0;
			padding-bottom: 1rem;
			border-right: none;
			border-bottom: 1px solid var(--dashboard-border);
		}

		.dashboard-settings-nav {
			flex-direction: row;
			flex-wrap: wrap;
		}

		.dashboard-placeholder-grid {
			grid-template-columns: 1fr;
		}
	}

	.dashboard-properties-grid {
		margin-top: 1rem;
		display: grid;
		gap: 0.8rem;
	}

	.dashboard-property-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		border-bottom: 1px solid var(--dashboard-border);
		padding-bottom: 0.65rem;
		font-size: 0.9rem;
	}

	.dashboard-table-wrap {
		overflow: hidden;
		border: 1px solid var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.9);
		background: color-mix(in oklab, var(--dashboard-panel) 90%, var(--dashboard-bg));
	}

	.dashboard-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.8rem;
		color: var(--dashboard-fg);
	}

	.dashboard-table thead tr {
		background: var(--dashboard-soft-bg);
		color: var(--dashboard-muted-fg);
	}

	.dashboard-table tbody tr {
		border-top: 1px solid var(--dashboard-border);
	}

	.dashboard-table th,
	.dashboard-table td {
		padding: 0.7rem 1rem;
		text-align: left;
	}

	.dashboard-table th:last-child,
	.dashboard-table td:last-child {
		text-align: center;
	}

	.dashboard-badge {
		display: inline-flex;
		align-items: center;
		border-radius: 999px;
		background: var(--dashboard-soft-bg);
		border: 1px solid var(--dashboard-border);
		padding: 0.25rem 0.55rem;
		font-size: 0.74rem;
		font-weight: 700;
		color: var(--dashboard-fg);
	}

	.dashboard-helper-text {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--dashboard-soft-fg);
	}

	.dashboard-form-section {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding-top: 1rem;
		margin-top: 0.5rem;
		border-top: 1px solid var(--dashboard-border);
	}

	.dashboard-section-label {
		font-size: 0.72rem;
		font-weight: 800;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--dashboard-soft-fg);
	}

	/* 隐藏浏览器原装选区，让协作光标显得更加纯粹 */
	::selection {
		background: color-mix(in oklab, var(--dashboard-accent) 22%, transparent);
	}

	/* Tiptap 内部排版样式：Notion 极简、高保真质感 */
	:global(.tiptap) {
		outline: none;
		min-height: 480px;
		font-size: var(--dashboard-doc-size, 16px);
		line-height: 1.75;
		color: var(--dashboard-fg);
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	:global(.tiptap > *) {
		position: relative;
		margin-inline: -0.75rem;
		border-radius: 0.9rem;
		padding: 0.14rem 0.75rem;
		transition: background-color 180ms ease, transform 180ms ease;
	}

	:global(.tiptap > :not(pre):not(hr):hover) {
		background: var(--dashboard-hover-bg);
	}

	:global(.tiptap p) {
		margin-bottom: 0.9em;
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	:global(.tiptap h1) {
		font-size: 1.9rem;
		font-weight: 800;
		margin-top: 1.75em;
		margin-bottom: 0.65em;
		color: var(--dashboard-fg);
		letter-spacing: -0.03em;
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	:global(.tiptap h2) {
		font-size: 1.45rem;
		font-weight: 750;
		margin-top: 1.55em;
		margin-bottom: 0.6em;
		color: var(--dashboard-fg);
		letter-spacing: -0.02em;
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	:global(.tiptap h3) {
		font-size: 1.18rem;
		font-weight: 600;
		margin-top: 1.4em;
		margin-bottom: 0.5em;
		color: color-mix(in oklab, var(--dashboard-fg) 92%, transparent);
		letter-spacing: -0.01em;
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	:global(.tiptap ul) {
		list-style-type: disc;
		padding-left: 1.8rem;
		margin-bottom: 0.8em;
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	:global(.tiptap ol) {
		list-style-type: decimal;
		padding-left: 1.6rem;
		margin-bottom: 0.8em;
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	:global(.tiptap li) {
		margin-bottom: 0.3em;
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	:global(.tiptap blockquote) {
		display: block;
		border-left: 3px solid color-mix(in oklab, var(--dashboard-accent) 36%, var(--dashboard-fg));
		padding: 0.95rem 0.5rem 0.95rem 1.15rem;
		font-style: italic;
		color: color-mix(in oklab, var(--dashboard-fg) 76%, transparent);
		margin: 1.5em 0;
		background: var(--dashboard-quote-bg);
		border-radius: 0 0.9rem 0.9rem 0;
		line-height: 1.72;
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
	}

	:global(.tiptap blockquote > :first-child) {
		margin-top: 0;
	}

	:global(.tiptap blockquote > :last-child) {
		margin-bottom: 0;
	}

	:global(.tiptap pre) {
		background-color: var(--dashboard-code-bg);
		color: var(--dashboard-code-fg);
		padding: 1.25rem;
		border-radius: 1rem;
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		font-size: 0.85em;
		overflow-x: auto;
		margin: 1.5em 0;
		box-shadow: inset 0 2px 6px color-mix(in oklab, black 22%, transparent);
	}

	:global(.tiptap pre:hover) {
		background-color: var(--dashboard-code-bg);
	}

	:global(.tiptap code) {
		background-color: var(--dashboard-inline-code-bg);
		padding: 0.15em 0.3em;
		border-radius: 0.25em;
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		font-size: 0.9em;
		color: var(--dashboard-fg);
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
		border-top: 1px solid var(--dashboard-border);
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

	.markdown-editor-host {
		min-height: 480px;
		padding-bottom: 5.5rem;
	}

	:global(.cm-editor) {
		height: 100%;
		background: transparent;
		font: 500 14px/1.85 "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
		color: var(--dashboard-fg);
	}

	:global(.cm-gutters) {
		border-right: 1px solid var(--dashboard-border);
		background: transparent;
		color: var(--dashboard-soft-fg);
	}

	:global(.cm-scroller) {
		font-family: "JetBrains Mono", monospace;
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
		border: 1px solid var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.7);
		background: var(--dashboard-panel);
		padding: 0.7rem 0.85rem;
		box-shadow: 0 16px 40px var(--dashboard-shadow-color);
		backdrop-filter: blur(14px);
	}

	.dashboard-toolbar-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 2rem;
		padding: 0.4rem 0.58rem;
		border: 1px solid transparent;
		border-radius: calc(var(--dashboard-radius) * 0.4);
		background: transparent;
		color: var(--dashboard-fg);
		font-size: 0.74rem;
		line-height: 1;
		cursor: pointer;
		transition: all 160ms ease;
	}

	.dashboard-toolbar-btn:hover {
		background: var(--dashboard-hover-bg);
		border-color: var(--dashboard-border);
	}

	.dashboard-toolbar-btn.is-active {
		background: var(--dashboard-active-bg);
		border-color: color-mix(in oklab, var(--dashboard-accent) 34%, transparent);
	}

	.dashboard-toolbar-btn:disabled {
		opacity: 0.35;
		cursor: not-allowed;
	}

	.toolbar-divider {
		background: var(--dashboard-border);
	}

	.toolbar-popover-wrap {
		position: relative;
		display: inline-flex;
	}

	.toolbar-color-popover {
		position: absolute;
		left: 50%;
		bottom: calc(100% + 0.75rem);
		transform: translateX(-50%);
		z-index: 60;
		width: 20rem;
		border: 1px solid var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.6);
		background: color-mix(in oklab, var(--dashboard-panel) 96%, transparent);
		padding: 0.8rem;
		box-shadow: 0 18px 40px var(--dashboard-shadow-color);
		backdrop-filter: blur(16px);
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
		border: 1px solid var(--dashboard-border);
		border-radius: 999px;
		background: color-mix(in oklab, var(--dashboard-panel) 96%, transparent);
		color: var(--dashboard-muted-fg);
		font-weight: 700;
		box-shadow: 0 8px 18px var(--dashboard-shadow-color);
		cursor: pointer;
		transition: all 160ms ease;
	}

	.handle-button:hover {
		background: var(--dashboard-fg);
		color: var(--dashboard-bg);
	}

	.handle-drag {
		font-size: 0.75rem;
		letter-spacing: -0.1em;
	}

	.command-menu {
		position: absolute;
		z-index: 35;
		width: 18rem;
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 8%, transparent);
		border-radius: calc(var(--dashboard-radius) * 0.55);
		background: var(--dashboard-panel);
		padding: 0.55rem;
		box-shadow: 0 24px 48px var(--dashboard-shadow-color);
		backdrop-filter: blur(18px);
	}

	.command-menu-header {
		padding: 0.4rem 0.55rem 0.55rem;
		color: var(--dashboard-soft-fg);
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
		background: var(--dashboard-hover-bg);
	}

	.command-item-title {
		color: var(--dashboard-fg);
		font-size: 0.86rem;
		font-weight: 700;
	}

	.command-item-hint {
		color: var(--dashboard-soft-fg);
		font-size: 0.75rem;
	}

	.command-empty {
		padding: 0.7rem;
		color: var(--dashboard-soft-fg);
		font-size: 0.82rem;
	}

	.doc-menu {
		position: absolute;
		right: 0;
		top: calc(100% + 0.2rem);
		z-index: 40;
		display: flex;
		width: 10.5rem;
		max-width: 10.5rem;
		flex-direction: column;
		gap: 0.1rem;
		border: 1px solid var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.55);
		background: var(--dashboard-panel);
		padding: 0.35rem;
		box-shadow: 0 18px 40px var(--dashboard-shadow-color);
		backdrop-filter: blur(18px);
	}

	.doc-menu-floating {
		position: fixed;
	}

	.doc-menu button {
		border: none;
		background: transparent;
		padding: 0.55rem 0.7rem;
		border-radius: 0.7rem;
		text-align: left;
		cursor: pointer;
	}

	.doc-menu button:hover {
		background: var(--dashboard-hover-bg);
	}

	.page-settings-fab {
		position: fixed;
		right: 1.4rem;
		bottom: 1.4rem;
		z-index: 45;
		display: flex;
		height: 3.25rem;
		width: 3.25rem;
		align-items: center;
		justify-content: center;
		border: 1px solid var(--dashboard-border);
		border-radius: 999px;
		background: var(--dashboard-panel);
		color: var(--dashboard-fg);
		box-shadow: 0 16px 36px var(--dashboard-shadow-color);
		cursor: pointer;
	}

	.preset-swatch {
		height: 2rem;
		width: 100%;
		border-radius: calc(var(--dashboard-radius) * 0.35);
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 12%, transparent);
		cursor: pointer;
	}

	.theme-range {
		margin-top: 0.35rem;
		appearance: none;
		height: 0.5rem;
		border-radius: 999px;
		background: transparent;
	}

	.theme-range::-webkit-slider-runnable-track {
		height: 0.5rem;
		border-radius: 999px;
		background:
			linear-gradient(
				90deg,
				color-mix(in oklab, var(--dashboard-bg) 92%, black),
				color-mix(in oklab, var(--dashboard-panel) 72%, var(--dashboard-accent)),
				color-mix(in oklab, white 84%, var(--dashboard-accent))
			);
	}

	.theme-range::-webkit-slider-thumb {
		appearance: none;
		margin-top: -4px;
		width: 1rem;
		height: 1rem;
		border-radius: 999px;
		border: 2px solid var(--dashboard-panel);
		background: var(--dashboard-fg);
		box-shadow: 0 2px 10px var(--dashboard-shadow-color);
	}

	.hue-range::-webkit-slider-runnable-track {
		background: linear-gradient(90deg, #ff4d4d, #ffd24d, #61ff4d, #4dfff3, #4d7cff, #cf4dff, #ff4d9d, #ff4d4d);
	}

	.rainbow-range::-webkit-slider-runnable-track {
		background: linear-gradient(90deg, #ff3b30, #ff9500, #ffcc00, #34c759, #00c7be, #007aff, #5856d6, #af52de, #ff2d55);
	}

	.color-preview {
		height: 2.2rem;
		border-radius: calc(var(--dashboard-radius) * 0.35);
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 10%, transparent);
	}

	.color-control {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: 0.8rem;
		color: var(--dashboard-fg);
	}

	.dashboard-highlight-chip {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.05rem 0.25rem;
		border-radius: 0.35rem;
		background: color-mix(in oklab, var(--dashboard-accent) 20%, transparent);
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
		color: var(--dashboard-soft-fg);
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	.markdown-preview-body {
		color: color-mix(in oklab, var(--dashboard-fg) 94%, transparent);
		font-size: var(--dashboard-doc-size, 16px);
		line-height: 1.75;
		font-family: var(--dashboard-doc-font), 'Noto Sans SC', 'Noto Serif SC', sans-serif;
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
		display: block;
		border-left: 3px solid color-mix(in oklab, var(--dashboard-accent) 36%, var(--dashboard-fg));
		padding: 0.95rem 0.5rem 0.95rem 1.15rem;
		font-style: italic;
		color: color-mix(in oklab, var(--dashboard-fg) 76%, transparent);
		background: var(--dashboard-quote-bg);
		border-radius: 0 0.9rem 0.9rem 0;
		line-height: 1.72;
	}

	.markdown-preview-body :global(blockquote > :first-child) {
		margin-top: 0;
	}

	.markdown-preview-body :global(blockquote > :last-child) {
		margin-bottom: 0;
	}

	.markdown-preview-body :global(pre) {
		overflow-x: auto;
		border-radius: 1rem;
		background: var(--dashboard-code-bg);
		padding: 1rem 1.15rem;
		color: var(--dashboard-code-fg);
	}

	.markdown-preview-body :global(code) {
		border-radius: 0.35rem;
		background: var(--dashboard-inline-code-bg);
		padding: 0.15rem 0.32rem;
	}

	@keyframes pulse {
		0%, 100% {
			opacity: 1;
		}

		50% {
			opacity: 0.4;
		}
	}
</style>
