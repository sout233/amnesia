<script lang="ts">
	import { userState } from '$lib/userData.svelte';
	import { toast } from '$lib/toastQueue.svelte';
	import { onMount, onDestroy, tick } from 'svelte';
	import { animate } from 'animejs';
	import { goto } from '$app/navigation';
	import { getUsers, addUser, deleteUser, type UserRecord } from '$lib/userDatabase';
	import { supabase } from '$lib/supabaseClient';
	import { listAccessibleDocs, createDoc as createSpaceDoc, updateDoc } from '$lib/docs/docService';
	import { decryptDocumentContent, deriveDocEncryptionKey, encryptDocumentContent } from '$lib/crypto/appCrypto';
	import { loginWithPassword, setUserEncryptionReady, updateUserAvatar } from '$lib/auth/authService';
	import { acceptTeamInvite, createTeam, createTeamInvite, listTeamInvites, listUserTeams } from '$lib/teams/teamService';
	import type { DocSpaceType, TeamInviteRecord, TeamRecord } from '$lib/types/domain';
	import { Editor, Node as TiptapNode, mergeAttributes } from '@tiptap/core';
	import StarterKit from '@tiptap/starter-kit';
	import Link from '@tiptap/extension-link';
	import Image from '@tiptap/extension-image';
	import { TextStyle } from '@tiptap/extension-text-style';
	import Color from '@tiptap/extension-color';
	import Highlight from '@tiptap/extension-highlight';
	import TaskList from '@tiptap/extension-task-list';
	import TaskItem from '@tiptap/extension-task-item';
	import Mention from '@tiptap/extension-mention';
	import { Table } from '@tiptap/extension-table';
	import TableRow from '@tiptap/extension-table-row';
	import TableHeader from '@tiptap/extension-table-header';
	import TableCell from '@tiptap/extension-table-cell';
	import { marked } from 'marked';
	import TurndownService from 'turndown';
	import DOMPurify from 'dompurify';
	import ThemedSelect, { type ThemedSelectOption } from '$lib/components/ThemedSelect.svelte';
	import { EditorState } from '@codemirror/state';
	import { history, redo as codeMirrorRedo, redoSelection, undo as codeMirrorUndo, undoSelection } from '@codemirror/commands';
	import {
		EditorView,
		lineNumbers,
		highlightActiveLineGutter,
		keymap,
		scrollPastEnd
	} from '@codemirror/view';
	import { markdown as markdownLanguage } from '@codemirror/lang-markdown';

	const RawHtmlEmbed = TiptapNode.create({
		name: 'rawHtmlEmbed',
		group: 'block',
		atom: true,
		draggable: true,
		selectable: true,
		isolating: true,

		addAttributes() {
			return {
				html: {
					default: ''
				}
			};
		},

		parseHTML() {
			return [
				{
					tag: 'div[data-html-embed-block]',
					getAttrs: (element) => ({
						html: element instanceof HTMLElement ? element.getAttribute('data-raw-html') ?? '' : ''
					})
				}
			];
		},

		renderHTML({ HTMLAttributes }) {
			const { html, ...rest } = HTMLAttributes;
			return [
				'div',
				mergeAttributes(rest, {
					class: 'raw-html-embed-shell',
					'data-html-embed-block': 'true',
					'data-raw-html': typeof html === 'string' ? html : ''
				})
			];
		},

		addNodeView() {
			return ({ node }) => {
				const dom = document.createElement('div');
				dom.className = 'raw-html-embed-shell';
				dom.setAttribute('data-html-embed-block', 'true');
				dom.setAttribute('contenteditable', 'false');

				const content = document.createElement('div');
				content.className = 'raw-html-embed-render';
				content.innerHTML = sanitizeHtml(String(node.attrs.html ?? ''));
				dom.appendChild(content);

				return { dom };
			};
		}
	});

	type DocRecord = {
		id: number;
		emoji: string;
		title: string;
		category: string;
		content: string;
		space_type?: DocSpaceType;
		owner_user_id?: string | number | null;
		team_id?: string | number | null;
		is_encrypted?: boolean;
		encryption_version?: number;
		settings?: Record<string, unknown>;
		created_at?: string;
		updated_at?: string;
		author?: string;
	};

	let sidebarNode = $state<HTMLElement | null>(null);
	let mainContentNode = $state<HTMLElement | null>(null);
	let dashboardShellNode = $state<HTMLElement | null>(null);
	let dashboardMotionCleanup: (() => void) | null = null;

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
	let markdownDirty = $state(false);
	let htmlContent = $state('');
	let editMode = $state<'rich' | 'html' | 'markdown'>('rich');
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
	let showUserProfileModal = $state(false);
	let showQuickSearchModal = $state(false);
	let isMobileViewport = $state(false);
	let mobileSidebarOpen = $state(false);
	let mobileToolbarExpanded = $state(false);
	let mobileToolbarDragOffset = $state(0);
	let lockPage = $state(false);
	let theme = $state('cupcake');
	let pagePaddingX = $state(48);
	let docFontSize = $state(16);
	let docFontFamily = $state('Noto Sans SC');
	let globalUiFont = $state('Noto Sans SC');
	let globalSettingsSection = $state<'appearance' | 'editor' | 'shortcuts' | 'advanced'>('appearance');
	let customEmojiInput = $state('');
	let activeDocMenuId = $state<number | null>(null);
	let propertiesDocId = $state<number | null>(null);
	let selectedTextColor = $state('#111827');
	let selectedHighlightColor = $state('#fef08a');
	let activeTextColorState = $state('');
	let activeHighlightColorState = $state('');
	let docMenuPosition = $state({ top: 0, left: 0 });
	let docMenuNode = $state<HTMLElement | null>(null);
	let tableContextMenuOpen = $state(false);
	let tableContextMenuPosition = $state({ top: 0, left: 0 });
	let tableContextMenuNode = $state<HTMLElement | null>(null);
	let showTextColorModal = $state(false);
	let showHighlightColorModal = $state(false);
	let textColorControls = $state({ l: 24, c: 0.03, h: 258, a: 1 });
	let highlightColorControls = $state({ l: 92, c: 0.08, h: 95, a: 1 });
	let showLinkModal = $state(false);
	let showImageModal = $state(false);
	let showHtmlModal = $state(false);
	let showRenameModal = $state(false);
	let showDeleteDocModal = $state(false);
	let showDeleteUserModal = $state(false);
	let showCreateDocModal = $state(false);
	let showCreateFolderModal = $state(false);
	let showEncryptionSetupModal = $state(false);
	let showTeamWorkspaceModal = $state(false);
	let showMarkdownWarningModal = $state(false);
	let pendingEditMode = $state<'markdown' | null>(null);
	let linkUrlInput = $state('');
	let linkTextInput = $state('');
	let imageUrlInput = $state('');
	let htmlEmbedInput = $state('');
	let renameInput = $state('');
	let pendingDeleteUsername = $state('');
	let newDocTitleInput = $state('');
	let newDocCategoryInput = $state('个人笔记');
	let newFolderInput = $state('');
	let newDocFolderInput = $state('');
	let pendingFolderSpace = $state<SpaceCategory>('个人笔记');
	let renameFolderInput = $state('');
	let moveFolderTarget = $state('');
	let encryptionPasswordInput = $state('');
	let currentTeamId = $state<string | number | null>(null);
	let currentTeamIdValue = $state('');
	let teams = $state<Array<TeamRecord & { memberRole?: string }>>([]);
	let teamInvites = $state<TeamInviteRecord[]>([]);
	let inviteTokenInput = $state('');
	let newTeamName = $state('');
	let newTeamSlug = $state('');
	let savedEditorSelection = $state<{ from: number; to: number } | null>(null);
	let avatarUploading = $state(false);
	let quickSearchInput = $state('');
	let quickSearchInputNode = $state<HTMLInputElement | null>(null);
	let showSyncStatusPopover = $state(false);
	let lastSavedAt = $state<string | null>(null);
	let spaceContextMenuOpen = $state(false);
	let spaceContextMenuNode = $state<HTMLElement | null>(null);
	let spaceContextMenuPosition = $state({ top: 0, left: 0 });
	let spaceContextMenuCategory = $state<SpaceCategory>('个人笔记');
	let spaceContextMenuFolder = $state('');
	let showRenameFolderModal = $state(false);
	let showDeleteFolderModal = $state(false);
	let showMoveFolderModal = $state(false);
	let mobileToolbarRootNode = $state<HTMLElement | null>(null);
	let mobileToolbarSheetNode = $state<HTMLElement | null>(null);
	let mobileToolbarOverlayNode = $state<HTMLElement | null>(null);
	let collapsedFolderKeys = $state<Record<string, boolean>>({});
	let draggingDocId = $state<number | null>(null);
	let sidebarDropIndicator = $state<{ top: number; width: number; left: number; visible: boolean }>({
		top: 0,
		width: 0,
		left: 0,
		visible: false
	});
	let blockDragIndicator = $state<{ top: number; visible: boolean }>({ top: 0, visible: false });

	type EncryptedDocPayload = {
		type: 'amnesia-encrypted-doc';
		version: number;
		iv: string;
		cipherText: string;
	};

	type ThemePreset = 'cupcake' | 'shadcn' | 'ibm' | 'far in blue sky...';
	type SpaceCategory = 'Amnesia 共享文章' | '团队工作区' | '个人笔记';
	type SpaceContextAction = 'doc' | 'folder';
	type SidebarDocRef = { doc: DocRecord; index: number };
	type MentionDocItem = {
		id: string;
		label: string;
		title: string;
		emoji: string;
		index: number;
	};
	type SidebarFolderEntry = {
		key: string;
		name: string;
		docs: SidebarDocRef[];
		order: number;
		placeholderDocId?: number;
	};

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

	(turndownService as unknown as {
		addRule: (
			key: string,
			rule: {
				filter: (node: Node) => boolean;
				replacement: (content: string, node: Node) => string;
			}
		) => void;
	}).addRule('preserveInlineStyledNodes', {
		filter: (node: Node) =>
			node instanceof HTMLElement &&
			(node.hasAttribute('data-inline-styled') ||
				node.tagName === 'MARK' ||
				(node.tagName === 'SPAN' && node.hasAttribute('style'))),
		replacement: (_content: string, node: Node) => (node as HTMLElement).outerHTML
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

	function rememberEditorSelection() {
		if (!editor) return;
		savedEditorSelection = {
			from: editor.state.selection.from,
			to: editor.state.selection.to
		};
	}

	function restoreEditorSelection() {
		if (!editor || !savedEditorSelection) return;
		editor.chain().focus().setTextSelection(savedEditorSelection).run();
	}

	function syncViewportState() {
		if (typeof window === 'undefined') return;
		isMobileViewport = window.innerWidth <= 900;
		if (!isMobileViewport) {
			mobileSidebarOpen = false;
			mobileToolbarExpanded = false;
		}
	}

	function openUserProfileModal() {
		showUserProfileModal = true;
		requestAnimationFrame(() => {
			animateModalEnter('.dashboard-user-profile-modal:not([data-modal-entered="1"])');
			const panel = document.querySelector('.dashboard-user-profile-modal');
			if (panel instanceof HTMLElement) {
				animate(panel, {
					opacity: [0, 1],
					translateY: [18, 0],
					scale: [0.97, 1],
					duration: 260,
					ease: 'outExpo',
					onComplete: () => {
						panel.style.removeProperty('transform');
						panel.style.opacity = '1';
					}
				});
			}
		});
	}

	function getDocPlainText(html: string) {
		if (typeof document === 'undefined') return html;
		const temp = document.createElement('div');
		temp.innerHTML = html;
		return (temp.textContent || temp.innerText || '').replace(/\s+/g, ' ').trim();
	}

	function getDocMentionItems(query = ''): MentionDocItem[] {
		const normalized = query.trim().toLowerCase();
		return docs
			.map((doc, index) => ({
				id: String(doc.id),
				label: doc.title,
				title: doc.title,
				emoji: doc.emoji || '📝',
				index
			}))
			.filter((item) => !normalized || item.title.toLowerCase().includes(normalized))
			.slice(0, 8);
	}

	function mentionDocToHref(docId: string) {
		return `amnesia://doc/${docId}`;
	}

	function buildMentionHref(docId: string) {
		const item = docs.find((doc) => String(doc.id) === docId);
		return item ? mentionDocToHref(docId) : '#';
	}

	function getDocByMentionId(docId: string) {
		return docs.find((doc) => String(doc.id) === docId) ?? null;
	}

	function selectMentionDocById(docId: string) {
		const index = docs.findIndex((doc) => String(doc.id) === docId);
		if (index < 0) return;
		handleDocClick(index, docs[index].title);
	}

	function createMentionSuggestionConfig() {
		return {
			char: '@',
			allowSpaces: true,
			items: ({ query }: { query: string }) => getDocMentionItems(query),
			command: ({ editor, range, props }: { editor: Editor; range: { from: number; to: number }; props: MentionDocItem }) => {
				editor
					.chain()
					.focus()
					.insertContentAt(range, [
						{
							type: 'mention',
							attrs: {
								id: props.id,
								label: props.title
							}
						},
						{ type: 'text', text: ' ' }
					])
					.run();
			},
			render: () => {
				let popup: HTMLDivElement | null = null;
				let selectedIndex = 0;
				let currentItems: MentionDocItem[] = [];

				const syncSelection = () => {
					if (!popup) return;
					Array.from(popup.querySelectorAll<HTMLButtonElement>('[data-mention-item-index]')).forEach((button) => {
						const buttonIndex = Number(button.dataset.mentionItemIndex ?? '-1');
						button.classList.toggle('is-selected', buttonIndex === selectedIndex);
					});
				};

				const renderItems = () => {
					if (!popup) return;
					if (currentItems.length === 0) {
						popup.innerHTML = `
							<div class="mention-menu-header">
								<div class="mention-menu-kicker">@ 链接到文章</div>
								<div class="mention-menu-subtitle">没有找到匹配项</div>
							</div>
						`;
						return;
					}
					popup.innerHTML = [
						`
							<div class="mention-menu-header">
								<div class="mention-menu-kicker">@ 链接到文章</div>
								<div class="mention-menu-subtitle">选择一篇文档插入为可点击引用</div>
							</div>
						`,
						...currentItems.map(
							(item, index) => `
								<button type="button" class="command-item mention-command-item ${index === selectedIndex ? 'is-selected' : ''}" data-mention-item-index="${index}">
									<span class="mention-command-main">
										<span class="mention-command-emoji">${item.emoji}</span>
										<span class="mention-command-copy">
											<span class="mention-command-title">${item.title}</span>
											<span class="mention-command-meta">点击后跳转到该页面</span>
										</span>
									</span>
									<span class="mention-command-shortcut">@</span>
								</button>
							`
						)
					].join('');
					Array.from(popup.querySelectorAll<HTMLButtonElement>('[data-mention-item-index]')).forEach((button) => {
						button.onclick = () => {
							const idx = Number(button.dataset.mentionItemIndex ?? '-1');
							if (idx >= 0 && currentItems[idx]) {
								selectedIndex = idx;
								syncSelection();
							}
						};
					});
				};

				return {
					onStart: (props: any) => {
						currentItems = props.items ?? [];
						selectedIndex = 0;
						popup = document.createElement('div');
						popup.className = 'command-menu mention-command-menu';
						popup.style.position = 'fixed';
						popup.style.left = `${props.clientRect?.()?.left ?? 0}px`;
						popup.style.top = `${(props.clientRect?.()?.bottom ?? 0) + 10}px`;
						document.body.appendChild(popup);
						renderItems();
						Array.from(popup.querySelectorAll<HTMLButtonElement>('[data-mention-item-index]')).forEach((button) => {
							button.onclick = () => {
								const idx = Number(button.dataset.mentionItemIndex ?? '-1');
								if (idx >= 0 && currentItems[idx]) {
									props.command(currentItems[idx]);
								}
							};
						});
						animate(popup, {
							opacity: [0, 1],
							translateY: [-6, 0],
							duration: 180,
							ease: 'outQuad'
						});
					},
					onUpdate: (props: any) => {
						currentItems = props.items ?? [];
						selectedIndex = 0;
						if (popup && props.clientRect) {
							popup.style.left = `${props.clientRect().left}px`;
							popup.style.top = `${props.clientRect().bottom + 10}px`;
						}
						renderItems();
						Array.from(popup?.querySelectorAll<HTMLButtonElement>('[data-mention-item-index]') ?? []).forEach((button) => {
							button.onclick = () => {
								const idx = Number(button.dataset.mentionItemIndex ?? '-1');
								if (idx >= 0 && currentItems[idx]) {
									props.command(currentItems[idx]);
								}
							};
						});
					},
					onKeyDown: (props: any) => {
						if (!currentItems.length) {
							return props.event.key === 'Escape';
						}
						if (props.event.key === 'ArrowDown') {
							selectedIndex = (selectedIndex + 1) % currentItems.length;
							syncSelection();
							return true;
						}
						if (props.event.key === 'ArrowUp') {
							selectedIndex = (selectedIndex - 1 + currentItems.length) % currentItems.length;
							syncSelection();
							return true;
						}
						if (props.event.key === 'Enter') {
							props.command(currentItems[selectedIndex]);
							return true;
						}
						if (props.event.key === 'Escape') {
							popup?.remove();
							popup = null;
							return true;
						}
						return false;
					},
					onExit: () => {
						popup?.remove();
						popup = null;
					}
				};
			}
		};
	}

	function animateMobileToolbar(expanded: boolean, immediate = false) {
		if (!mobileToolbarSheetNode || !mobileToolbarOverlayNode) return;
		const overlay = mobileToolbarOverlayNode;
		if (expanded) {
			overlay.style.display = 'flex';
		}
		const expandedHeight = overlay.scrollHeight;
		const targetHeight = expanded ? expandedHeight : 0;
		animate(overlay, {
			height: [overlay.offsetHeight || 0, targetHeight],
			opacity: expanded ? [0, 1] : [1, 0],
			duration: immediate ? 0 : 260,
			ease: 'outExpo',
			onComplete: () => {
				overlay.style.height = expanded ? 'auto' : '0px';
				overlay.style.opacity = expanded ? '1' : '0';
				overlay.style.display = expanded ? 'flex' : 'none';
			}
		});
		animate(mobileToolbarSheetNode, {
			translateY: [mobileToolbarDragOffset, 0],
			duration: immediate ? 0 : 280,
			ease: 'outExpo',
			onComplete: () => {
				if (mobileToolbarSheetNode) {
					mobileToolbarSheetNode.style.removeProperty('transform');
				}
			}
		});
		mobileToolbarDragOffset = 0;
	}

	function setMobileToolbarExpanded(next: boolean, immediate = false) {
		if (mobileToolbarExpanded === next && !immediate) return;
		mobileToolbarExpanded = next;
		requestAnimationFrame(() => animateMobileToolbar(next, immediate));
	}

	function toggleMobileToolbar() {
		setMobileToolbarExpanded(!mobileToolbarExpanded);
	}

	function bindMobileToolbarGesture(node: HTMLElement) {
		let pointerId: number | null = null;
		let startY = 0;
		let startOffset = 0;
		let dragging = false;

		const onPointerDown = (event: PointerEvent) => {
			const target = event.target as HTMLElement | null;
			if (!target?.closest('.dashboard-mobile-toolbar-sheet-handle-wrap, .dashboard-mobile-toolbar-bar')) return;
			pointerId = event.pointerId;
			startY = event.clientY;
			startOffset = mobileToolbarDragOffset;
			dragging = true;
			node.setPointerCapture(pointerId);
		};

		const onPointerMove = (event: PointerEvent) => {
			if (!dragging || event.pointerId !== pointerId || !mobileToolbarSheetNode) return;
			const delta = event.clientY - startY;
			const limit = mobileToolbarExpanded ? 180 : 240;
			mobileToolbarDragOffset = Math.max(-limit, Math.min(limit, startOffset + delta));
			mobileToolbarSheetNode.style.transform = `translateY(${mobileToolbarDragOffset}px)`;
		};

		const finishGesture = (event: PointerEvent) => {
			if (!dragging || event.pointerId !== pointerId) return;
			dragging = false;
			if (pointerId != null && node.hasPointerCapture(pointerId)) {
				node.releasePointerCapture(pointerId);
			}
			const threshold = mobileToolbarExpanded ? 72 : -56;
			const shouldExpand = mobileToolbarExpanded
				? mobileToolbarDragOffset < 72
				: mobileToolbarDragOffset < threshold;
			const shouldCollapse = mobileToolbarExpanded && mobileToolbarDragOffset > 72;
			if (shouldCollapse) {
				setMobileToolbarExpanded(false);
			} else if (shouldExpand) {
				setMobileToolbarExpanded(true);
			} else {
				animateMobileToolbar(mobileToolbarExpanded);
			}
			pointerId = null;
		};

		node.addEventListener('pointerdown', onPointerDown);
		node.addEventListener('pointermove', onPointerMove);
		node.addEventListener('pointerup', finishGesture);
		node.addEventListener('pointercancel', finishGesture);

		return {
			destroy() {
				node.removeEventListener('pointerdown', onPointerDown);
				node.removeEventListener('pointermove', onPointerMove);
				node.removeEventListener('pointerup', finishGesture);
				node.removeEventListener('pointercancel', finishGesture);
			}
		};
	}

	function runUndo() {
		if (editMode === 'rich') {
			editor?.chain().focus().undo().run();
			return;
		}
		if (markdownEditorView) {
			codeMirrorUndo(markdownEditorView);
		}
	}

	function runRedo() {
		if (editMode === 'rich') {
			editor?.chain().focus().redo().run();
			return;
		}
		if (markdownEditorView) {
			codeMirrorRedo(markdownEditorView);
		}
	}

	function canUndo() {
		if (editMode === 'rich') {
			return !!editor?.can().chain().focus().undo().run();
		}
		return !!markdownEditorView;
	}

	function canRedo() {
		if (editMode === 'rich') {
			return !!editor?.can().chain().focus().redo().run();
		}
		return !!markdownEditorView;
	}

	function openQuickSearchModal() {
		showQuickSearchModal = true;
		requestAnimationFrame(() => {
			animateModalEnter('.dashboard-quick-search-modal:not([data-modal-entered="1"])');
			quickSearchInputNode?.focus();
			quickSearchInputNode?.select();
		});
	}

	function closeQuickSearchModal() {
		showQuickSearchModal = false;
		quickSearchInput = '';
	}

	function animateCurrentDocView() {
		if (titleNode) {
			animate(titleNode, {
				opacity: [0.72, 1],
				translateY: [10, 0],
				duration: 320,
				ease: 'outExpo',
				onComplete: () => {
					titleNode?.style.removeProperty('transform');
					if (titleNode) titleNode.style.opacity = '1';
				}
			});
		}

		if (editorShellNode) {
			animate(editorShellNode, {
				opacity: [0.8, 1],
				translateY: [12, 0],
				duration: 360,
				delay: 40,
				ease: 'outExpo',
				onComplete: () => {
					editorShellNode?.style.removeProperty('transform');
					if (editorShellNode) editorShellNode.style.opacity = '1';
				}
			});
		}
	}

	function animateModalEnter(
		boxSelector = '.dashboard-modal-box:not([data-modal-entered="1"])',
		backdropSelector = '.dashboard-modal-backdrop:not([data-backdrop-entered="1"])'
	) {
		const backdrops = Array.from(document.querySelectorAll(backdropSelector));
		for (const backdrop of backdrops) {
			if (!(backdrop instanceof HTMLElement)) continue;
			backdrop.dataset.backdropEntered = '1';
			animate(backdrop, {
				opacity: [0, 1],
				duration: 170,
				ease: 'outQuad'
			});
		}

		const boxes = Array.from(document.querySelectorAll(boxSelector));
		for (const box of boxes) {
			if (!(box instanceof HTMLElement)) continue;
			box.dataset.modalEntered = '1';
			animate(box, {
				opacity: [0, 1],
				translateY: [18, 0],
				scale: [0.975, 1],
				duration: 240,
				ease: 'outExpo',
				onComplete: () => {
					box.style.removeProperty('transform');
					box.style.opacity = '1';
				}
			});
		}
	}

	function animateSectionToggle(section: 'global' | 'team' | 'private', open: boolean) {
		const selector =
			section === 'global'
				? '.dashboard-global-panel'
				: section === 'team'
					? '.dashboard-team-panel'
					: '.dashboard-private-panel';
		const panel = dashboardShellNode?.querySelector(selector);
		if (!(panel instanceof HTMLElement)) return;

		animate(panel, {
			opacity: open ? [0, 1] : [1, 0.7],
			translateY: open ? [-8, 0] : [0, -4],
			duration: 220,
			ease: 'outExpo',
			onComplete: () => {
				panel.style.removeProperty('transform');
				panel.style.opacity = '1';
			}
		});
	}

	function wireDashboardMotion(root: HTMLElement) {
		const interactiveSelector = [
			'.dashboard-btn',
			'.dashboard-icon-btn',
			'.dashboard-list-row',
			'.dashboard-doc-row',
			'.dashboard-folder-add-btn',
			'.dashboard-mode-toggle',
			'.dashboard-overlay-btn',
			'.dashboard-emoji-trigger',
			'.page-settings-fab',
			'.handle-button',
			'.themed-select-option'
		].join(', ');

		const shouldIgnoreTransition = (element: HTMLElement) =>
			element.classList.contains('dashboard-doc-row') ||
			element.classList.contains('dashboard-list-row') ||
			element.classList.contains('themed-select-option');

		const isTransformSensitive = (element: HTMLElement) =>
			element.matches(
				'.dashboard-select-trigger, .editor-toolbar-overlay, .toolbar-color-popover, .block-handle, .command-menu, .doc-menu, .themed-select-panel'
			);

		const animateHoverIn = (element: HTMLElement) => {
			if (isTransformSensitive(element)) return;
			const scale = element.classList.contains('page-settings-fab') ? 1.035 : 1.018;
			const rise = element.classList.contains('dashboard-doc-row') ? -1.5 : -2;
			animate(element, {
				scale,
				translateY: rise,
				duration: 180,
				ease: 'outQuad'
			});
		};

		const animateHoverOut = (element: HTMLElement) => {
			if (isTransformSensitive(element)) return;
			animate(element, {
				scale: 1,
				translateY: 0,
				duration: 180,
				ease: 'outQuad'
			});
		};

		const animatePress = (element: HTMLElement) => {
			if (isTransformSensitive(element)) return;
			animate(element, {
				scale: 0.985,
				duration: 120,
				ease: 'outQuad'
			});
		};

		const animateRelease = (element: HTMLElement) => {
			if (isTransformSensitive(element)) return;
			animate(element, {
				scale: element.matches(':hover') ? 1.018 : 1,
				translateY: element.matches(':hover') ? -1.5 : 0,
				duration: 160,
				ease: 'outQuad'
			});
		};

		const animateInsertedNode = (node: HTMLElement) => {
			if (node.dataset.motionAnimated === '1') return;

			if (node.matches('.dashboard-modal-backdrop')) {
				node.dataset.motionAnimated = '1';
				animate(node, {
					opacity: [0, 1],
					duration: 180,
					ease: 'outQuad'
				});
				return;
			}

			if (node.matches('.dashboard-modal-box')) {
				node.dataset.motionAnimated = '1';
				animate(node, {
					opacity: [0, 1],
					translateY: [18, 0],
					scale: [0.975, 1],
					duration: 260,
					ease: 'outExpo'
				});
				return;
			}

			if (node.matches('.doc-menu, .command-menu')) {
				node.dataset.motionAnimated = '1';
				animate(node, {
					opacity: [0, 1],
					duration: 140,
					ease: 'outQuad'
				});
				return;
			}

			if (node.matches('.dashboard-collapsible-panel')) {
				node.dataset.motionAnimated = '1';
				animate(node, {
					opacity: [0, 1],
					translateY: [-8, 0],
					duration: 220,
					ease: 'outExpo',
					onComplete: () => {
						node.style.removeProperty('transform');
						node.style.opacity = '1';
					}
				});
				return;
			}

			if (
				node.matches(
					'.dashboard-doc-row, .dashboard-list-row'
				)
			) {
				node.dataset.motionAnimated = '1';
				animate(node, {
					opacity: [0, 1],
					translateY: [10, 0],
					duration: 240,
					ease: 'outExpo',
					onComplete: () => {
						node.style.removeProperty('transform');
						node.style.opacity = '1';
					}
				});
			}
		};

		const animateTree = (startNode: ParentNode) => {
			const candidates = Array.from(
				startNode.querySelectorAll?.(
					'.dashboard-modal-backdrop, .dashboard-modal-box, .doc-menu, .command-menu, .dashboard-collapsible-panel, .dashboard-doc-row, .dashboard-list-row'
				) ?? []
			);

			if (startNode instanceof HTMLElement) {
				candidates.unshift(startNode);
			}

			for (const candidate of candidates) {
				if (candidate instanceof HTMLElement) {
					animateInsertedNode(candidate);
				}
			}
		};

		const handlePointerOver = (event: Event) => {
			const target = event.target;
			if (!(target instanceof HTMLElement)) return;
			const interactive = target.closest(interactiveSelector);
			if (!(interactive instanceof HTMLElement)) return;
			const related = event instanceof PointerEvent ? event.relatedTarget : null;
			if (related instanceof Node && interactive.contains(related)) return;
			animateHoverIn(interactive);
		};

		const handlePointerOut = (event: Event) => {
			const target = event.target;
			if (!(target instanceof HTMLElement)) return;
			const interactive = target.closest(interactiveSelector);
			if (!(interactive instanceof HTMLElement)) return;
			const related = event instanceof PointerEvent ? event.relatedTarget : null;
			if (related instanceof Node && interactive.contains(related)) return;
			animateHoverOut(interactive);
		};

		const handlePointerDown = (event: Event) => {
			const target = event.target;
			if (!(target instanceof HTMLElement)) return;
			const interactive = target.closest(interactiveSelector);
			if (!(interactive instanceof HTMLElement)) return;
			animatePress(interactive);
		};

		const handlePointerUp = (event: Event) => {
			const target = event.target;
			if (!(target instanceof HTMLElement)) return;
			const interactive = target.closest(interactiveSelector);
			if (!(interactive instanceof HTMLElement)) return;
			animateRelease(interactive);
		};

		const handleFocusIn = (event: Event) => {
			const target = event.target;
			if (!(target instanceof HTMLElement)) return;
			const interactive = target.closest(interactiveSelector);
			if (!(interactive instanceof HTMLElement)) return;
			if (shouldIgnoreTransition(interactive)) return;
			if (isTransformSensitive(interactive)) return;
			animate(interactive, {
				scale: 1.012,
				translateY: -1,
				duration: 160,
				ease: 'outQuad'
			});
		};

		const handleFocusOut = (event: Event) => {
			const target = event.target;
			if (!(target instanceof HTMLElement)) return;
			const interactive = target.closest(interactiveSelector);
			if (!(interactive instanceof HTMLElement)) return;
			if (shouldIgnoreTransition(interactive)) return;
			if (isTransformSensitive(interactive)) return;
			animate(interactive, {
				scale: 1,
				translateY: 0,
				duration: 160,
				ease: 'outQuad'
			});
		};

		const observer = new MutationObserver((records) => {
			for (const record of records) {
				for (const node of Array.from(record.addedNodes)) {
					if (node instanceof HTMLElement) {
						animateTree(node);
					}
				}
			}
		});

		root.addEventListener('pointerover', handlePointerOver);
		root.addEventListener('pointerout', handlePointerOut);
		root.addEventListener('pointerdown', handlePointerDown);
		root.addEventListener('pointerup', handlePointerUp);
		root.addEventListener('focusin', handleFocusIn);
		root.addEventListener('focusout', handleFocusOut);

		observer.observe(root, { childList: true, subtree: true });
		animateTree(root);

		return () => {
			root.removeEventListener('pointerover', handlePointerOver);
			root.removeEventListener('pointerout', handlePointerOut);
			root.removeEventListener('pointerdown', handlePointerDown);
			root.removeEventListener('pointerup', handlePointerUp);
			root.removeEventListener('focusin', handleFocusIn);
			root.removeEventListener('focusout', handleFocusOut);
			observer.disconnect();
		};
	}

	function syncUserProfile(
		nextUser: Partial<{
			id?: string | number;
			username: string;
			role: import('$lib/types/domain').SystemRole;
			encryptionReady?: boolean;
			encryptionNoticeAccepted?: boolean;
			docEncryptionKey?: string;
			avatarSeed?: string | null;
			avatarUrl?: string | null;
		}>
	) {
		const session = userState.session;
		if (!session) return;
		userState.setSession({
			user: {
				...session.user,
				...nextUser
			}
		});
	}

	async function randomizeUserAvatar() {
		const session = userState.session;
		if (!session?.user?.id) return;
		const username = userState.session?.user?.username || 'amnesia';
		const randomSeed = `${username}-${crypto.randomUUID()}`;
		const updated = await updateUserAvatar({
			userId: session.user.id,
			avatarSeed: randomSeed,
			avatarUrl: null
		});
		syncUserProfile({
			avatarSeed: updated.avatarSeed ?? randomSeed,
			avatarUrl: updated.avatarUrl ?? null
		});
		toast.success('已生成随机头像');
	}

	async function resetUserAvatar() {
		const session = userState.session;
		if (!session?.user?.id) return;
		const username = userState.session?.user?.username || 'amnesia';
		const updated = await updateUserAvatar({
			userId: session.user.id,
			avatarSeed: username,
			avatarUrl: null
		});
		syncUserProfile({
			avatarSeed: updated.avatarSeed ?? username,
			avatarUrl: updated.avatarUrl ?? null
		});
		toast.success('已恢复默认头像');
	}

	async function compressAvatarImage(file: File) {
		const imageUrl = URL.createObjectURL(file);
		try {
			const image = await new Promise<HTMLImageElement>((resolve, reject) => {
				const img = new window.Image();
				img.onload = () => resolve(img);
				img.onerror = () => reject(new Error('头像读取失败'));
				img.src = imageUrl;
			});

			const maxSide = 512;
			const scale = Math.min(1, maxSide / Math.max(image.width, image.height));
			const targetWidth = Math.max(1, Math.round(image.width * scale));
			const targetHeight = Math.max(1, Math.round(image.height * scale));

			const canvas = document.createElement('canvas');
			canvas.width = targetWidth;
			canvas.height = targetHeight;
			const context = canvas.getContext('2d');
			if (!context) {
				throw new Error('头像压缩失败');
			}

			context.clearRect(0, 0, targetWidth, targetHeight);
			context.drawImage(image, 0, 0, targetWidth, targetHeight);

			const outputType = file.type === 'image/png' ? 'image/png' : 'image/jpeg';
			const quality = outputType === 'image/png' ? undefined : 0.82;

			return await new Promise<string>((resolve, reject) => {
				canvas.toBlob(
					(blob) => {
						if (!blob) {
							reject(new Error('头像压缩失败'));
							return;
						}
						const reader = new FileReader();
						reader.onload = () => {
							if (typeof reader.result === 'string') resolve(reader.result);
							else reject(new Error('头像压缩失败'));
						};
						reader.onerror = () => reject(new Error('头像压缩失败'));
						reader.readAsDataURL(blob);
					},
					outputType,
					quality
				);
			});
		} finally {
			URL.revokeObjectURL(imageUrl);
		}
	}

	async function uploadCustomAvatar(file: File) {
		const session = userState.session;
		if (!session?.user?.id) return;
		if (!file.type.startsWith('image/')) {
			toast.error('请上传图片文件');
			return;
		}
		avatarUploading = true;
		try {
			const dataUrl = await compressAvatarImage(file);

			const updated = await updateUserAvatar({
				userId: session.user.id,
				avatarUrl: dataUrl,
				avatarSeed: session.user.avatarSeed || session.user.username
			});
			syncUserProfile({
				avatarSeed: updated.avatarSeed ?? session.user.username,
				avatarUrl: updated.avatarUrl ?? dataUrl
			});
			toast.success('自定义头像已上传');
		} catch (error: any) {
			const message = String(error?.message ?? '');
			if (message.includes('avatar_seed') || message.includes('avatar_url')) {
				toast.error('头像字段尚未完成数据库迁移，请先运行 scripts/init-db.py 后重试');
			} else {
				toast.error(error?.message ?? '头像上传失败');
			}
		} finally {
			avatarUploading = false;
		}
	}

	function logoutCurrentUser() {
		userState.setSession(null);
		goto('/login');
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
			panel: 'oklch(0.995 0.005 95 / 0.82)',
			sidebar: 'oklch(0.96 0.015 95 / 0.86)',
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
			name: 'far in blue sky...',
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

	const teamSelectOptions = $derived.by<ThemedSelectOption[]>(() =>
		teams.map((team) => ({
			value: String(team.id),
			label: team.name,
			hint: team.memberRole ? `身份：${team.memberRole}` : undefined
		}))
	);

	const createDocSpaceOptions = [
		{ value: 'Amnesia 共享文章', label: '🌍 全局文章', hint: '所有用户都能看到' },
		{ value: '团队工作区', label: '👥 团队文章', hint: '仅当前团队成员可见' },
		{ value: '个人笔记', label: '🔒 私有文章', hint: '仅你自己可见并加密存储' }
	] satisfies ThemedSelectOption[];

	const themeSelectOptions = $derived.by<ThemedSelectOption[]>(() =>
		themeOptions.map((option) => ({
			value: option.name,
			label: option.name,
			hint:
				option.name === 'cupcake'
					? '从DaisyUI抄过来的'
					: option.name === 'shadcn'
						? '从Vercel那里抄过来的'
						: option.name === 'ibm'
							? '从IBM那里抄过来的'
							: '打叠的积极大'
		}))
	);

	const fontSelectOptions = $derived.by<ThemedSelectOption[]>(() =>
		fontOptions.map((option) => ({
			value: option.value,
			label: option.label
		}))
	);

	const roleSelectOptions: ThemedSelectOption[] = [
		{ value: 'root', label: 'root', hint: '系统最高权限' },
		{ value: '管理员', label: '管理员', hint: '管理用户与团队' },
		{ value: '用户', label: '用户', hint: '标准使用权限' }
	];

	const folderSelectOptions = $derived.by<ThemedSelectOption[]>(() => {
		const folders = folderOptionsBySpace[newDocCategoryInput as keyof typeof folderOptionsBySpace] ?? [];
		return [
			{ value: '', label: '默认分组', hint: '直接放到当前空间根分组' },
			...folders.map((folder) => ({
				value: folder,
				label: folder
			}))
		];
	});

	const categoryOptions = $derived.by(() => {
		const categories = Array.from(new Set(docs.map((doc) => doc.category).filter(Boolean)));
		return categories.length ? categories : ['团队工作区', '个人笔记'];
	});

	const folderOptionsBySpace = $derived.by(() => {
		const map = {
			'Amnesia 共享文章': [] as string[],
			'团队工作区': [] as string[],
			'个人笔记': [] as string[]
		};

		for (const doc of docs) {
			if (doc.space_type === 'global' && doc.category !== 'Amnesia 共享文章') {
				map['Amnesia 共享文章'].push(doc.category);
			}
			if (doc.space_type === 'team' && doc.category !== '团队工作区') {
				map['团队工作区'].push(doc.category);
			}
			if (doc.space_type === 'private' && doc.category !== '个人笔记') {
				map['个人笔记'].push(doc.category);
			}
		}

		return {
			'Amnesia 共享文章': Array.from(new Set(map['Amnesia 共享文章'])),
			'团队工作区': Array.from(new Set(map['团队工作区'])),
			'个人笔记': Array.from(new Set(map['个人笔记']))
		};
	});

	const globalSidebarFolders = $derived.by(() => buildSidebarFoldersForSpace('Amnesia 共享文章'));
	const teamSidebarFolders = $derived.by(() => buildSidebarFoldersForSpace('团队工作区'));
	const privateSidebarFolders = $derived.by(() => buildSidebarFoldersForSpace('个人笔记'));
	const propertiesDoc = $derived.by(() =>
		propertiesDocId == null
			? activeDoc
			: docs.find((doc) => doc.id === propertiesDocId) ?? activeDoc
	);

	function getDocSpaceTypeByCategory(category: string): DocSpaceType {
		if (category === 'Amnesia 共享文章') return 'global';
		if (category === '团队工作区') return 'team';
		return 'private';
	}

	function getFolderKey(spaceCategory: SpaceCategory, folderName: string) {
		return `${spaceCategory}:${folderName}`;
	}

	function getSpaceTitleByType(spaceType: DocSpaceType | undefined): SpaceCategory {
		if (spaceType === 'global') return 'Amnesia 共享文章';
		if (spaceType === 'team') return '团队工作区';
		return '个人笔记';
	}

	function isFolderPlaceholderDoc(doc: DocRecord) {
		return doc.title.startsWith('__folder__:');
	}

	function getFolderNameFromPlaceholder(doc: DocRecord) {
		return doc.title.replace(/^__folder__:/, '').trim();
	}

	function getSidebarOrder(doc: DocRecord) {
		const value = (doc.settings as Record<string, unknown> | undefined)?.sidebarOrder;
		return typeof value === 'number' ? value : 0;
	}

	function getDocListForSpace(spaceCategory: SpaceCategory) {
		if (spaceCategory === 'Amnesia 共享文章') {
			return docs
				.map((doc, index) => ({ doc, index }))
				.filter((item) => item.doc.space_type === 'global');
		}
		if (spaceCategory === '团队工作区') {
			return docs
				.map((doc, index) => ({ doc, index }))
				.filter(
					(item) =>
						item.doc.space_type === 'team' && String(item.doc.team_id ?? '') === currentTeamIdValue
				);
		}
		return docs
			.map((doc, index) => ({ doc, index }))
			.filter((item) => item.doc.space_type === 'private');
	}

	function buildSidebarFoldersForSpace(spaceCategory: SpaceCategory) {
		const docRefs = getDocListForSpace(spaceCategory);
		const rootDocs: SidebarDocRef[] = [];
		const folderMap = new Map<string, SidebarFolderEntry>();

		for (const docRef of docRefs) {
			const { doc } = docRef;
			if (isFolderPlaceholderDoc(doc)) {
				const folderName = getFolderNameFromPlaceholder(doc) || doc.category;
				if (!folderMap.has(folderName)) {
					folderMap.set(folderName, {
						key: getFolderKey(spaceCategory, folderName),
						name: folderName,
						docs: [],
						order: getSidebarOrder(doc),
						placeholderDocId: doc.id
					});
				}
				continue;
			}

			if (doc.category === spaceCategory) {
				rootDocs.push(docRef);
				continue;
			}

			const folderName = doc.category;
			const existing = folderMap.get(folderName) ?? {
				key: getFolderKey(spaceCategory, folderName),
				name: folderName,
				docs: [],
				order: getSidebarOrder(doc)
			};
			existing.docs.push(docRef);
			folderMap.set(folderName, existing);
		}

		for (const folder of folderMap.values()) {
			folder.docs.sort((a, b) => getSidebarOrder(a.doc) - getSidebarOrder(b.doc));
			if (!folder.order && folder.docs.length > 0) {
				folder.order = getSidebarOrder(folder.docs[0].doc);
			}
		}

		return {
			rootDocs: rootDocs.sort((a, b) => getSidebarOrder(a.doc) - getSidebarOrder(b.doc)),
			folders: Array.from(folderMap.values()).sort((a, b) =>
				a.order === b.order ? a.name.localeCompare(b.name, 'zh-CN') : a.order - b.order
			)
		};
	}

	function toggleFolderCollapsed(spaceCategory: SpaceCategory, folderName: string) {
		const key = getFolderKey(spaceCategory, folderName);
		collapsedFolderKeys = {
			...collapsedFolderKeys,
			[key]: !collapsedFolderKeys[key]
		};
	}

	function isFolderCollapsed(spaceCategory: SpaceCategory, folderName: string) {
		return !!collapsedFolderKeys[getFolderKey(spaceCategory, folderName)];
	}

	async function moveDocToFolder(docId: number, spaceCategory: SpaceCategory, folderName: string) {
		const doc = docs.find((item) => item.id === docId);
		if (!doc || isFolderPlaceholderDoc(doc)) return;
		const nextCategory = folderName.trim() || spaceCategory;
		if (doc.category === nextCategory) return;
		try {
			await updateDoc({
				id: doc.id,
				category: nextCategory
			});
			doc.category = nextCategory;
			await refreshDocs(doc.id);
			toast.success(folderName ? '文章已移动到新文件夹' : '文章已移动到根分组');
		} catch {
			toast.error('移动文章失败');
		}
	}

	function showSidebarDropLine(target: HTMLElement) {
		const rect = target.getBoundingClientRect();
		sidebarDropIndicator = {
			top: rect.top + rect.height,
			left: rect.left + 10,
			width: Math.max(60, rect.width - 20),
			visible: true
		};
	}

	function hideSidebarDropLine() {
		sidebarDropIndicator = {
			...sidebarDropIndicator,
			visible: false
		};
	}

	function getEffectiveCategory(spaceCategory: string, folderName: string) {
		const trimmedFolder = folderName.trim();
		return trimmedFolder || spaceCategory;
	}

	function getSpaceLabel(doc: DocRecord) {
		if (doc.space_type === 'global') return '全局';
		if (doc.space_type === 'team') return '团队';
		return '私有';
	}

	function stripHtmlToText(html: string) {
		if (typeof document === 'undefined') return html;
		const temp = document.createElement('div');
		temp.innerHTML = html;
		return (temp.textContent || temp.innerText || '').replace(/\s+/g, ' ').trim();
	}

	function formatSavedAt(value?: string | null) {
		if (!value) return '尚未保存';
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return '尚未保存';
		return new Intl.DateTimeFormat('zh-CN', {
			month: 'numeric',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		}).format(date);
	}

	const quickSearchResults = $derived.by(() => {
		const query = quickSearchInput.trim().toLowerCase();
		const source = docs.map((doc, index) => {
			const plainText = stripHtmlToText(doc.content || '');
			const haystack = `${doc.title} ${doc.category} ${getSpaceLabel(doc)} ${plainText}`.toLowerCase();
			const matched = !query || haystack.includes(query);
			const titleMatch = query ? doc.title.toLowerCase().includes(query) : false;
			const categoryMatch = query ? doc.category.toLowerCase().includes(query) : false;
			const snippetSource = plainText || '暂无正文内容';
			const queryIndex = query ? plainText.toLowerCase().indexOf(query) : -1;
			const snippet =
				queryIndex >= 0
					? `${queryIndex > 18 ? '…' : ''}${snippetSource.slice(Math.max(0, queryIndex - 18), queryIndex + Math.max(query.length, 26)).trim()}`
					: snippetSource.slice(0, 64).trim();

			return {
				doc,
				index,
				matched,
				score:
					(titleMatch ? 5 : 0) +
					(categoryMatch ? 2 : 0) +
					(queryIndex >= 0 ? 1 : 0) +
					(doc.updated_at ? new Date(doc.updated_at).getTime() / 10 ** 13 : 0),
				snippet: snippet || '暂无正文内容'
			};
		});

		return source
			.filter((item) => item.matched)
			.sort((a, b) => b.score - a.score)
			.slice(0, 12);
	});

	function getSpaceEmoji(spaceType: DocSpaceType | undefined) {
		if (spaceType === 'global') return '🌍';
		if (spaceType === 'team') return '👥';
		return '🔒';
	}

	function shouldEncryptDoc(doc: DocRecord) {
		return doc.space_type === 'private';
	}

	function isEncryptedPayload(value: string): value is string {
		return value.trim().startsWith('{') && value.includes('"amnesia-encrypted-doc"');
	}

	function parseEncryptedPayload(value: string): EncryptedDocPayload | null {
		if (!isEncryptedPayload(value)) return null;
		try {
			const parsed = JSON.parse(value) as EncryptedDocPayload;
			if (parsed?.type !== 'amnesia-encrypted-doc' || !parsed.iv || !parsed.cipherText) return null;
			return parsed;
		} catch {
			return null;
		}
	}

	async function buildInitialDocContent(spaceType: DocSpaceType) {
		if (spaceType !== 'private') {
			return {
				content: '<p></p>',
				isEncrypted: false,
				encryptionVersion: 1
			};
		}

		const encryptionKey = userState.session?.user?.docEncryptionKey;
		if (!encryptionKey) {
			throw new Error('私有文档需要先完成加密初始化');
		}

		const encrypted = await encryptDocumentContent('<p></p>', encryptionKey);
		return {
			content: JSON.stringify({
				type: 'amnesia-encrypted-doc',
				version: encrypted.version,
				iv: encrypted.iv,
				cipherText: encrypted.cipherText
			} satisfies EncryptedDocPayload),
			isEncrypted: true,
			encryptionVersion: encrypted.version
		};
	}

	async function serializeDocContent(doc: DocRecord) {
		if (!shouldEncryptDoc(doc)) {
			return {
				content: doc.content,
				isEncrypted: false,
				encryptionVersion: 1
			};
		}

		const encryptionKey = userState.session?.user?.docEncryptionKey;
		if (!encryptionKey) {
			throw new Error('缺少文档加密密钥，请重新登录后重试');
		}

		const encrypted = await encryptDocumentContent(doc.content, encryptionKey);
		return {
			content: JSON.stringify({
				type: 'amnesia-encrypted-doc',
				version: encrypted.version,
				iv: encrypted.iv,
				cipherText: encrypted.cipherText
			} satisfies EncryptedDocPayload),
			isEncrypted: true,
			encryptionVersion: encrypted.version
		};
	}

	async function hydrateDocFromDatabase(doc: DocRecord) {
		if (!doc.is_encrypted) return doc;
		const payload = parseEncryptedPayload(doc.content);
		if (!payload) {
			return {
				...doc,
				content: '<p>加密内容格式异常，无法读取。</p>'
			};
		}

		const encryptionKey = userState.session?.user?.docEncryptionKey;
		if (!encryptionKey) {
			return {
				...doc,
				content: '<p>缺少文档加密密钥，请重新登录后查看此私有文档。</p>'
			};
		}

		try {
			const plainText = await decryptDocumentContent(payload.cipherText, payload.iv, encryptionKey);
			return {
				...doc,
				content: plainText
			};
		} catch {
			return {
				...doc,
				content: '<p>文档解密失败，当前密钥可能与创建时不一致。</p>'
			};
		}
	}

	async function loadTeamsForCurrentUser() {
		const currentUserId = userState.session?.user?.id;
		if (!currentUserId) return;
		const memberships = await listUserTeams(String(currentUserId));
		const previousTeamId = currentTeamId;
		teams = memberships.map((item) => ({
			...item.amnesia_teams,
			memberRole: item.role
		}));
		currentTeamId =
			teams.find((team) => team.id === previousTeamId)?.id ??
			teams[0]?.id ??
			null;
		currentTeamIdValue = currentTeamId == null ? '' : String(currentTeamId);
		if (currentTeamId) {
			teamInvites = await listTeamInvites(currentTeamId);
		} else {
			teamInvites = [];
		}
	}

	async function refreshDocs(preserveActiveDocId?: number) {
		const currentUserId = userState.session?.user?.id;
		if (!currentUserId) return;
		const data = await listAccessibleDocs(currentUserId);
		docs = await Promise.all(data.map((doc) => hydrateDocFromDatabase(doc)));

		if (docs.length === 0) {
			activeDocIndex = 0;
			return;
		}

		const nextIndex =
			preserveActiveDocId != null
				? docs.findIndex((doc) => doc.id === preserveActiveDocId)
				: activeDocIndex;
		activeDocIndex = nextIndex >= 0 ? nextIndex : 0;

		const currentDoc = docs[activeDocIndex];
		if (currentDoc) {
			if (titleNode) titleNode.innerText = currentDoc.title;
			if (editor) {
				editor.commands.setContent(currentDoc.content, { emitUpdate: false });
				syncActiveFormattingState();
			}
			syncMarkdownFromHtml(currentDoc.content);
			htmlContent = currentDoc.content;
		}
	}

	async function handleCreateTeam() {
		const currentUserId = userState.session?.user?.id;
		if (!currentUserId || !newTeamName.trim() || !newTeamSlug.trim()) {
			toast.warning('请填写团队名称与 slug');
			return;
		}
		try {
			const team = await createTeam({
				name: newTeamName.trim(),
				slug: newTeamSlug.trim(),
				ownerUserId: String(currentUserId)
			});
			teams = [...teams, { ...team, memberRole: 'owner' }];
			currentTeamId = team.id;
			newTeamName = '';
			newTeamSlug = '';
			showTeamWorkspaceModal = false;
			await refreshDocs();
			toast.success('团队已创建');
		} catch (error: any) {
			toast.error(`创建团队失败: ${error?.message ?? '未知错误'}`);
		}
	}

	async function handleCreateInvite() {
		const currentUserId = userState.session?.user?.id;
		if (!currentUserId || !currentTeamId) {
			toast.warning('请先选择一个团队');
			return;
		}
		try {
			const invite = await createTeamInvite({
				teamId: currentTeamId,
				createdByUserId: currentUserId
			});
			teamInvites = [invite, ...teamInvites];
			await navigator.clipboard.writeText(invite.token);
			toast.success('邀请令牌已生成并复制');
		} catch (error: any) {
			toast.error(`生成邀请失败: ${error?.message ?? '未知错误'}`);
		}
	}

	async function handleAcceptInvite() {
		const currentUserId = userState.session?.user?.id;
		if (!currentUserId || !inviteTokenInput.trim()) {
			toast.warning('请输入邀请令牌');
			return;
		}
		try {
			const result = await acceptTeamInvite(inviteTokenInput.trim(), currentUserId);
			if (!result.success) {
				toast.error(result.message);
				return;
			}
			inviteTokenInput = '';
			await loadTeamsForCurrentUser();
			await refreshDocs();
			toast.success(result.message);
		} catch (error: any) {
			toast.error(`加入团队失败: ${error?.message ?? '未知错误'}`);
		}
	}

	async function handleCurrentTeamChange(nextTeamId: string | number | null) {
		const normalizedTeamId = nextTeamId == null || nextTeamId === '' ? null : String(nextTeamId);
		currentTeamId = normalizedTeamId;
		currentTeamIdValue = normalizedTeamId ?? '';
		if (currentTeamId) {
			teamInvites = await listTeamInvites(currentTeamId);
		} else {
			teamInvites = [];
		}
		await refreshDocs();
	}

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
		if (editor) {
			editor.setOptions({
				editorProps: {
					attributes: {
						class: 'tiptap',
						style: `--dashboard-doc-font:${docFontFamily}; --dashboard-doc-size:${docFontSize}px;`
					}
				}
			});
		}
		if (markdownEditorNode) {
			markdownEditorNode.style.setProperty('--dashboard-doc-font', docFontFamily || 'Noto Sans SC');
			markdownEditorNode.style.setProperty('--dashboard-doc-size', `${docFontSize}px`);
		}
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

	function escapeHtmlAttribute(value: string) {
		return value
			.replaceAll('&', '&amp;')
			.replaceAll('"', '&quot;')
			.replaceAll('<', '&lt;')
			.replaceAll('>', '&gt;');
	}

	function htmlToMarkdownSource(html: string) {
		if (typeof document === 'undefined') return html;
		const temp = document.createElement('div');
		temp.innerHTML = html;
		temp.querySelectorAll('[style*="color"], mark[style], span[style]').forEach((node) => {
			if (!(node instanceof HTMLElement)) return;
			node.dataset.inlineStyled = 'true';
		});
		temp.querySelectorAll('[data-html-embed-block]').forEach((node) => {
			if (!(node instanceof HTMLElement)) return;
			const raw = node.dataset.rawHtml || '';
			const wrapper = document.createElement('div');
			wrapper.dataset.inlineStyled = 'true';
			wrapper.innerHTML = raw;
			node.replaceWith(wrapper);
		});
		return turndownService.turndown(temp.innerHTML);
	}

	function formatCompactDate(value?: string) {
		if (!value) return '未记录';
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return '未记录';
		return new Intl.DateTimeFormat('zh-CN', {
			month: 'numeric',
			day: 'numeric'
		}).format(date);
	}

	function handleDashboardKeydown(event: KeyboardEvent) {
		if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
			event.preventDefault();
			if (showQuickSearchModal) {
				closeQuickSearchModal();
			} else {
				openQuickSearchModal();
			}
			return;
		}

		if (event.key === 'Escape' && showQuickSearchModal) {
			event.preventDefault();
			closeQuickSearchModal();
		}
	}

	const preserveTrailingBlankLinesKeymap = keymap.of([
		{
			key: 'Enter',
			run(view) {
				const { state } = view;
				const selection = state.selection.main;
				if (!selection.empty || selection.from !== state.doc.length) {
					return false;
				}

				const lastLine = state.doc.lineAt(selection.from);
				if (lastLine.text.trim().length > 0) {
					return false;
				}

				view.dispatch({
					changes: { from: selection.from, insert: '\n' },
					selection: { anchor: selection.from + 1 },
					scrollIntoView: true
				});
				return true;
			}
		}
	]);

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
					history(),
					lineNumbers(),
					highlightActiveLineGutter(),
					markdownLanguage(),
					EditorView.lineWrapping,
					scrollPastEnd(),
					preserveTrailingBlankLinesKeymap,
					keymap.of([
						{ key: 'Mod-z', run: undoSelection, preventDefault: true },
						{ key: 'Mod-y', run: redoSelection, preventDefault: true },
						{ key: 'Mod-Shift-z', run: redoSelection, preventDefault: true }
					]),
					EditorView.updateListener.of(async (update) => {
						if (!update.docChanged) return;
						markdownContent = update.state.doc.toString();
						markdownPreviewHtml = sanitizeHtml(await marked.parse(markdownContent));
						markdownDirty = true;
					})
				]
			})
		});
	}

	function initHtmlEditor() {
		if (!markdownEditorNode) return;
		if (markdownEditorView) {
			markdownEditorView.destroy();
			markdownEditorView = null;
		}

		markdownEditorView = new EditorView({
			parent: markdownEditorNode,
			state: EditorState.create({
				doc: htmlContent,
				extensions: [
					history(),
					lineNumbers(),
					highlightActiveLineGutter(),
					EditorView.lineWrapping,
					scrollPastEnd(),
					keymap.of([
						{ key: 'Mod-z', run: undoSelection, preventDefault: true },
						{ key: 'Mod-y', run: redoSelection, preventDefault: true },
						{ key: 'Mod-Shift-z', run: redoSelection, preventDefault: true }
					]),
					EditorView.updateListener.of((update) => {
						if (!update.docChanged) return;
						htmlContent = update.state.doc.toString();
						markdownPreviewHtml = sanitizeHtml(htmlContent);
					})
				]
			})
		});
	}

	function syncMarkdownEditorDoc() {
		if (!markdownEditorView) return;
		const source = editMode === 'html' ? htmlContent : markdownContent;
		const current = markdownEditorView.state.doc.toString();
		if (current === source) return;
		markdownEditorView.dispatch({
			changes: { from: 0, to: current.length, insert: source }
		});
	}

	async function renameActiveDoc() {
		const currentDoc = docs[activeDocIndex];
		if (!currentDoc) return;
		renameInput = currentDoc.title;
		closeDocMenu();
		showRenameModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	async function confirmRenameDoc() {
		const currentDoc = docs[activeDocIndex];
		const nextTitle = renameInput.trim();
		if (!currentDoc || !nextTitle || nextTitle === currentDoc.title) {
			showRenameModal = false;
			return;
		}
		currentDoc.title = nextTitle;
		if (titleNode) {
			titleNode.innerText = nextTitle;
		}
		showRenameModal = false;
		activeDocMenuId = null;
		triggerAutoSave();
	}

	function animateDocMenuIn() {
		if (!docMenuNode) return;
		animate(docMenuNode, {
			opacity: [0, 1],
			translateY: [-10, 0],
			scale: [0.96, 1],
			duration: 220,
			ease: 'outExpo'
		});

		const items = Array.from(docMenuNode.querySelectorAll('.doc-menu-item'));
		if (items.length > 0) {
			animate(items, {
				opacity: [0, 1],
				translateX: [-10, 0],
				delay: (_el: Element, index: number) => 40 + index * 24,
				duration: 220,
				ease: 'outExpo'
			});
		}
	}

	function closeDocMenu() {
		activeDocMenuId = null;
	}

	function closeTableContextMenu() {
		tableContextMenuOpen = false;
	}

	function closeSpaceContextMenu() {
		spaceContextMenuOpen = false;
		spaceContextMenuFolder = '';
	}

	function animateSpaceContextMenuIn() {
		if (!spaceContextMenuNode) return;
		animate(spaceContextMenuNode, {
			opacity: [0, 1],
			translateY: [-8, 0],
			scale: [0.97, 1],
			duration: 200,
			ease: 'outExpo'
		});
	}

	function openTableContextMenu(event: MouseEvent) {
		event.preventDefault();
		tableContextMenuPosition = {
			top: event.clientY + 4,
			left: Math.max(14, event.clientX - 8)
		};
		tableContextMenuOpen = true;
		requestAnimationFrame(() => {
			if (!tableContextMenuNode) return;
			animate(tableContextMenuNode, {
				opacity: [0, 1],
				translateY: [-8, 0],
				scale: [0.97, 1],
				duration: 200,
				ease: 'outExpo'
			});
		});
	}

	function openSpaceContextMenu(event: MouseEvent, category: SpaceCategory, folderName = '') {
		event.preventDefault();
		activeDocMenuId = null;
		spaceContextMenuCategory = category;
		spaceContextMenuFolder = folderName;
		spaceContextMenuPosition = {
			top: event.clientY + 4,
			left: Math.max(14, event.clientX - 8)
		};
		spaceContextMenuOpen = true;
		requestAnimationFrame(() => {
			animateSpaceContextMenuIn();
		});
	}

	function createDocInSpace(category: SpaceCategory) {
		closeSpaceContextMenu();
		openCreateDocModal(category);
		if (spaceContextMenuFolder) {
			newDocFolderInput = spaceContextMenuFolder;
		}
	}

	async function createFolderInSpace(category: SpaceCategory) {
		closeSpaceContextMenu();
		newFolderInput = '';
		pendingFolderSpace = category;
		showCreateFolderModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function openRenameFolderModal() {
		renameFolderInput = spaceContextMenuFolder;
		closeSpaceContextMenu();
		showRenameFolderModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function openDeleteFolderModal() {
		closeSpaceContextMenu();
		showDeleteFolderModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function openMoveFolderModal() {
		moveFolderTarget = '';
		closeSpaceContextMenu();
		showMoveFolderModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	async function confirmRenameFolder() {
		const sourceFolder = spaceContextMenuFolder.trim();
		const targetFolder = renameFolderInput.trim();
		if (!sourceFolder || !targetFolder || sourceFolder === targetFolder) {
			showRenameFolderModal = false;
			return;
		}
		try {
			const targetDocs = getDocListForSpace(spaceContextMenuCategory)
				.map((item) => item.doc)
				.filter((doc) => doc.category === sourceFolder);
			for (const doc of targetDocs) {
				await updateDoc({
					id: doc.id,
					category: targetFolder,
					title: isFolderPlaceholderDoc(doc) ? `__folder__:${targetFolder}` : undefined
				});
			}
			showRenameFolderModal = false;
			await refreshDocs();
			toast.success('文件夹已重命名');
		} catch {
			toast.error('重命名文件夹失败');
		}
	}

	async function confirmDeleteFolder() {
		const folderName = spaceContextMenuFolder.trim();
		if (!folderName) {
			showDeleteFolderModal = false;
			return;
		}
		try {
			const targetDocs = getDocListForSpace(spaceContextMenuCategory)
				.map((item) => item.doc)
				.filter((doc) => doc.category === folderName);
			for (const doc of targetDocs) {
				if (isFolderPlaceholderDoc(doc)) {
					const { error } = await supabase.from('amnesia_docs').delete().eq('id', doc.id);
					if (error) throw error;
					continue;
				}
				await updateDoc({
					id: doc.id,
					category: spaceContextMenuCategory
				});
			}
			showDeleteFolderModal = false;
			await refreshDocs();
			toast.success('文件夹已删除，文章已移回根分组');
		} catch {
			toast.error('删除文件夹失败');
		}
	}

	async function confirmMoveFolderDocs() {
		const sourceFolder = spaceContextMenuFolder.trim();
		const targetFolder = moveFolderTarget.trim();
		if (!sourceFolder || !targetFolder || sourceFolder === targetFolder) {
			showMoveFolderModal = false;
			return;
		}
		try {
			const targetDocs = getDocListForSpace(spaceContextMenuCategory)
				.map((item) => item.doc)
				.filter((doc) => doc.category === sourceFolder && !isFolderPlaceholderDoc(doc));
			for (const doc of targetDocs) {
				await updateDoc({
					id: doc.id,
					category: targetFolder
				});
			}
			showMoveFolderModal = false;
			await refreshDocs();
			toast.success('文件夹内文章已批量迁移');
		} catch {
			toast.error('批量迁移失败');
		}
	}

	function openDocMenuFromEvent(event: MouseEvent, id: number) {
		event.preventDefault();
		event.stopPropagation();
		closeSpaceContextMenu();
		const target = event.currentTarget as HTMLElement | null;
		if (!target) {
			openDocMenu(id);
			return;
		}
		const rect = target.getBoundingClientRect();
		docMenuPosition = {
			top: rect.bottom + 6,
			left: Math.max(12, rect.right - 196)
		};
		activeDocMenuId = id;
		requestAnimationFrame(() => {
			animateDocMenuIn();
		});
	}

	function openDocMenu(id: number) {
		closeSpaceContextMenu();
		const target = document.getElementById(`doc-menu-trigger-${id}`);
		if (!target) {
			activeDocMenuId = activeDocMenuId === id ? null : id;
			return;
		}
		const rect = target.getBoundingClientRect();
		docMenuPosition = {
			top: rect.bottom + 6,
			left: Math.max(12, rect.right - 196)
		};
		activeDocMenuId = activeDocMenuId === id ? null : id;
		animate(target, {
			scale: [1, 1.12, 1],
			rotate: [0, -8, 0],
			duration: 320,
			ease: 'outElastic(1, 0.7)'
		});
		requestAnimationFrame(() => {
			animateDocMenuIn();
		});
	}

	async function duplicateActiveDoc() {
		const currentDoc = docs[activeDocIndex];
		if (!currentDoc) return;
		closeDocMenu();
		try {
			const serialized = await serializeDocContent(currentDoc);
			const data = await createSpaceDoc({
				title: `${currentDoc.title} 副本`,
				emoji: currentDoc.emoji,
				category: currentDoc.category,
				content: serialized.content,
				author: currentDoc.author || userState.session?.user?.username || '未知',
				ownerUserId: currentDoc.owner_user_id ?? userState.session?.user?.id ?? null,
				teamId: currentDoc.team_id ?? null,
				spaceType: currentDoc.space_type ?? getDocSpaceTypeByCategory(currentDoc.category),
				isEncrypted: serialized.isEncrypted,
				encryptionVersion: serialized.encryptionVersion,
				settings: currentDoc.settings ?? {}
			});
			docs = [...docs, await hydrateDocFromDatabase(data)];
			activeDocIndex = docs.findIndex((doc) => doc.id === data.id);
			await tick();
			handleDocClick(activeDocIndex, data.title);
			activeDocMenuId = null;
			toast.success('已创建文档副本');
		} catch {
			toast.error('创建副本失败');
		}
	}

	async function createNewDoc(category: string) {
		const currentUser = userState.session?.user;
		if (!currentUser?.id) {
			toast.error('缺少用户身份，请重新登录');
			return;
		}
		try {
			const spaceType = getDocSpaceTypeByCategory(category);
			const effectiveCategory = getEffectiveCategory(category, newDocFolderInput);
			if (spaceType === 'team' && !currentTeamId) {
				toast.warning('请先创建或选择一个团队');
				return;
			}
			const initialContent = await buildInitialDocContent(spaceType);
			const data = await createSpaceDoc({
				title: newDocTitleInput.trim() || '未命名文章',
				emoji: '📝',
				category: effectiveCategory,
				content: initialContent.content,
				author: currentUser.username,
				ownerUserId: currentUser.id,
				teamId: spaceType === 'team' ? currentTeamId : null,
				spaceType,
				isEncrypted: initialContent.isEncrypted,
				encryptionVersion: initialContent.encryptionVersion,
				settings: {}
			});
			docs = [...docs, await hydrateDocFromDatabase(data)];
			showCreateDocModal = false;
			newDocTitleInput = '';
			newDocFolderInput = '';
			await refreshDocs(data.id);
			await tick();
			toast.success('新文章已创建');
		} catch {
			toast.error('创建文章失败');
		}
	}

	function openCreateDocModal(category?: string) {
		closeSpaceContextMenu();
		mobileSidebarOpen = false;
		newDocTitleInput = '';
		newDocCategoryInput = category || categoryOptions[0] || '个人笔记';
		newDocFolderInput = spaceContextMenuFolder || '';
		showCreateDocModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function openCreateFolderModal() {
		closeSpaceContextMenu();
		mobileSidebarOpen = false;
		newFolderInput = '';
		pendingFolderSpace = (newDocCategoryInput as SpaceCategory) || '个人笔记';
		showCreateFolderModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function openEmojiPickerModal() {
		mobileToolbarExpanded = false;
		showEmojiPickerModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function openGlobalSettingsModal() {
		mobileToolbarExpanded = false;
		mobileSidebarOpen = false;
		showGlobalSettingsModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function openPageSettingsModal() {
		mobileToolbarExpanded = false;
		showPageSettingsModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function openTeamWorkspaceModal() {
		mobileSidebarOpen = false;
		showTeamWorkspaceModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function openPropertiesModal() {
		mobileToolbarExpanded = false;
		showPropertiesModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function openUserManagementModal() {
		mobileSidebarOpen = false;
		showUserManagement = true;
		requestAnimationFrame(() => animateModalEnter());
		refreshUsers();
	}

	async function confirmCreateFolder() {
		const name = newFolderInput.trim();
		if (!name) return;
		const currentUser = userState.session?.user;
		if (!currentUser?.id) {
			toast.error('缺少用户身份，请重新登录');
			return;
		}

		const category = pendingFolderSpace || '个人笔记';
		const spaceType = getDocSpaceTypeByCategory(category);
		if (spaceType === 'team' && !currentTeamId) {
			toast.warning('请先创建或选择一个团队');
			return;
		}

		try {
			const initialContent = await buildInitialDocContent(spaceType);
			const data = await createSpaceDoc({
				title: `__folder__:${name}`,
				emoji: '📁',
				category: name,
				content: initialContent.content,
				author: currentUser.username,
				ownerUserId: currentUser.id,
				teamId: spaceType === 'team' ? currentTeamId : null,
				spaceType,
				isEncrypted: initialContent.isEncrypted,
				encryptionVersion: initialContent.encryptionVersion,
				settings: {
					isFolder: true,
					parentSpace: category
				}
			});
			docs = [...docs, await hydrateDocFromDatabase(data)];
			newDocFolderInput = name;
			showCreateFolderModal = false;
			newFolderInput = '';
			await refreshDocs(data.id);
			toast.success('文件夹已创建');
		} catch {
			toast.error('创建文件夹失败');
		}
	}

	async function confirmEncryptionSetup() {
		const currentUser = userState.session?.user;
		if (!currentUser?.id || !encryptionPasswordInput.trim()) return;
		const verifiedUser = await loginWithPassword({
			username: currentUser.username,
			password: encryptionPasswordInput.trim()
		});
		if (!verifiedUser || verifiedUser.id !== currentUser.id) {
			toast.error('密码不正确，无法初始化文档加密');
			return;
		}

		const keyHint = await deriveDocEncryptionKey(encryptionPasswordInput.trim());
		await setUserEncryptionReady(currentUser.id, keyHint);
		userState.setSession({
			user: {
				...currentUser,
				encryptionReady: true,
				encryptionNoticeAccepted: true,
				docEncryptionKey: keyHint
			}
		});
		encryptionPasswordInput = '';
		showEncryptionSetupModal = false;
		toast.success('文档加密密钥已初始化');
	}

	async function deleteActiveDoc() {
		const currentDoc = docs[activeDocIndex];
		if (!currentDoc) return;
		closeDocMenu();
		showDeleteDocModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	async function confirmDeleteActiveDoc() {
		const currentDoc = docs[activeDocIndex];
		if (!currentDoc) return;

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
		showDeleteDocModal = false;
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
		linkUrlInput = editor?.getAttributes('link')?.href ?? '';
		linkTextInput = editor?.state.doc.textBetween(editor.state.selection.from, editor.state.selection.to, ' ') ?? '';
		showLinkModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function insertImage() {
		imageUrlInput = '';
		showImageModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function insertSafeHtml() {
		htmlEmbedInput = '';
		showHtmlModal = true;
		requestAnimationFrame(() => animateModalEnter());
	}

	function confirmInsertLink() {
		if (!editor || !linkUrlInput.trim()) return;
		const chain = editor.chain().focus();
		if (editor.state.selection.empty && linkTextInput.trim()) {
			chain.insertContent(linkTextInput.trim());
		}
		chain.extendMarkRange('link').setLink({ href: linkUrlInput.trim(), target: '_blank' }).run();
		showLinkModal = false;
	}

	function confirmInsertImageUrl() {
		if (!editor || !imageUrlInput.trim()) return;
		editor.chain().focus().setImage({ src: imageUrlInput.trim(), alt: 'image' }).run();
		showImageModal = false;
	}

	function confirmInsertSafeHtml() {
		if (!editor || !htmlEmbedInput.trim()) return;
		const sanitizedHtml = sanitizeHtml(htmlEmbedInput.trim());
		if (!sanitizedHtml.trim()) {
			toast.warning('可插入的 HTML 为空，已被安全过滤。');
			return;
		}
		editor
			.chain()
			.focus()
			.insertContent({
				type: 'rawHtmlEmbed',
				attrs: {
					html: sanitizedHtml
				}
			})
			.run();
		syncActiveFormattingState();
		showHtmlModal = false;
	}

	function toggleTaskListBlock() {
		editor?.chain().focus().toggleTaskList().run();
	}

	function insertBasicTable() {
		editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
	}

	function addTableRowAfter() {
		editor?.chain().focus().addRowAfter().run();
	}

	function addTableColumnAfter() {
		editor?.chain().focus().addColumnAfter().run();
	}

	async function handleImageFileUpload(file: File) {
		if (!file.type.startsWith('image/')) {
			toast.error('只能上传图片文件');
			return;
		}
		const reader = new FileReader();
		reader.onload = () => {
			const src = reader.result;
			if (typeof src === 'string' && editor) {
				editor.chain().focus().setImage({ src, alt: file.name }).run();
				showImageModal = false;
			}
		};
		reader.readAsDataURL(file);
	}

	function applyTextColor(color: string) {
		if (lockPage) return;
		selectedTextColor = color;
		restoreEditorSelection();
		editor?.chain().setColor(color).run();
		syncActiveFormattingState();
	}

	function applyHighlightColor(color: string) {
		if (lockPage) return;
		selectedHighlightColor = color;
		restoreEditorSelection();
		editor?.chain().setHighlight({ color }).run();
		syncActiveFormattingState();
	}

	function resetTextColor() {
		if (lockPage) return;
		restoreEditorSelection();
		editor?.chain().unsetColor().run();
		activeTextColorState = '';
		syncActiveFormattingState();
	}

	function resetHighlightColor() {
		if (lockPage) return;
		restoreEditorSelection();
		editor?.chain().unsetHighlight().run();
		activeHighlightColorState = '';
		syncActiveFormattingState();
	}

	function toggleTextColorPicker() {
		if (activeTextColorState) {
			resetTextColor();
			return;
		}
		applyTextColor(selectedTextColor || '#111827');
	}

	function toggleHighlightColorPicker() {
		if (activeHighlightColorState) {
			resetHighlightColor();
			return;
		}
		applyHighlightColor(selectedHighlightColor || '#fef08a');
	}

	function syncActiveFormattingState() {
		const activeTextColor = getActiveTextColor();
		const activeHighlightColor = getActiveHighlightColor();
		activeTextColorState = activeTextColor || '';
		activeHighlightColorState = activeHighlightColor || '';
		if (activeTextColor) {
			selectedTextColor = activeTextColor;
		}
		if (activeHighlightColor) {
			selectedHighlightColor = activeHighlightColor;
		}
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
	} else if (editMode === 'html') {
		htmlContent = markdownPreviewHtml;
		syncMarkdownEditorDoc();
	} else {
		syncMarkdownEditorDoc();
	}
}

async function copyPageContent() {
	const currentDoc = docs[activeDocIndex];
	if (!currentDoc) return;
	const textToCopy =
		editMode === 'html'
			? htmlContent || currentDoc.content
			: editMode === 'markdown'
				? markdownContent || currentDoc.content
				: currentDoc.content;
	await navigator.clipboard.writeText(textToCopy);
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
			id: 'task',
			label: '待办列表',
			hint: '插入可勾选的 to-do',
			run: () => editor?.chain().focus().toggleTaskList().run()
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
		},
		{
			id: 'table',
			label: '表格',
			hint: '插入 3x3 表格',
			run: () => editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
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
	let globalArticlesOpen = $state(true);
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
		pendingDeleteUsername = username;
		showDeleteUserModal = true;
	}

	async function confirmDeleteUser() {
		if (!pendingDeleteUsername) return;
		const res = await deleteUser(pendingDeleteUsername);
		if (res.success) {
			toast.success(res.message);
			await refreshUsers();
		} else {
			toast.error(res.message);
		}
		pendingDeleteUsername = '';
		showDeleteUserModal = false;
	}

	// 触发云端自动防抖同步
	function triggerAutoSave() {
		if (editMode === 'markdown') {
			return;
		}
		syncStatus = 'syncing';
		clearTimeout(saveTimeout);
		saveTimeout = setTimeout(async () => {
			const currentDoc = docs[activeDocIndex];
			if (!currentDoc) return;

			try {
				const serialized = await serializeDocContent(currentDoc);
				const updatedDoc = await updateDoc({
					id: currentDoc.id,
					title: currentDoc.title,
					content: serialized.content,
					emoji: currentDoc.emoji,
					category: currentDoc.category,
					settings: currentDoc.settings,
					isEncrypted: serialized.isEncrypted,
					encryptionVersion: serialized.encryptionVersion
				});
				docs[activeDocIndex] = {
					...docs[activeDocIndex],
					updated_at: updatedDoc.updated_at ?? new Date().toISOString()
				};
				lastSavedAt = docs[activeDocIndex]?.updated_at ?? new Date().toISOString();
			} catch (error) {
				console.error('Failed to sync doc to Supabase:', error);
				syncStatus = 'idle';
				toast.error('数据同步失败，请检查网络');
				return;
			}

			syncStatus = 'saved';
		}, 1000);
	}

	function syncMarkdownFromHtml(html: string) {
		htmlContent = html;
		markdownContent = htmlToMarkdownSource(html);
		markdownPreviewHtml = html;
		markdownDirty = false;
	}

	async function applyHtmlToEditor(html: string) {
		if (!editor || !docs[activeDocIndex]) return;
		const sanitizedHtml = sanitizeHtml(html);
		editor.commands.setContent(sanitizedHtml, { emitUpdate: false });
		docs[activeDocIndex].content = editor.getHTML();
		htmlContent = docs[activeDocIndex].content;
		markdownPreviewHtml = docs[activeDocIndex].content;
		syncMarkdownFromHtml(docs[activeDocIndex].content);
		syncActiveFormattingState();
		triggerAutoSave();
	}

	async function applyMarkdownToEditor(markdown: string) {
		if (!editor || !docs[activeDocIndex]) return;

		const parsed = await marked.parse(markdown);
		const normalizedHtml = sanitizeHtml(parsed).replace(
			/<div([^>]*?)data-inline-styled="true"([^>]*)>([\s\S]*?)<\/div>/gi,
			(_match, beforeAttrs, afterAttrs, innerHtml) =>
				`<div data-html-embed-block="true" data-raw-html="${escapeHtmlAttribute(innerHtml)}"${beforeAttrs}${afterAttrs}></div>`
		);
		editor.commands.setContent(normalizedHtml, { emitUpdate: false });
		docs[activeDocIndex].content = editor.getHTML();
		htmlContent = docs[activeDocIndex].content;
		markdownPreviewHtml = docs[activeDocIndex].content;
		syncMarkdownFromHtml(docs[activeDocIndex].content);
		syncActiveFormattingState();
		markdownDirty = false;
		triggerAutoSave();
	}

	async function handleMarkdownInput(e: Event) {
		const target = e.currentTarget as HTMLTextAreaElement;
		markdownContent = target.value;
		markdownPreviewHtml = sanitizeHtml(await marked.parse(markdownContent));
		markdownDirty = true;
	}

	async function saveMarkdownChanges() {
		if (editMode !== 'markdown') return;
		await applyMarkdownToEditor(markdownContent);
		toast.success('Markdown 已手动保存');
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
		const hit = document.elementFromPoint(clientX, clientY);
		const block = getTopLevelBlock(hit);
		if (!block || block.closest('.editor-toolbar-overlay, .block-handle, .command-menu')) {
			hideBlockHandle();
			return;
		}

		const shellRect = editorShellNode.getBoundingClientRect();
		const blockRect = block.getBoundingClientRect();
		blockHandleTop = blockRect.top - shellRect.top + blockRect.height / 2;
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

	function reorderActiveBlockToPoint(clientY: number) {
		if (!editor || !editorNode || !activeBlockElement) return;
		const block = activeBlockElement;
		const blocks = Array.from(editorNode.children).filter(
			(node): node is HTMLElement => node instanceof HTMLElement
		);
		const fromPos = editor.view.posAtDOM(block, 0);
		const sourceNode = editor.state.doc.nodeAt(fromPos);
		if (!sourceNode) return;

		let targetElement: HTMLElement | null = null;
		for (const candidate of blocks) {
			if (candidate === block) continue;
			const rect = candidate.getBoundingClientRect();
			if (clientY < rect.top + rect.height / 2) {
				targetElement = candidate;
				break;
			}
		}

		let insertPos = editor.state.doc.content.size;
		if (targetElement) {
			insertPos = editor.view.posAtDOM(targetElement, 0);
		}

		const sourceSlice = sourceNode.toJSON();
		editor
			.chain()
			.focus()
			.deleteRange({ from: fromPos, to: fromPos + sourceNode.nodeSize })
			.insertContentAt(insertPos > fromPos ? insertPos - sourceNode.nodeSize : insertPos, sourceSlice)
			.run();
	}

	function handleBlockDragStart(event: DragEvent) {
		if (!activeBlockElement) return;
		blockHandleLocked = true;
		event.dataTransfer?.setData('text/plain', 'amnesia-block');
		event.dataTransfer?.setDragImage(activeBlockElement, 12, 12);
	}

	function handleBlockDragOver(event: DragEvent) {
		if (editMode !== 'rich' || !editorNode) return;
		event.preventDefault();
		const blocks = Array.from(editorNode.children).filter(
			(node): node is HTMLElement => node instanceof HTMLElement
		);
		const hovered = blocks.find((candidate) => {
			const rect = candidate.getBoundingClientRect();
			return event.clientY >= rect.top && event.clientY <= rect.bottom;
		});
		if (!hovered) return;
		const rect = hovered.getBoundingClientRect();
		blockDragIndicator = {
			top: rect.top - editorNode.getBoundingClientRect().top + (event.clientY > rect.top + rect.height / 2 ? rect.height : 0),
			visible: true
		};
	}

	function handleBlockDrop(event: DragEvent) {
		if (editMode !== 'rich') return;
		event.preventDefault();
		if (event.dataTransfer?.files?.length) {
			const file = event.dataTransfer.files[0];
			if (file) {
				handleImageFileUpload(file);
			}
			blockDragIndicator = { top: 0, visible: false };
			blockHandleLocked = false;
			return;
		}
		reorderActiveBlockToPoint(event.clientY);
		blockDragIndicator = { top: 0, visible: false };
		blockHandleLocked = false;
	}

	function handleBlockDragEnd() {
		blockDragIndicator = { top: 0, visible: false };
		blockHandleLocked = false;
	}

	async function toggleEditMode(mode: 'rich' | 'html' | 'markdown') {
		if (mode === editMode) return;

		if (mode === 'markdown') {
			if (editor) {
				syncMarkdownFromHtml(docs[activeDocIndex]?.content || editor.getHTML());
			}
			pendingEditMode = 'markdown';
			showMarkdownWarningModal = true;
			requestAnimationFrame(() => animateModalEnter());
			return;
		}

		if (editMode === 'markdown' && markdownDirty) {
			toast.warning('Markdown 有未保存改动，请先手动保存。');
			return;
		}

		if (mode === 'html') {
			htmlContent = docs[activeDocIndex]?.content || editor?.getHTML() || '';
			markdownPreviewHtml = sanitizeHtml(htmlContent);
			editMode = 'html';
			await tick();
			initHtmlEditor();
			hideCommandMenu();
			hideBlockHandle();
			requestAnimationFrame(() => {
				animateCurrentDocView();
			});
			return;
		}

		if (editMode === 'html') {
			await applyHtmlToEditor(htmlContent);
		}

		editMode = 'rich';
		hideCommandMenu();
		hideBlockHandle();
		await tick();
		requestAnimationFrame(() => {
			animateCurrentDocView();
		});
	}

	async function confirmMarkdownModeSwitch() {
		showMarkdownWarningModal = false;
		if (pendingEditMode !== 'markdown') return;
		editMode = 'markdown';
		pendingEditMode = null;
		await tick();
		initMarkdownEditor();
		markdownDirty = false;
		toast.info('已进入 Markdown 模式，修改后要手动保存。');
		hideCommandMenu();
		hideBlockHandle();
		requestAnimationFrame(() => {
			animateCurrentDocView();
		});
	}

	// 切换文档
	function handleDocClick(index: number, docTitle: string) {
		if (activeDocIndex === index) return;
		closeSpaceContextMenu();
		mobileSidebarOpen = false;
		activeDocIndex = index;
		closeQuickSearchModal();
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
			htmlContent = currentDoc.content;
			requestAnimationFrame(() => {
				animateCurrentDocView();
			});
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
		syncViewportState();
		window.addEventListener('resize', syncViewportState);
		window.addEventListener('keydown', handleDashboardKeydown);
		if (!userState.session) {
			goto('/login');
			return;
		}
		if (!userState.session.user.encryptionReady) {
			showEncryptionSetupModal = true;
			requestAnimationFrame(() => animateModalEnter());
		}

		// 1. 从 Supabase 拉取真正的文档
		const currentUserId = userState.session?.user?.id;
		if (!currentUserId) {
			toast.error('缺少用户身份，请重新登录');
			goto('/login');
			return;
		}
		try {
			await loadTeamsForCurrentUser();
			await refreshDocs();
			lastSavedAt = docs[activeDocIndex]?.updated_at ?? null;
			await tick();
		} catch (error) {
			toast.error('拉取云端文档失败，请检查网络');
			console.error(error);
		}

		// 2. 初始化 Tiptap 编辑器
		const initialDoc = docs[activeDocIndex];
		if (initialDoc && editorNode) {
			if (titleNode) {
				titleNode.innerText = initialDoc.title;
			}
			syncMarkdownFromHtml(initialDoc.content);
			htmlContent = initialDoc.content;

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
					Image,
					TaskList,
					TaskItem.configure({ nested: true }),
					Table.configure({
						resizable: true,
						renderWrapper: true
					}),
					TableRow,
					TableHeader,
					TableCell,
					Mention.configure({
						HTMLAttributes: {
							class: 'doc-mention'
						},
						renderText: ({ node }) => `@${node.attrs.label ?? node.attrs.id}`,
						renderHTML: ({ node }) => [
							'a',
							{
								href: buildMentionHref(String(node.attrs.id ?? '')),
								'data-doc-id': String(node.attrs.id ?? ''),
								'data-label': String(node.attrs.label ?? ''),
								'data-type': 'mention'
							},
							`@${node.attrs.label ?? node.attrs.id}`
						],
						suggestion: createMentionSuggestionConfig() as any
					})
				],
				content: initialDoc.content,
				editorProps: {
					attributes: {
						class: 'tiptap',
						style: `font-size:${docFontSize}px; --dashboard-doc-font:${docFontFamily};`
					},
					handleDOMEvents: {
						contextmenu: (_view, event) => {
							const target = event.target;
							if (!(target instanceof HTMLElement)) return false;
							const insideTable = target.closest('.tableWrapper, table, td, th');
							if (!(insideTable instanceof HTMLElement)) {
								closeTableContextMenu();
								return false;
							}
							openTableContextMenu(event as MouseEvent);
							return true;
						}
					},
					handleClick(view, _pos, event) {
						const target = event.target;
						if (!(target instanceof HTMLElement)) return false;
						const mentionNode = target.closest('[data-type="mention"][data-doc-id]');
						if (!(mentionNode instanceof HTMLElement)) return false;
						const docId = mentionNode.dataset.docId;
						if (!docId) return false;
						event.preventDefault();
						selectMentionDocById(docId);
						return true;
					}
				},
				onUpdate: ({ editor }) => {
					if (docs[activeDocIndex]) {
						docs[activeDocIndex].content = editor.getHTML();
						htmlContent = docs[activeDocIndex].content;
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
				ease: 'outExpo',
				onComplete: () => {
					sidebarNode?.style.removeProperty('transform');
				}
			});
		}

		if (mainContentNode) {
			animate(mainContentNode, {
				opacity: [0, 1],
				translateY: [20, 0],
				duration: 1000,
				delay: 200,
				ease: 'outExpo',
				onComplete: () => {
					mainContentNode?.style.removeProperty('transform');
					if (mainContentNode) mainContentNode.style.opacity = '1';
				}
			});
		}

		if (dashboardShellNode) {
			dashboardMotionCleanup = wireDashboardMotion(dashboardShellNode);
		}

		toast.success('工作台已加载完毕');
		await refreshUsers();
	});

	onDestroy(() => {
		if (typeof window !== 'undefined') {
			window.removeEventListener('keydown', handleDashboardKeydown);
			window.removeEventListener('resize', syncViewportState);
		}
		dashboardMotionCleanup?.();
		dashboardMotionCleanup = null;
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

<div bind:this={dashboardShellNode} class="dashboard-shell flex h-[100dvh] max-h-[100dvh] w-full overflow-hidden text-sm">

	{#if isMobileViewport && mobileSidebarOpen}
		<button
			type="button"
			class="dashboard-mobile-sidebar-backdrop"
			aria-label="关闭侧边栏"
			onclick={() => (mobileSidebarOpen = false)}
		></button>
	{/if}

	<!-- =================== 左侧 Notion 侧边栏 =================== -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		bind:this={sidebarNode}
		class="dashboard-sidebar w-60 h-full min-h-0 flex flex-col justify-between shrink-0 select-none z-10 overflow-visible {isMobileViewport ? 'dashboard-sidebar-mobile' : ''} {isMobileViewport && mobileSidebarOpen ? 'is-open' : ''}"
	>
		<div class="flex-1 min-h-0 flex flex-col overflow-y-auto overflow-x-visible p-2.5 space-y-3">

			<!-- 用户资料块 -->
			<button
				type="button"
				class="dashboard-list-row dashboard-sidebar-card w-full flex items-center gap-2 p-1.5 rounded-xl cursor-pointer transition-all duration-200 text-left"
				onclick={openUserProfileModal}
			>
				<div class="dashboard-avatar w-7 h-7 ml-1 rounded-lg flex items-center justify-center text-xs font-bold font-mono overflow-hidden">
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
					<!-- <p class="dashboard-muted text-[10px] mt-0.5 truncate">
						{userState.session?.user?.role || '用户'}
					</p> -->
				</div>
			</button>

			<!-- 快速导航区 -->
			<div class="space-y-0.5">
				<button
					type="button"
					onclick={openQuickSearchModal}
					class="dashboard-list-row dashboard-sidebar-entry dashboard-muted w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-xs font-medium cursor-pointer"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="opacity-60 ml-1"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0-14 0m18 11l-6-6"/></svg>
					快速检索
				</button>

				{#if userState.session?.user?.role === 'root' || userState.session?.user?.role === '管理员'}
					<button
						type="button"
						onclick={openUserManagementModal}
						class="dashboard-list-row dashboard-sidebar-entry dashboard-muted w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-xs font-medium cursor-pointer"
					>
						<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="opacity-60 ml-1"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2m8-10a4 4 0 1 0 0-8a4 4 0 0 0 0 8m14 10v-2a4 4 0 0 0-3-3.87m-4-12a4 4 0 0 1 0 7.75"/></svg>
						用户管理
					</button>
				{/if}
			</div>

			{#if sidebarDropIndicator.visible}
				<div
					class="sidebar-drop-indicator"
					style={`top:${sidebarDropIndicator.top}px; left:${sidebarDropIndicator.left}px; width:${sidebarDropIndicator.width}px;`}
				></div>
			{/if}

			<!-- 文档大分类 - 全局文章 -->
			<div class="space-y-1">
				<div class="dashboard-folder-header">
					<button
						type="button"
						class="dashboard-muted dashboard-sidebar-section flex-1 flex items-center justify-between px-2 py-0.5 text-[10px] font-bold tracking-wider cursor-pointer"
						oncontextmenu={(event) => openSpaceContextMenu(event, 'Amnesia 共享文章')}
						onclick={() => {
							globalArticlesOpen = !globalArticlesOpen;
							requestAnimationFrame(() => animateSectionToggle('global', globalArticlesOpen));
						}}
					>
						<span>🌍 全局文章</span>
						<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" class="transition-transform duration-200 {globalArticlesOpen ? 'rotate-90' : ''}"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m9 18l6-6l-6-6"/></svg>
					</button>
					<button type="button" class="dashboard-folder-add-btn" title="创建全局文章" onclick={() => openCreateDocModal('Amnesia 共享文章')}>+</button>
				</div>

				{#if globalArticlesOpen}
					<div
						class="dashboard-collapsible-panel dashboard-global-panel space-y-0.5 pl-1"
						ondragover={(event) => event.preventDefault()}
						ondrop={async (event) => {
							event.preventDefault();
							if (draggingDocId) {
								await moveDocToFolder(draggingDocId, 'Amnesia 共享文章', '');
								draggingDocId = null;
							}
						}}
					>
						{#each globalSidebarFolders.rootDocs as item}
							<div
								class="dashboard-doc-row dashboard-sidebar-doc relative flex items-center gap-1 pr-1 rounded-lg transition-all duration-200 {activeDocIndex === item.index ? 'is-active font-bold' : ''}"
								oncontextmenu={(event) => openDocMenuFromEvent(event, item.doc.id)}
								draggable={!isFolderPlaceholderDoc(item.doc)}
								ondragstart={() => (draggingDocId = item.doc.id)}
								ondragend={() => (draggingDocId = null)}
								ondragover={(event) => {
									event.preventDefault();
									showSidebarDropLine(event.currentTarget as HTMLElement);
								}}
								ondrop={hideSidebarDropLine}
							>
								<button
									type="button"
									class="flex-1 flex items-center gap-2 px-2 py-1.5 text-left text-[12px] font-semibold cursor-pointer truncate"
									onclick={() => handleDocClick(item.index, item.doc.title)}
								>
									<span>{item.doc.emoji}</span>
									<span class="truncate">{item.doc.title}</span>
									<span class="dashboard-space-pill">{getSpaceLabel(item.doc)}</span>
								</button>
								<button id={`doc-menu-trigger-${item.doc.id}`} type="button" class="dashboard-icon-btn" onclick={() => openDocMenu(item.doc.id)}>
								<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24">
									<path d="M0 0h24v24H0z" fill="none" />
									<path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0" />
								</svg>
								</button>
							</div>
						{/each}
						{#each globalSidebarFolders.folders as folder}
							<div class="dashboard-folder-group">
								<div
									class="dashboard-folder-row"
									oncontextmenu={(event) => openSpaceContextMenu(event, 'Amnesia 共享文章', folder.name)}
									ondragover={(event) => event.preventDefault()}
									ondrop={async (event) => {
										event.preventDefault();
										if (draggingDocId) {
											await moveDocToFolder(draggingDocId, 'Amnesia 共享文章', folder.name);
											draggingDocId = null;
										}
									}}
								>
									<button type="button" class="dashboard-folder-label" onclick={() => toggleFolderCollapsed('Amnesia 共享文章', folder.name)}>
										<span class:folder-collapsed={isFolderCollapsed('Amnesia 共享文章', folder.name)}>▸</span>
										<span>📁</span>
										<span class="truncate">{folder.name}</span>
									</button>
								</div>
								{#if !isFolderCollapsed('Amnesia 共享文章', folder.name)}
								<div class="dashboard-folder-children">
									{#each folder.docs as item}
										<div
											class="dashboard-doc-row dashboard-sidebar-doc relative flex items-center gap-1 pr-1 rounded-lg transition-all duration-200 {activeDocIndex === item.index ? 'is-active font-bold' : ''}"
											oncontextmenu={(event) => openDocMenuFromEvent(event, item.doc.id)}
											draggable={!isFolderPlaceholderDoc(item.doc)}
											ondragstart={() => (draggingDocId = item.doc.id)}
											ondragend={() => (draggingDocId = null)}
											ondragover={(event) => {
												event.preventDefault();
												showSidebarDropLine(event.currentTarget as HTMLElement);
											}}
											ondrop={hideSidebarDropLine}
										>
											<button
												type="button"
												class="flex-1 flex items-center gap-2 px-2 py-1.5 text-left text-[12px] font-semibold cursor-pointer truncate"
												onclick={() => handleDocClick(item.index, item.doc.title)}
											>
												<span>{item.doc.emoji}</span>
												<span class="truncate">{item.doc.title}</span>
												<span class="dashboard-space-pill">{getSpaceLabel(item.doc)}</span>
											</button>
											<button id={`doc-menu-trigger-${item.doc.id}`} type="button" class="dashboard-icon-btn" onclick={() => openDocMenu(item.doc.id)}>
												<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24">
													<path d="M0 0h24v24H0z" fill="none" />
													<path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0" />
												</svg>
											</button>
										</div>
									{/each}
								</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- 文档大分类 - 团队工作区 -->
			<div class="space-y-1">
				<div class="dashboard-folder-header">
					<button
						type="button"
						class="dashboard-muted dashboard-sidebar-section flex-1 flex items-center justify-between px-2 py-0.5 text-[10px] font-bold tracking-wider cursor-pointer"
						oncontextmenu={(event) => openSpaceContextMenu(event, '团队工作区')}
						onclick={() => {
							teamWorkspaceOpen = !teamWorkspaceOpen;
							requestAnimationFrame(() => animateSectionToggle('team', teamWorkspaceOpen));
						}}
					>
						<span>👥 团队工作区</span>
						<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" class="transition-transform duration-200 {teamWorkspaceOpen ? 'rotate-90' : ''}"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m9 18l6-6l-6-6"/></svg>
					</button>
					<div class="flex items-center gap-1">
						<button type="button" class="dashboard-folder-add-btn" title="管理团队空间" onclick={openTeamWorkspaceModal}>⚙</button>
						<button type="button" class="dashboard-folder-add-btn" title="在团队工作区添加文章" onclick={() => openCreateDocModal('团队工作区')}>+</button>
					</div>
				</div>

				{#if teamWorkspaceOpen}
					<div
						class="dashboard-collapsible-panel dashboard-team-panel space-y-2 pl-1"
						ondragover={(event) => event.preventDefault()}
						ondrop={async (event) => {
							event.preventDefault();
							if (draggingDocId) {
								await moveDocToFolder(draggingDocId, '团队工作区', '');
								draggingDocId = null;
							}
						}}
					>
						{#if teams.length > 0}
							<div class="dashboard-team-switcher px-2 py-2 rounded-xl dashboard-sidebar-card">
								<div class="dashboard-section-label">当前团队</div>
								<div class="flex items-center gap-1">
									<div class="mt-2 w-full">
										<ThemedSelect
											bind:value={currentTeamIdValue}
											options={teamSelectOptions}
											placeholder="选择当前团队"
											positioning="absolute"
											onChange={(value) => handleCurrentTeamChange(value)}
										/>
									</div>
									<button type="button" aria-label="查看团队信息" class="dashboard-btn dashboard-btn-subtle w-12 justify-center mt-2" onclick={openTeamWorkspaceModal}>
										<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24">
											<path d="M0 0h24v24H0z" fill="none" />
											<path fill="currentColor" d="M2 22a8 8 0 1 1 16 0zm8-9c-3.315 0-6-2.685-6-6s2.685-6 6-6s6 2.685 6 6s-2.685 6-6 6m7.363 2.233A7.505 7.505 0 0 1 22.983 22H20c0-2.61-1-4.986-2.637-6.767m-2.023-2.276A7.98 7.98 0 0 0 18 7a7.96 7.96 0 0 0-1.015-3.903A5 5 0 0 1 21 8a5 5 0 0 1-5.66 4.957" />
										</svg>
									</button>
								</div>
							</div>
						{:else}
							<div class="px-2 py-1 text-[11px] dashboard-muted">暂无团队，请先创建或加入团队</div>
						{/if}
						{#each teamSidebarFolders.rootDocs as item}
							<div
								class="dashboard-doc-row dashboard-sidebar-doc relative flex items-center gap-1 pr-1 rounded-lg transition-all duration-200 {activeDocIndex === item.index ? 'is-active font-bold' : ''}"
								oncontextmenu={(event) => openDocMenuFromEvent(event, item.doc.id)}
								draggable={!isFolderPlaceholderDoc(item.doc)}
								ondragstart={() => (draggingDocId = item.doc.id)}
								ondragend={() => (draggingDocId = null)}
								ondragover={(event) => {
									event.preventDefault();
									showSidebarDropLine(event.currentTarget as HTMLElement);
								}}
								ondrop={hideSidebarDropLine}
							>
								<button
									type="button"
									class="flex-1 flex items-center gap-2 px-2 py-1.5 text-left text-[12px] font-semibold cursor-pointer truncate"
									onclick={() => handleDocClick(item.index, item.doc.title)}
								>
									<span>{item.doc.emoji}</span>
									<span class="truncate">{item.doc.title}</span>
									<span class="dashboard-space-pill">{getSpaceLabel(item.doc)}</span>
								</button>
								<button id={`doc-menu-trigger-${item.doc.id}`} type="button" class="dashboard-icon-btn" onclick={() => openDocMenu(item.doc.id)}>
									<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24">
										<path d="M0 0h24v24H0z" fill="none" />
										<path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0" />
									</svg>
								</button>
							</div>
						{/each}
						{#each teamSidebarFolders.folders as folder}
							<div class="dashboard-folder-group">
								<div
									class="dashboard-folder-row"
									oncontextmenu={(event) => openSpaceContextMenu(event, '团队工作区', folder.name)}
									ondragover={(event) => event.preventDefault()}
									ondrop={async (event) => {
										event.preventDefault();
										if (draggingDocId) {
											await moveDocToFolder(draggingDocId, '团队工作区', folder.name);
											draggingDocId = null;
										}
									}}
								>
									<button type="button" class="dashboard-folder-label" onclick={() => toggleFolderCollapsed('团队工作区', folder.name)}>
										<span class:folder-collapsed={isFolderCollapsed('团队工作区', folder.name)}>▸</span>
										<span>📁</span>
										<span class="truncate">{folder.name}</span>
									</button>
								</div>
								{#if !isFolderCollapsed('团队工作区', folder.name)}
								<div class="dashboard-folder-children">
									{#each folder.docs as item}
										<div
											class="dashboard-doc-row dashboard-sidebar-doc relative flex items-center gap-1 pr-1 rounded-lg transition-all duration-200 {activeDocIndex === item.index ? 'is-active font-bold' : ''}"
											oncontextmenu={(event) => openDocMenuFromEvent(event, item.doc.id)}
											draggable={!isFolderPlaceholderDoc(item.doc)}
											ondragstart={() => (draggingDocId = item.doc.id)}
											ondragend={() => (draggingDocId = null)}
											ondragover={(event) => {
												event.preventDefault();
												showSidebarDropLine(event.currentTarget as HTMLElement);
											}}
											ondrop={hideSidebarDropLine}
										>
											<button
												type="button"
												class="flex-1 flex items-center gap-2 px-2 py-1.5 text-left text-[12px] font-semibold cursor-pointer truncate"
												onclick={() => handleDocClick(item.index, item.doc.title)}
											>
												<span>{item.doc.emoji}</span>
												<span class="truncate">{item.doc.title}</span>
												<span class="dashboard-space-pill">{getSpaceLabel(item.doc)}</span>
											</button>
											<button id={`doc-menu-trigger-${item.doc.id}`} type="button" class="dashboard-icon-btn" onclick={() => openDocMenu(item.doc.id)}>
												<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24">
													<path d="M0 0h24v24H0z" fill="none" />
													<path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0" />
												</svg>
											</button>
										</div>
									{/each}
								</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- 文档大分类 - 个人笔记 -->
			<div class="space-y-1">
				<div class="dashboard-folder-header">
					<button
						type="button"
						class="dashboard-muted dashboard-sidebar-section flex-1 flex items-center justify-between px-2 py-0.5 text-[10px] font-bold tracking-wider cursor-pointer"
						oncontextmenu={(event) => openSpaceContextMenu(event, '个人笔记')}
						onclick={() => {
							personalNotesOpen = !personalNotesOpen;
							requestAnimationFrame(() => animateSectionToggle('private', personalNotesOpen));
						}}
					>
						<span>📝 个人笔记</span>
						<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" class="transition-transform duration-200 {personalNotesOpen ? 'rotate-90' : ''}"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m9 18l6-6l-6-6"/></svg>
					</button>
					<button type="button" class="dashboard-folder-add-btn" title="在个人笔记添加文章" onclick={() => openCreateDocModal('个人笔记')}>+</button>
				</div>

				{#if personalNotesOpen}
					<div
						class="dashboard-collapsible-panel dashboard-private-panel space-y-0.5 pl-1"
						ondragover={(event) => event.preventDefault()}
						ondrop={async (event) => {
							event.preventDefault();
							if (draggingDocId) {
								await moveDocToFolder(draggingDocId, '个人笔记', '');
								draggingDocId = null;
							}
						}}
					>
						{#each privateSidebarFolders.rootDocs as item}
							<div
								class="dashboard-doc-row dashboard-sidebar-doc relative flex items-center gap-1 pr-1 rounded-lg transition-all duration-200 {activeDocIndex === item.index ? 'is-active font-bold' : ''}"
								oncontextmenu={(event) => openDocMenuFromEvent(event, item.doc.id)}
								draggable={!isFolderPlaceholderDoc(item.doc)}
								ondragstart={() => (draggingDocId = item.doc.id)}
								ondragend={() => (draggingDocId = null)}
								ondragover={(event) => {
									event.preventDefault();
									showSidebarDropLine(event.currentTarget as HTMLElement);
								}}
								ondrop={hideSidebarDropLine}
							>
								<button
									type="button"
									class="flex-1 flex items-center gap-2 px-2 py-1.5 text-left text-[12px] font-semibold cursor-pointer truncate"
									onclick={() => handleDocClick(item.index, item.doc.title)}
								>
									<span>{item.doc.emoji}</span>
									<span class="truncate">{item.doc.title}</span>
									<span class="dashboard-space-pill">{getSpaceLabel(item.doc)}</span>
								</button>
								<button id={`doc-menu-trigger-${item.doc.id}`} type="button" class="dashboard-icon-btn" onclick={() => openDocMenu(item.doc.id)}>
    								<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24">
    									<path d="M0 0h24v24H0z" fill="none" />
    									<path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0" />
    								</svg>
								</button>
							</div>
						{/each}
						{#each privateSidebarFolders.folders as folder}
							<div class="dashboard-folder-group">
								<div
									class="dashboard-folder-row"
									oncontextmenu={(event) => openSpaceContextMenu(event, '个人笔记', folder.name)}
									ondragover={(event) => event.preventDefault()}
									ondrop={async (event) => {
										event.preventDefault();
										if (draggingDocId) {
											await moveDocToFolder(draggingDocId, '个人笔记', folder.name);
											draggingDocId = null;
										}
									}}
								>
									<button type="button" class="dashboard-folder-label" onclick={() => toggleFolderCollapsed('个人笔记', folder.name)}>
										<span class:folder-collapsed={isFolderCollapsed('个人笔记', folder.name)}>▸</span>
										<span>📁</span>
										<span class="truncate">{folder.name}</span>
									</button>
								</div>
								{#if !isFolderCollapsed('个人笔记', folder.name)}
								<div class="dashboard-folder-children">
									{#each folder.docs as item}
										<div
											class="dashboard-doc-row dashboard-sidebar-doc relative flex items-center gap-1 pr-1 rounded-lg transition-all duration-200 {activeDocIndex === item.index ? 'is-active font-bold' : ''}"
											oncontextmenu={(event) => openDocMenuFromEvent(event, item.doc.id)}
											draggable={!isFolderPlaceholderDoc(item.doc)}
											ondragstart={() => (draggingDocId = item.doc.id)}
											ondragend={() => (draggingDocId = null)}
											ondragover={(event) => {
												event.preventDefault();
												showSidebarDropLine(event.currentTarget as HTMLElement);
											}}
											ondrop={hideSidebarDropLine}
										>
											<button
												type="button"
												class="flex-1 flex items-center gap-2 px-2 py-1.5 text-left text-[12px] font-semibold cursor-pointer truncate"
												onclick={() => handleDocClick(item.index, item.doc.title)}
											>
												<span>{item.doc.emoji}</span>
												<span class="truncate">{item.doc.title}</span>
												<span class="dashboard-space-pill">{getSpaceLabel(item.doc)}</span>
											</button>
											<button id={`doc-menu-trigger-${item.doc.id}`} type="button" class="dashboard-icon-btn" onclick={() => openDocMenu(item.doc.id)}>
		    								<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24">
		    									<path d="M0 0h24v24H0z" fill="none" />
		    									<path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0m7 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0" />
		    								</svg>
											</button>
										</div>
									{/each}
								</div>
								{/if}
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
				onclick={() => openCreateDocModal()}
			>
				<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v14m-7-7h14"/></svg>
				拉一坨大的
			</button>
			<button
				type="button"
				class="dashboard-list-row dashboard-sidebar-entry dashboard-muted w-full flex items-center gap-2 p-2 rounded-lg text-xs font-bold cursor-pointer transition-all duration-200"
				onclick={openGlobalSettingsModal}
			>
				<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15a3 3 0 1 0 0-6a3 3 0 0 0 0 6m7.94-2a8.99 8.99 0 0 0 .06-1a8.99 8.99 0 0 0-.06-1l2.12-1.65l-2-3.46l-2.49 1a9.2 9.2 0 0 0-1.73-1l-.38-2.65h-4l-.38 2.65a9.2 9.2 0 0 0-1.73 1l-2.49-1l-2 3.46L4.06 11a8.99 8.99 0 0 0-.06 1a8.99 8.99 0 0 0 .06 1l-2.12 1.65l2 3.46l2.49-1c.53.42 1.11.76 1.73 1l.38 2.65h4l.38-2.65c.62-.24 1.2-.58 1.73-1l2.49 1l2-3.46z"/></svg>
				全局设置
			</button>
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
				{#if isMobileViewport}
					<button
						type="button"
						class="dashboard-mobile-topbar-btn"
						aria-label="打开导航"
						onclick={() => (mobileSidebarOpen = true)}
					>
						<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7h16M4 12h16M4 17h16"/></svg>
					</button>
				{/if}
				{#if isMobileViewport}
					<span class="dashboard-strong font-semibold flex items-center gap-1 truncate min-w-0">
						<span class="shrink-0">{activeDoc?.emoji || ''}</span>
						<span class="truncate">{activeDoc?.title || '未命名文章'}</span>
					</span>
				{:else}
					<span>工作台</span>
					<span>/</span>
					<span>{activeDoc?.category || ''}</span>
					<span>/</span>
					<span class="dashboard-strong font-semibold flex items-center gap-1 truncate">
						<span>{activeDoc?.emoji || ''}</span>
						<span>{activeDoc?.title || ''}</span>
					</span>
				{/if}
			</div>
			<div class="flex items-center gap-1.5 text-xs dashboard-muted font-medium font-sans shrink-0">
				{#if isMobileViewport}
					<button
						type="button"
						class="dashboard-mobile-topbar-btn"
						aria-label="页面设置"
						onclick={openPageSettingsModal}
					>
						<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 20h9M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1l1-4z"/></svg>
					</button>
				{/if}
				<div
					class="dashboard-sync-status"
					onmouseenter={() => (showSyncStatusPopover = true)}
					onmouseleave={() => (showSyncStatusPopover = false)}
				>
					<div class="dashboard-sync-trigger">
						{#if syncStatus === 'syncing'}
							<span class="status-dot is-syncing"></span>
							<span>同步中...</span>
						{:else if syncStatus === 'saved'}
							<span class="status-dot is-saved"></span>
							<span class="status-text is-saved">已同步</span>
						{:else}
							<span class="status-dot is-idle"></span>
							<span>已离线</span>
						{/if}
					</div>
					{#if showSyncStatusPopover}
						<div class="dashboard-sync-popover">
							<div class="dashboard-sync-popover-row">
								<span class="dashboard-muted">连接状态</span>
								<span class="dashboard-strong">
									{syncStatus === 'syncing' ? '正在同步' : syncStatus === 'saved' ? '云端已连接' : '等待重试'}
								</span>
							</div>
							<div class="dashboard-sync-popover-row">
								<span class="dashboard-muted">上次保存</span>
								<span class="dashboard-strong">{formatSavedAt(lastSavedAt ?? activeDoc?.updated_at)}</span>
							</div>
						</div>
					{/if}
				</div>
			</div>
		</div>

		<!-- 高对比度封面 -->
		<div class="dashboard-cover w-full h-44 relative group overflow-hidden shrink-0">
			<div class="grid-bg absolute inset-0 opacity-60"></div>
			<!-- 科幻淡雅的线性渐变 -->
			<div class="absolute inset-0 bg-gradient-to-tr from-black/20 via-transparent to-white/10"></div>
			<div class="absolute bottom-4 right-6 flex gap-2 opacity-0 group-hover:opacity-100 transition-all duration-300">
				<button type="button" class="dashboard-overlay-btn" onclick={() => toast.info('暂不支持')}>
					更改封面
				</button>
			</div>
		</div>

		<!-- 动态内容骨架屏与 Tiptap 富文本核心画布 -->
		{#if docs.length === 0}
			<div class="mx-auto flex h-full max-w-3xl flex-col items-center justify-center px-12 text-center">
				<div class="dashboard-surface flex h-20 w-20 items-center justify-center rounded-3xl text-4xl">🗂️</div>
				<h2 class="mt-6 text-2xl font-bold dashboard-strong">这里还没有文章</h2>
				<p class="mt-3 max-w-xl dashboard-muted">
				你先看看左边都有啥呢。
				</p>
				<button type="button" class="dashboard-btn dashboard-btn-primary mt-6" onclick={() => openCreateDocModal()}>
					拉一坨大的
				</button>
			</div>
		{:else}
			<div class="mx-auto w-full max-w-4xl -translate-y-10 pb-16 relative" style={`padding-left:${pagePaddingX}px; padding-right:${pagePaddingX}px;`}>

				<!-- 超大 Emoji -->
				<div class="mb-6 flex items-center gap-4">
					<button type="button" class="dashboard-surface dashboard-emoji-trigger" onclick={openEmojiPickerModal}>
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
					<span>
						创建于 {formatCompactDate(activeDoc?.created_at)} · 更新于 {formatCompactDate(activeDoc?.updated_at)}
					</span>
				</div>

				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					bind:this={editorShellNode}
					class="editor-shell"
					onmousemove={(e) => updateBlockHandleFromPoint(e.clientX, e.clientY)}
					onmouseleave={releaseBlockHandle}
					ondrop={handleBlockDrop}
					ondragover={(e) => {
						e.preventDefault();
						handleBlockDragOver(e);
					}}
				>
					<div
						bind:this={editorNode}
						class="tiptap-editor-container {editMode !== 'rich' ? 'hidden-editor' : ''}"
						style={`font-size:${docFontSize}px; --dashboard-doc-font:${docFontFamily};`}
						onclick={hideCommandMenu}
					></div>

					{#if editMode === 'markdown' || editMode === 'html'}
						<div class="markdown-split-view">
							<div bind:this={markdownEditorNode} class="markdown-editor-host"></div>
							<div class="markdown-preview">
								<div class="markdown-preview-label">{editMode === 'html' ? 'HTML Preview' : 'Markdown Preview'}</div>
								<div class="markdown-preview-body">
									{@html markdownPreviewHtml}
								</div>
							</div>
						</div>
					{/if}

					{#if editMode === 'rich' && blockHandleVisible}
						<div
							class="block-handle opacity-0"
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
							<button
								type="button"
								class="handle-button handle-drag"
								onclick={openBlockCommandMenu}
								ondragstart={handleBlockDragStart}
								ondragend={handleBlockDragEnd}
								draggable="true"
								title="块操作"
							>
								⋮⋮
							</button>
						</div>
					{/if}

					{#if blockDragIndicator.visible}
						<div class="block-drop-indicator" style={`top:${blockDragIndicator.top}px;`}></div>
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

					{#if editor && !isMobileViewport}
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
							<button
								type="button"
								onclick={() => toggleEditMode('html')}
								class="dashboard-mode-toggle dashboard-mode-toggle-mono {editMode === 'html' ? 'dashboard-btn-primary' : 'dashboard-btn-subtle'}"
							>
								HTML
							</button>
							{#if editMode === 'markdown'}
								<button
									type="button"
									onclick={saveMarkdownChanges}
									class="dashboard-mode-toggle {markdownDirty ? 'dashboard-btn-primary' : 'dashboard-btn-subtle'}"
									title="手动保存 Markdown"
								>
									保存
								</button>
							{/if}

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
							<div class="tooltip" data-tip="插入链接">
								<button type="button" onclick={insertLink} class="dashboard-toolbar-btn" title="插入链接" aria-label="插入链接">
									<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10a5 5 0 0 1 7.54.54l.92.93a5 5 0 0 1 0 7.07l-3 3a5 5 0 0 1-7.07 0l-1-1m1.61-8.69a5 5 0 0 1-7.07 0l-1-1a5 5 0 0 1 0-7.07l3-3a5 5 0 0 1 7.07 0l.92.93A5 5 0 0 1 11 14"/></svg>
								</button>
							</div>
							<div class="tooltip" data-tip="插入图片">
								<button type="button" onclick={insertImage} class="dashboard-toolbar-btn" title="插入图片" aria-label="插入图片">
									<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2m3 6h.01M21 15l-5-5L5 21"/></svg>
								</button>
							</div>
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
								onclick={toggleTaskListBlock}
								class="dashboard-toolbar-btn {editor.isActive('taskList') ? 'is-active' : ''}"
								title="待办列表"
							>
								☑ 待办
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
							<button
								type="button"
								onclick={insertBasicTable}
								class="dashboard-toolbar-btn {editor.isActive('table') ? 'is-active' : ''}"
								title="插入表格"
							>
								表格
							</button>

							<div class="toolbar-divider mx-1 h-4 w-px"></div>

							<div class="relative">
							    <div class="tooltip" data-tip="文本颜色（右键）">
								<button
									type="button"
									class="dashboard-toolbar-btn font-black {activeTextColorState ? 'is-active' : ''}"
									style={`color:${activeTextColorState || selectedTextColor || 'var(--dashboard-fg)'};`}
									onclick={toggleTextColorPicker}
									oncontextmenu={(e) => {
										e.preventDefault();
										rememberEditorSelection();
										syncActiveFormattingState();
										showTextColorModal = true;
										showHighlightColorModal = false;
									}}
									title="文本颜色"
								>A</button>
								</div>
							</div>

							<div class="relative">
								<div class="tooltip" data-tip="文字背景色（右键）">
									<button
										type="button"
										class="dashboard-toolbar-btn font-black {activeHighlightColorState ? 'is-active' : ''}"
										onclick={toggleHighlightColorPicker}
										oncontextmenu={(e) => {
											e.preventDefault();
											rememberEditorSelection();
											syncActiveFormattingState();
											showHighlightColorModal = true;
											showTextColorModal = false;
										}}
										title="文字背景色"
									><span class="dashboard-highlight-chip" style={`background:${activeHighlightColorState || selectedHighlightColor || 'color-mix(in oklab, var(--dashboard-accent) 20%, transparent)'};`}>A</span></button>
								</div>
							</div>

							<div class="toolbar-divider mx-1 h-4 w-px"></div>

							<div class="tooltip" data-tip="撤销">
								<button
									type="button"
									onclick={runUndo}
									disabled={!canUndo()}
									class="dashboard-toolbar-btn"
									title="撤销"
								>
									↩
								</button>
							</div>
							<div class="tooltip" data-tip="重做">
								<button
									type="button"
									onclick={runRedo}
									disabled={!canRedo()}
									class="dashboard-toolbar-btn"
									title="重做"
								>
									↪
								</button>
							</div>
							</div>
						</div>
					{/if}
				</div>

			</div>
		{/if}

	</div>

	<button type="button" class="page-settings-fab" onclick={openPageSettingsModal} title="页面设置" hidden={isMobileViewport}>
		<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 20h9M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1l1-4z"/></svg>
	</button>

</div>

{#if editor && isMobileViewport}
	<div bind:this={mobileToolbarRootNode} class="dashboard-mobile-toolbar-root">
		<div use:bindMobileToolbarGesture bind:this={mobileToolbarSheetNode} class="dashboard-mobile-toolbar-sheet {mobileToolbarExpanded ? 'is-expanded' : ''}">
			<div class="dashboard-mobile-toolbar-sheet-handle-wrap">
				<button
					type="button"
					class="dashboard-mobile-toolbar-sheet-handle"
					aria-label={mobileToolbarExpanded ? '收起工具栏' : '展开工具栏'}
					aria-expanded={mobileToolbarExpanded}
					onclick={toggleMobileToolbar}
				>
					<span class="dashboard-mobile-toolbar-sheet-grabber"></span>
					<!-- <svg class={`dashboard-mobile-toolbar-arrow ${mobileToolbarExpanded ? 'is-open' : ''}`} xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
						<path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m6 9l6 6l6-6"/>
					</svg> -->
				</button>
			</div>
			<div class="dashboard-mobile-toolbar-bar">
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
			</div>
			<div bind:this={mobileToolbarOverlayNode} class="editor-toolbar-overlay is-mobile {mobileToolbarExpanded ? 'is-expanded' : ''}">
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
				<button
					type="button"
					onclick={() => toggleEditMode('html')}
					class="dashboard-mode-toggle dashboard-mode-toggle-mono {editMode === 'html' ? 'dashboard-btn-primary' : 'dashboard-btn-subtle'}"
				>
					HTML
				</button>
				{#if editMode === 'markdown'}
					<button
						type="button"
						onclick={saveMarkdownChanges}
						class="dashboard-mode-toggle {markdownDirty ? 'dashboard-btn-primary' : 'dashboard-btn-subtle'}"
						title="手动保存 Markdown"
					>
						保存
					</button>
				{/if}

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
				<div class="tooltip" data-tip="插入链接">
					<button type="button" onclick={insertLink} class="dashboard-toolbar-btn" title="插入链接" aria-label="插入链接">
						<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10a5 5 0 0 1 7.54.54l.92.93a5 5 0 0 1 0 7.07l-3 3a5 5 0 0 1-7.07 0l-1-1m1.61-8.69a5 5 0 0 1-7.07 0l-1-1a5 5 0 0 1 0-7.07l3-3a5 5 0 0 1 7.07 0l.92.93A5 5 0 0 1 11 14"/></svg>
					</button>
				</div>
				<div class="tooltip" data-tip="插入图片">
					<button type="button" onclick={insertImage} class="dashboard-toolbar-btn" title="插入图片" aria-label="插入图片">
						<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2m3 6h.01M21 15l-5-5L5 21"/></svg>
					</button>
				</div>
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
					onclick={toggleTaskListBlock}
					class="dashboard-toolbar-btn {editor.isActive('taskList') ? 'is-active' : ''}"
					title="待办列表"
				>
					☑ 待办
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
				<button
					type="button"
					onclick={insertBasicTable}
					class="dashboard-toolbar-btn {editor.isActive('table') ? 'is-active' : ''}"
					title="插入表格"
				>
					表格
				</button>

				<div class="toolbar-divider mx-1 h-4 w-px"></div>

				<div class="relative">
					<div class="tooltip" data-tip="文本颜色">
						<button
							type="button"
							class="dashboard-toolbar-btn font-black {activeTextColorState ? 'is-active' : ''}"
							style={`color:${activeTextColorState || selectedTextColor || 'var(--dashboard-fg)'};`}
							onclick={toggleTextColorPicker}
							oncontextmenu={(e) => {
								e.preventDefault();
								rememberEditorSelection();
								syncActiveFormattingState();
								showTextColorModal = true;
								showHighlightColorModal = false;
							}}
							title="文本颜色"
						>A</button>
					</div>
				</div>

				<div class="relative">
					<div class="tooltip" data-tip="文字背景色">
						<button
							type="button"
							class="dashboard-toolbar-btn font-black {activeHighlightColorState ? 'is-active' : ''}"
							style={`background:${activeHighlightColorState || selectedHighlightColor || 'transparent'}; color:${activeHighlightColorState ? '#111' : 'var(--dashboard-fg)'};`}
							onclick={toggleHighlightColorPicker}
							oncontextmenu={(e) => {
								e.preventDefault();
								rememberEditorSelection();
								syncActiveFormattingState();
								showHighlightColorModal = true;
								showTextColorModal = false;
							}}
							title="文字背景色"
						>A</button>
					</div>
				</div>

				<div class="toolbar-divider mx-1 h-4 w-px"></div>

				<button
					type="button"
					onclick={runUndo}
					disabled={!canUndo()}
					class="dashboard-toolbar-btn"
					title="撤销"
				>↺</button>
				<button
					type="button"
					onclick={runRedo}
					disabled={!canRedo()}
					class="dashboard-toolbar-btn"
					title="重做"
				>↻</button>
			</div>
		</div>
	</div>
{/if}

{#if activeDocMenuId !== null}
	<div class="doc-menu-backdrop" onclick={closeDocMenu}></div>
	<div
		bind:this={docMenuNode}
		class="doc-menu doc-menu-floating"
		style={`top:${docMenuPosition.top}px; left:${docMenuPosition.left}px;`}
	>
		<div class="doc-menu-headerline">
			<span class="doc-menu-kicker">必须操作你了</span>
		</div>
		<button class="doc-menu-item" type="button" onclick={renameActiveDoc}>
			<span class="doc-menu-icon">✎</span>
			<span class="doc-menu-copy">
				<span class="doc-menu-title">重命名</span>
				<span class="doc-menu-desc">修改页面标题</span>
			</span>
		</button>
		<button class="doc-menu-item" type="button" onclick={duplicateActiveDoc}>
			<span class="doc-menu-icon">⧉</span>
			<span class="doc-menu-copy">
				<span class="doc-menu-title">克隆</span>
				<span class="doc-menu-desc">疯狂地生。</span>
			</span>
		</button>
		<button
			class="doc-menu-item"
			type="button"
			onclick={() => {
				propertiesDocId = activeDocMenuId;
				showPropertiesModal = true;
				closeDocMenu();
			}}
		>
			<span class="doc-menu-icon">◎</span>
			<span class="doc-menu-copy">
				<span class="doc-menu-title">属性</span>
				<span class="doc-menu-desc">查看页面元信息</span>
			</span>
		</button>
		<div class="doc-menu-divider"></div>
		<button type="button" class="doc-menu-item is-danger" onclick={deleteActiveDoc}>
			<span class="doc-menu-icon" aria-hidden="true">
				<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24">
					<path d="M0 0h24v24H0z" fill="none" />
					<path fill="currentColor" d="M12 0a12 12 0 1 0 12 12A12 12 0 0 0 12 0M5.29 5.29a9.63 9.63 0 0 1 12.23-1a.26.26 0 0 1 0 .4L4.67 17.56a.27.27 0 0 1-.4 0a9.49 9.49 0 0 1 1-12.24Zm13.46 13.47a9.53 9.53 0 0 1-12.23 1a.26.26 0 0 1 0-.4L19.37 6.49a.26.26 0 0 1 .4 0a9.49 9.49 0 0 1-1 12.24Z" />
				</svg>
			</span>
			<span class="doc-menu-copy">
				<span class="doc-menu-title">删除</span>
				<span class="doc-menu-desc">移除此文章</span>
			</span>
							</button>
						</div>
					{/if}

{#if tableContextMenuOpen}
	<div class="doc-menu-backdrop" onclick={closeTableContextMenu}></div>
	<div
		bind:this={tableContextMenuNode}
		class="doc-menu doc-menu-floating"
		style={`top:${tableContextMenuPosition.top}px; left:${tableContextMenuPosition.left}px;`}
	>
		<div class="doc-menu-headerline">
			<span class="doc-menu-kicker">表格操作</span>
		</div>
		<button class="doc-menu-item" type="button" onclick={() => { addTableRowAfter(); closeTableContextMenu(); }}>
			<span class="doc-menu-icon">＋</span>
			<span class="doc-menu-copy">
				<span class="doc-menu-title">新增一行</span>
				<span class="doc-menu-desc">在当前行后面插入</span>
			</span>
		</button>
		<button class="doc-menu-item" type="button" onclick={() => { addTableColumnAfter(); closeTableContextMenu(); }}>
			<span class="doc-menu-icon">＋</span>
			<span class="doc-menu-copy">
				<span class="doc-menu-title">新增一列</span>
				<span class="doc-menu-desc">在当前列右侧插入</span>
			</span>
		</button>
		<div class="doc-menu-divider"></div>
		<button class="doc-menu-item" type="button" onclick={() => { editor?.chain().focus().deleteRow().run(); closeTableContextMenu(); }}>
			<span class="doc-menu-icon">－</span>
			<span class="doc-menu-copy">
				<span class="doc-menu-title">删除当前行</span>
				<span class="doc-menu-desc">移除所在行</span>
			</span>
		</button>
		<button class="doc-menu-item" type="button" onclick={() => { editor?.chain().focus().deleteColumn().run(); closeTableContextMenu(); }}>
			<span class="doc-menu-icon">－</span>
			<span class="doc-menu-copy">
				<span class="doc-menu-title">删除当前列</span>
				<span class="doc-menu-desc">移除所在列</span>
			</span>
		</button>
	</div>
{/if}

{#if spaceContextMenuOpen}
	<div class="doc-menu-backdrop" onclick={closeSpaceContextMenu}></div>
	<div
		bind:this={spaceContextMenuNode}
		class="doc-menu doc-menu-floating space-context-menu"
		style={`top:${spaceContextMenuPosition.top}px; left:${spaceContextMenuPosition.left}px;`}
	>
		<div class="doc-menu-headerline">
			<span class="doc-menu-kicker">{spaceContextMenuCategory}</span>
		</div>
		<button class="doc-menu-item" type="button" onclick={() => createDocInSpace(spaceContextMenuCategory)}>
			<span class="doc-menu-icon">＋</span>
			<span class="doc-menu-copy">
				<span class="doc-menu-title">添加文章</span>
				<span class="doc-menu-desc">禁止随地大小便</span>
			</span>
		</button>
		<button class="doc-menu-item" type="button" onclick={() => createFolderInSpace(spaceContextMenuCategory)}>
			<span class="doc-menu-icon">📁</span>
			<span class="doc-menu-copy">
				<span class="doc-menu-title">添加文件夹</span>
				<span class="doc-menu-desc">我的篮子非常大，适合日常的收纳</span>
			</span>
		</button>
		{#if spaceContextMenuFolder}
			<div class="doc-menu-divider"></div>
			<button class="doc-menu-item" type="button" onclick={openRenameFolderModal}>
				<span class="doc-menu-icon">✎</span>
				<span class="doc-menu-copy">
					<span class="doc-menu-title">重命名文件夹</span>
					<span class="doc-menu-desc">修改当前文件夹名称</span>
				</span>
			</button>
			<button class="doc-menu-item" type="button" onclick={openMoveFolderModal}>
				<span class="doc-menu-icon">⇄</span>
				<span class="doc-menu-copy">
					<span class="doc-menu-title">批量迁移文章</span>
					<span class="doc-menu-desc">把当前文件夹内文章移到别的文件夹（NTR？）</span>
				</span>
			</button>
			<button class="doc-menu-item is-danger" type="button" onclick={openDeleteFolderModal}>
				<span class="doc-menu-icon">⊘</span>
				<span class="doc-menu-copy">
					<span class="doc-menu-title">删除文件夹</span>
					<span class="doc-menu-desc">删除文件夹并把文章移回根分组</span>
				</span>
			</button>
		{/if}
	</div>
{/if}

{#if showQuickSearchModal}
	<div class="dashboard-modal-backdrop" onclick={closeQuickSearchModal}>
		<div
			class="dashboard-modal-box dashboard-modal-medium dashboard-quick-search-modal"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="dashboard-modal-header">
				<div>
					<h3 class="dashboard-modal-title">快速检索</h3>
					<p class="dashboard-muted mt-1 text-xs">按标题、空间、分组或正文内容搜索，快捷键 `Ctrl/Cmd + K`。</p>
				</div>
				<button type="button" class="dashboard-icon-btn" onclick={closeQuickSearchModal}>✕</button>
			</div>
			<div class="dashboard-field mb-2">
				<input
					bind:this={quickSearchInputNode}
					bind:value={quickSearchInput}
					class="dashboard-input"
					placeholder="输入关键词，比如：炉管、API、团队、原神……"
				/>
			</div>
			<div class="dashboard-quick-search-results">
				{#if quickSearchResults.length === 0}
					<div class="dashboard-quick-search-empty">
						<div class="dashboard-strong font-semibold">没有找到匹配内容</div>
						<div class="dashboard-muted text-xs">换个关键词，或者先创建一篇新文章。</div>
					</div>
				{:else}
					{#each quickSearchResults as result}
						<button
							type="button"
							class="dashboard-quick-search-item"
							onclick={() => handleDocClick(result.index, result.doc.title)}
						>
							<div class="dashboard-quick-search-main">
								<div class="flex min-w-0 items-center gap-2">
									<span class="shrink-0 text-base">{result.doc.emoji || '📝'}</span>
									<span class="dashboard-strong truncate font-semibold">{result.doc.title}</span>
									<span class="dashboard-space-pill shrink-0">{getSpaceLabel(result.doc)}</span>
								</div>
								<div class="dashboard-muted shrink-0 text-[11px]">/{result.doc.category || '未分类'}</div>
							</div>
							<div class="dashboard-muted line-clamp-2 text-left text-xs">{result.snippet}</div>
						</button>
					{/each}
				{/if}
			</div>
		</div>
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

{#if showUserProfileModal}
	<div class="dashboard-modal-backdrop" onclick={() => showUserProfileModal = false}>
		<div class="dashboard-modal-box dashboard-modal-medium dashboard-user-profile-modal" onclick={(e) => e.stopPropagation()}>
			<div class="dashboard-modal-header">
				<h3 class="dashboard-modal-title">个人信息</h3>
				<button type="button" class="dashboard-icon-btn" onclick={() => showUserProfileModal = false}>✕</button>
			</div>
			<div class="dashboard-modal-body">
				<div class="flex items-center gap-4">
					<div class="dashboard-user-avatar-preview">
						{#if userState.avatarUrl}
							<img src={userState.avatarUrl} alt="用户头像" class="h-full w-full object-cover" />
						{:else}
							AM
						{/if}
					</div>
					<div class="min-w-0">
						<div class="dashboard-strong text-base font-bold">{userState.session?.user?.username || '游客'}</div>
						<div class="dashboard-helper-text mt-1">默认头像是随机生成的，你可以在下面自定义，但是吧别的我还没写）</div>
					</div>
				</div>
				<div class="flex flex-wrap gap-2">
					<label class="dashboard-btn dashboard-btn-primary cursor-pointer">
						上传头像
						<input
							type="file"
							accept="image/*"
							class="hidden"
							onchange={(e) => {
								const file = (e.currentTarget as HTMLInputElement).files?.[0];
								if (file) uploadCustomAvatar(file);
								(e.currentTarget as HTMLInputElement).value = '';
							}}
						/>
					</label>
					<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={randomizeUserAvatar}>随机生成</button>
					<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={resetUserAvatar}>恢复默认</button>
				</div>
				{#if avatarUploading}
					<div class="dashboard-helper-text">头像上传中...</div>
				{/if}
			</div>
			<div class="dashboard-modal-actions dashboard-user-profile-actions">
				<button
					type="button"
					class="dashboard-btn dashboard-btn-danger dashboard-user-logout-btn"
					onclick={() => {
						showUserProfileModal = false;
						logoutCurrentUser();
					}}
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 8V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2m7-2H9m11-3l3 3l-3 3"/></svg>
					登出
				</button>
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showUserProfileModal = false}>关闭</button>
			</div>
		</div>
	</div>
{/if}

{#if showTextColorModal}
	<div class="dashboard-modal-backdrop" onclick={() => showTextColorModal = false}>
		<div class="dashboard-modal-box dashboard-modal-medium" onclick={(e) => e.stopPropagation()}>
			<h3 class="dashboard-modal-title">文本颜色</h3>
			<div class="dashboard-modal-body">
				<div class="color-preview h-14" style={`background:${selectedTextColor || '#111827'};`}></div>
				<div class="grid grid-cols-6 gap-2">
					{#each ['oklch(0.22 0.03 258)', 'oklch(0.32 0.12 260)', 'oklch(0.55 0.18 25)', 'oklch(0.62 0.17 145)', 'oklch(0.68 0.15 330)', 'oklch(0.8 0.08 95)', 'oklch(0.92 0.01 250)', 'oklch(0.45 0.2 15)', 'oklch(0.35 0.11 220)', 'oklch(0.72 0.16 80)', 'oklch(0.58 0.22 345)', 'oklch(0.28 0.02 260)'] as color}
						<button type="button" class="preset-swatch" style={`background:${color};`} onclick={() => { selectedTextColor = color; applyTextColor(color); syncActiveFormattingState(); }} aria-label={`文本颜色 ${color}`} title={`文本颜色 ${color}`}></button>
					{/each}
				</div>
				<label class="color-control"><span>Lightness</span><input type="range" min="0" max="100" bind:value={textColorControls.l} oninput={applyCurrentTextColor} class="theme-range lightness-range" /></label>
				<label class="color-control"><span>Chroma</span><input type="range" min="0" max="0.37" step="0.005" bind:value={textColorControls.c} oninput={applyCurrentTextColor} class="theme-range chroma-range" /></label>
				<label class="color-control"><span>Hue</span><input type="range" min="0" max="360" bind:value={textColorControls.h} oninput={applyCurrentTextColor} class="theme-range hue-range" /></label>
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={resetTextColor}>恢复默认</button>
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showTextColorModal = false}>关闭</button>
			</div>
		</div>
	</div>
{/if}

{#if showHighlightColorModal}
	<div class="dashboard-modal-backdrop" onclick={() => showHighlightColorModal = false}>
		<div class="dashboard-modal-box dashboard-modal-medium" onclick={(e) => e.stopPropagation()}>
			<h3 class="dashboard-modal-title">文字背景色</h3>
			<div class="dashboard-modal-body">
				<div class="color-preview h-14" style={`background:${selectedHighlightColor || '#fef08a'};`}></div>
				<div class="grid grid-cols-6 gap-2">
					{#each ['oklch(0.96 0.08 95)', 'oklch(0.95 0.09 50)', 'oklch(0.92 0.08 145)', 'oklch(0.93 0.08 250)', 'oklch(0.9 0.11 330)', 'oklch(0.87 0.13 20)', 'oklch(0.84 0.1 80)', 'oklch(0.91 0.06 220)', 'oklch(0.89 0.05 20)', 'oklch(0.97 0.03 260)', 'oklch(0.88 0.12 300)', 'oklch(0.82 0.1 170)'] as color}
						<button type="button" class="preset-swatch" style={`background:${color};`} onclick={() => { selectedHighlightColor = color; applyHighlightColor(color); syncActiveFormattingState(); }} aria-label={`背景颜色 ${color}`} title={`背景颜色 ${color}`}></button>
					{/each}
				</div>
				<label class="color-control"><span>Lightness</span><input type="range" min="0" max="100" bind:value={highlightColorControls.l} oninput={applyCurrentHighlightColor} class="theme-range lightness-range" /></label>
				<label class="color-control"><span>Chroma</span><input type="range" min="0" max="0.37" step="0.005" bind:value={highlightColorControls.c} oninput={applyCurrentHighlightColor} class="theme-range chroma-range" /></label>
				<label class="color-control"><span>Hue</span><input type="range" min="0" max="360" bind:value={highlightColorControls.h} oninput={applyCurrentHighlightColor} class="theme-range hue-range" /></label>
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={resetHighlightColor}>恢复默认</button>
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showHighlightColorModal = false}>关闭</button>
			</div>
		</div>
	</div>
{/if}

{#if showLinkModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box dashboard-modal-medium">
			<h3 class="dashboard-modal-title">插入超链接</h3>
			<div class="dashboard-field">
				<span class="dashboard-field-label">链接地址</span>
				<input bind:value={linkUrlInput} class="dashboard-input" placeholder="https://example.com" />
			</div>
			<div class="dashboard-field">
				<span class="dashboard-field-label">链接文本</span>
				<input bind:value={linkTextInput} class="dashboard-input" placeholder="链接文字" />
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showLinkModal = false}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-primary" onclick={confirmInsertLink}>插入</button>
			</div>
		</div>
	</div>
{/if}

{#if showImageModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box dashboard-modal-medium">
			<h3 class="dashboard-modal-title">插入图片</h3>
			<div class="dashboard-field">
				<span class="dashboard-field-label">图片 URL</span>
				<input bind:value={imageUrlInput} class="dashboard-input" placeholder="https://example.com/image.png" />
			</div>
			<div class="dashboard-field">
				<span class="dashboard-field-label">或上传图片文件</span>
				<label class="dashboard-btn dashboard-btn-subtle justify-center">
					选择图片
					<input
						type="file"
						accept="image/*"
						class="hidden"
						onchange={(e) => {
							const file = (e.currentTarget as HTMLInputElement).files?.[0];
							if (file) handleImageFileUpload(file);
						}}
					/>
				</label>
			</div>
			<div class="dashboard-helper-text">也支持直接把图片拖进编辑器。</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showImageModal = false}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-primary" onclick={confirmInsertImageUrl}>插入 URL 图片</button>
			</div>
		</div>
	</div>
{/if}

{#if showHtmlModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box dashboard-modal-medium">
			<h3 class="dashboard-modal-title">插入 HTML</h3>
			<div class="dashboard-field">
				<span class="dashboard-field-label">HTML 代码</span>
				<textarea bind:value={htmlEmbedInput} class="dashboard-input dashboard-textarea" rows="8" placeholder="<iframe ...></iframe>"></textarea>
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showHtmlModal = false}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-primary" onclick={confirmInsertSafeHtml}>插入</button>
			</div>
		</div>
	</div>
{/if}

{#if showRenameModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box">
			<h3 class="dashboard-modal-title">重命名文章</h3>
			<div class="dashboard-field">
				<span class="dashboard-field-label">文章标题</span>
				<input bind:value={renameInput} class="dashboard-input" placeholder="输入新的文章标题" />
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showRenameModal = false}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-primary" onclick={confirmRenameDoc}>保存</button>
			</div>
		</div>
	</div>
{/if}

{#if showRenameFolderModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box">
			<h3 class="dashboard-modal-title">重命名文件夹</h3>
			<div class="dashboard-field">
				<span class="dashboard-field-label">文件夹名称</span>
				<input bind:value={renameFolderInput} class="dashboard-input" placeholder="新的文件夹名称" />
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showRenameFolderModal = false}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-primary" onclick={confirmRenameFolder}>保存</button>
			</div>
		</div>
	</div>
{/if}

{#if showDeleteFolderModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box">
			<h3 class="dashboard-modal-title">删除文件夹</h3>
			<div class="dashboard-helper-text">确认删除文件夹“{spaceContextMenuFolder}”？文件夹内文章会被移回当前空间根分组。</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showDeleteFolderModal = false}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-danger" onclick={confirmDeleteFolder}>删除</button>
			</div>
		</div>
	</div>
{/if}

{#if showMoveFolderModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box">
			<h3 class="dashboard-modal-title">批量迁移文件夹内文章</h3>
			<div class="dashboard-field">
				<span class="dashboard-field-label">目标文件夹</span>
				<input bind:value={moveFolderTarget} class="dashboard-input" placeholder="输入目标文件夹名称" />
			</div>
			<div class="dashboard-helper-text">会把“{spaceContextMenuFolder}”里的普通文章批量移动到目标文件夹。</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showMoveFolderModal = false}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-primary" onclick={confirmMoveFolderDocs}>迁移</button>
			</div>
		</div>
	</div>
{/if}

{#if showDeleteDocModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box">
			<h3 class="dashboard-modal-title">删除文章</h3>
			<div class="dashboard-helper-text">确认删除当前文章？此操作不可撤销。</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showDeleteDocModal = false}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-danger" onclick={confirmDeleteActiveDoc}>删除</button>
			</div>
		</div>
	</div>
{/if}

{#if showCreateDocModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box">
			<h3 class="dashboard-modal-title">添加新文章</h3>
			<div class="dashboard-field">
				<span class="dashboard-field-label">文章标题</span>
				<input bind:value={newDocTitleInput} class="dashboard-input" placeholder="未命名文章" />
			</div>
			<div class="dashboard-field">
				<span class="dashboard-field-label">文章空间</span>
				<ThemedSelect
					bind:value={newDocCategoryInput}
					options={createDocSpaceOptions}
					placeholder="选择文章空间"
				/>
			</div>
			<div class="dashboard-field">
				<div class="flex items-center justify-between gap-3">
					<span class="dashboard-field-label">子文件夹</span>
					<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={openCreateFolderModal}>新建文件夹</button>
				</div>
				{#if folderOptionsBySpace[newDocCategoryInput as keyof typeof folderOptionsBySpace].length > 0}
					<div class="mt-2">
						<ThemedSelect
							bind:value={newDocFolderInput}
							options={folderSelectOptions}
							placeholder="选择子文件夹"
						/>
					</div>
				{:else}
					<input bind:value={newDocFolderInput} class="dashboard-input mt-2" placeholder="留空则进入默认分组" />
				{/if}
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showCreateDocModal = false}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-primary" onclick={() => createNewDoc(newDocCategoryInput)}>创建</button>
			</div>
		</div>
	</div>
{/if}

{#if showCreateFolderModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box">
			<h3 class="dashboard-modal-title">添加文件夹</h3>
			<div class="dashboard-field">
				<span class="dashboard-field-label">文件夹名称</span>
				<input bind:value={newFolderInput} class="dashboard-input" placeholder="新的文件夹" />
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => showCreateFolderModal = false}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-primary" onclick={confirmCreateFolder}>创建</button>
			</div>
		</div>
	</div>
{/if}

{#if showMarkdownWarningModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box dashboard-modal-medium">
			<h3 class="dashboard-modal-title">切换到 Markdown 编辑</h3>
			<div class="dashboard-helper-text">
				格式可能无法完全转换。颜色、高亮和部分自定义 HTML 结构在 Markdown 模式下可能会丢失。
			</div>
			<div class="dashboard-helper-text">
				如果继续，我们会尽量把当前文章转成 Markdown；你编辑完成后，再把 Markdown 重新转换成 HTML 文档。
			</div>
			<div class="dashboard-helper-text">
				进入 Markdown 模式后不会自动保存，修改完成后需要你手动点“保存”。
			</div>
			<div class="dashboard-modal-actions">
				<button
					type="button"
					class="dashboard-btn dashboard-btn-subtle"
					onclick={() => {
						showMarkdownWarningModal = false;
						pendingEditMode = null;
					}}
				>
					取消
				</button>
				<button type="button" class="dashboard-btn dashboard-btn-primary" onclick={confirmMarkdownModeSwitch}>
					继续进入 Markdown
				</button>
			</div>
		</div>
	</div>
{/if}

{#if showTeamWorkspaceModal}
	<div class="dashboard-modal-backdrop" onclick={() => showTeamWorkspaceModal = false}>
		<div class="dashboard-modal-box dashboard-modal-large" onclick={(e) => e.stopPropagation()}>
			<div class="dashboard-modal-header">
				<h3 class="dashboard-modal-title">团队空间</h3>
				<button type="button" class="dashboard-icon-btn" onclick={() => showTeamWorkspaceModal = false}>✕</button>
			</div>
			<div class="dashboard-settings-grid">
				<div class="space-y-3">
					<div class="dashboard-section-label">创建团队</div>
					<input type="text" bind:value={newTeamName} class="dashboard-input" placeholder="团队名称" />
					<input type="text" bind:value={newTeamSlug} class="dashboard-input" placeholder="团队 slug" />
					<button type="button" class="dashboard-btn dashboard-btn-primary w-full justify-center" onclick={handleCreateTeam}>
						创建团队
					</button>
				</div>
				<div class="space-y-3">
					<div class="dashboard-section-label">管理与加入</div>
					{#if teams.length > 0}
						<ThemedSelect
							bind:value={currentTeamIdValue}
							options={teamSelectOptions}
							placeholder="选择团队"
							onChange={(value) => handleCurrentTeamChange(value)}
						/>
						<button type="button" class="dashboard-btn dashboard-btn-subtle w-full justify-center" onclick={handleCreateInvite}>
							生成邀请令牌
						</button>
						{#if teamInvites.length > 0}
							<div class="dashboard-helper-text">最近邀请：{teamInvites[0].token}</div>
						{/if}
					{:else}
						<div class="dashboard-helper-text">你还没有加入任何团队。</div>
					{/if}
					<input type="text" bind:value={inviteTokenInput} class="dashboard-input" placeholder="输入邀请令牌加入团队" />
					<button type="button" class="dashboard-btn dashboard-btn-subtle w-full justify-center" onclick={handleAcceptInvite}>
						加入团队
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}

{#if showEncryptionSetupModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box dashboard-modal-medium">
			<h3 class="dashboard-modal-title">初始化文档加密</h3>
			<div class="dashboard-helper-text my-0.5">
				为了保护你的私有文章，Amnesia 会在文档上传前先在浏览器本地完成加密，再把密文存进数据库。
			</div>
			<div class="dashboard-helper-text my-0.5">
				目前的逻辑是：先使用你的登录密码通过本地派生逻辑生成文档密钥，再用 Web Crypto API 的 <strong>AES-GCM</strong> 算法对私有文章内容加密；数据库里保存的是密文、随机 IV 和版本信息，而不是可直接阅读的正文。
			</div>
			<div class="dashboard-helper-text my-0.5">
				之所以这样做，是因为我不想在数据库里直接看到其他用户的私人文章内容，所以即使我去翻数据库，也看不到你的正文实际内容。
			</div>
			<div class="dashboard-helper-text my-0.5">
				这意味着你的私有文章默认会以“先本地加密、再上传”的方式保存；只有输入正确的登录密码，浏览器才能重新派生出同一把密钥并解密内容。这个初始化只允许设置一次，之后无法修改。你可以随时导出你的文章（以已解密或者加密的形式）。请确认你已经理解这个机制。
			</div>
			<div class="dashboard-helper-text my-0.5">
				请输入你当前账号的登录密码来确认并生成文档加密密钥。如果以后忘记登录密码，私有文章内容也会随之无法恢复，请务必自行保管好密码。
			</div>
			<div class="dashboard-field">
				<span class="dashboard-field-label">输入你的登录密码</span>
				<input type="password" bind:value={encryptionPasswordInput} class="dashboard-input" placeholder="用于派生文档加密密钥" />
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-primary" onclick={confirmEncryptionSetup}>确认初始化</button>
			</div>
		</div>
	</div>
{/if}


{#if showPropertiesModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box">
			<h3 class="dashboard-modal-title">页面属性</h3>
			<div class="dashboard-properties-grid">
				<div class="dashboard-property-row"><span class="dashboard-muted">作者</span><span>{propertiesDoc?.author || userState.session?.user?.username || '未知'}</span></div>
				<div class="dashboard-property-row"><span class="dashboard-muted">创建时间</span><span>{propertiesDoc?.created_at || '未记录'}</span></div>
				<div class="dashboard-property-row"><span class="dashboard-muted">最后编辑</span><span>{propertiesDoc?.updated_at || '未记录'}</span></div>
				<div class="dashboard-property-row"><span class="dashboard-muted">分类</span><span>{propertiesDoc?.category || '未分类'}</span></div>
				<div class="dashboard-property-row"><span class="dashboard-muted">空间</span><span>{getSpaceLabel(propertiesDoc)}</span></div>
			</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => { showPropertiesModal = false; propertiesDocId = null; }}>关闭</button>
			</div>
		</div>
	</div>
{/if}

{#if showDeleteUserModal}
	<div class="dashboard-modal-backdrop">
		<div class="dashboard-modal-box">
			<h3 class="dashboard-modal-title">删除用户</h3>
			<div class="dashboard-helper-text">确认删除用户 “{pendingDeleteUsername}”？此操作不可撤销。</div>
			<div class="dashboard-modal-actions">
				<button type="button" class="dashboard-btn dashboard-btn-subtle" onclick={() => { showDeleteUserModal = false; pendingDeleteUsername = ''; }}>取消</button>
				<button type="button" class="dashboard-btn dashboard-btn-danger" onclick={confirmDeleteUser}>删除</button>
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
							<ThemedSelect
								bind:value={theme}
								options={themeSelectOptions}
								placeholder="选择主题"
								onChange={() => { applyTheme(); persistDashboardSettings(); }}
							/>
						</div>
						<div class="dashboard-field">
							<span class="dashboard-field-label">全局界面字体</span>
							<ThemedSelect
								bind:value={globalUiFont}
								options={fontSelectOptions}
								placeholder="选择全局字体"
								onChange={() => { applyTheme(); persistDashboardSettings(); }}
							/>
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
					<ThemedSelect
						bind:value={docFontFamily}
						options={fontSelectOptions}
						placeholder="选择页面字体"
						onChange={() => { applyTheme(); persistDashboardSettings(); }}
					/>
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
						<ThemedSelect
							bind:value={newRole}
							options={roleSelectOptions}
							placeholder="选择权限"
						/>
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

	.dashboard-mobile-sidebar-backdrop {
		position: fixed;
		inset: 0;
		z-index: 44;
		border: none;
		background: color-mix(in oklab, black 40%, transparent);
		backdrop-filter: blur(10px);
	}

	.dashboard-topbar {
		border-bottom: 1px solid color-mix(in oklab, var(--dashboard-fg) 8%, transparent);
		background: color-mix(in oklab, var(--dashboard-panel) 86%, transparent);
		backdrop-filter: blur(18px);
	}

	.dashboard-mobile-topbar-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border: 1px solid var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.45);
		background: color-mix(in oklab, var(--dashboard-panel) 90%, transparent);
		color: var(--dashboard-fg);
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
		padding-left: 2px;
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
		padding-left: 2px;
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

	.dashboard-user-avatar-preview {
		display: flex;
		height: 4.75rem;
		width: 4.75rem;
		flex-shrink: 0;
		align-items: center;
		justify-content: center;
		overflow: hidden;
		border: 1px solid var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.8);
		background: color-mix(in oklab, var(--dashboard-panel) 88%, var(--dashboard-bg));
		box-shadow: 0 10px 24px var(--dashboard-shadow-color);
		font-size: 1.25rem;
		font-weight: 800;
		color: var(--dashboard-fg);
	}

	.dashboard-user-profile-actions {
		justify-content: space-between;
		align-items: center;
	}

	.dashboard-user-logout-btn {
		margin-right: auto;
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

	.dashboard-sync-status {
		position: relative;
		display: inline-flex;
		align-items: center;
	}

	.dashboard-sync-trigger {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.28rem 0.55rem;
		border-radius: 999px;
		background: color-mix(in oklab, var(--dashboard-panel) 68%, transparent);
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 7%, transparent);
		backdrop-filter: blur(12px);
	}

	.dashboard-sync-popover {
		position: absolute;
		top: calc(100% + 0.55rem);
		right: 0;
		z-index: 35;
		min-width: 14rem;
		border-radius: calc(var(--dashboard-radius) * 0.65);
		border: 1px solid var(--dashboard-border);
		background: color-mix(in oklab, var(--dashboard-panel) 94%, transparent);
		padding: 0.8rem 0.9rem;
		box-shadow: 0 18px 42px var(--dashboard-shadow-color);
		backdrop-filter: blur(18px);
	}

	.dashboard-sync-popover-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		font-size: 0.76rem;
	}

	.dashboard-sync-popover-row + .dashboard-sync-popover-row {
		margin-top: 0.55rem;
		padding-top: 0.55rem;
		border-top: 1px solid var(--dashboard-border);
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

	.dashboard-quick-search-modal {
		padding-top: 1.1rem;
	}

	.dashboard-quick-search-results {
		display: grid;
		gap: 0.6rem;
		max-height: min(60vh, 32rem);
		overflow-y: auto;
		padding-right: 0.15rem;
	}

	.dashboard-quick-search-item {
		display: grid;
		gap: 0.45rem;
		width: 100%;
		border: 1px solid var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.55);
		background: color-mix(in oklab, var(--dashboard-panel) 88%, transparent);
		padding: 0.8rem 0.9rem;
		text-align: left;
		transition: background-color 160ms ease, border-color 160ms ease, transform 160ms ease;
		cursor: pointer;
	}

	.dashboard-quick-search-item:hover {
		background: var(--dashboard-hover-bg);
		border-color: color-mix(in oklab, var(--dashboard-accent) 22%, transparent);
		transform: translateY(-1px);
	}

	.dashboard-quick-search-main {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.8rem;
	}

	.dashboard-quick-search-empty {
		display: grid;
		place-items: center;
		gap: 0.35rem;
		min-height: 10rem;
		border: 1px dashed var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.65);
		background: color-mix(in oklab, var(--dashboard-panel) 72%, transparent);
		padding: 1rem;
		text-align: center;
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

	.dashboard-input {
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

	.dashboard-textarea {
		min-height: 10rem;
		resize: vertical;
		font-family: "JetBrains Mono", monospace;
		line-height: 1.6;
	}

	.dashboard-input:focus {
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
		padding: 0.1rem 0 0.3rem 0.2rem;
	}

	.block-drop-indicator {
		position: absolute;
		left: 0.45rem;
		right: 0.85rem;
		z-index: 26;
		height: 2px;
		border-radius: 999px;
		background: var(--dashboard-accent);
		box-shadow: 0 0 0 1px color-mix(in oklab, var(--dashboard-panel) 82%, transparent);
		pointer-events: none;
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

	.dashboard-mobile-toolbar-root {
		position: fixed;
		right: 0;
		bottom: 0;
		left: 0;
		z-index: 36;
		pointer-events: none;
	}

	.dashboard-mobile-toolbar-root::before {
		content: '';
		position: absolute;
		right: 0;
		bottom: calc(100% - 1px);
		left: 0;
		height: 1.5rem;
		background: linear-gradient(180deg, transparent, color-mix(in oklab, var(--dashboard-bg) 78%, transparent));
		pointer-events: none;
	}

	.dashboard-mobile-toolbar-sheet {
		pointer-events: auto;
		position: absolute;
		right: 0;
		bottom: 0;
		left: 0;
		display: none;
		flex-direction: column;
		border-top: 1px solid var(--dashboard-border);
		border-radius: 1.25rem 1.25rem 0 0;
		background:
			linear-gradient(
				180deg,
				color-mix(in oklab, var(--dashboard-panel) 96%, white 4%),
				color-mix(in oklab, var(--dashboard-panel) 93%, var(--dashboard-bg))
			);
		box-shadow: 0 -18px 48px var(--dashboard-shadow-color);
		backdrop-filter: blur(22px) saturate(1.06);
		touch-action: none;
		will-change: transform;
	}

	.dashboard-mobile-toolbar-sheet.is-expanded {
		max-height: min(68dvh, 34rem);
	}

	.dashboard-mobile-toolbar-sheet-handle-wrap {
		display: flex;
		justify-content: center;
		padding: 0.45rem 0.8rem 0.15rem;
	}

	.dashboard-mobile-toolbar-sheet-handle {
		pointer-events: auto;
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		border: none;
		background: transparent;
		padding: 0.1rem 0.35rem;
		color: var(--dashboard-fg);
		cursor: pointer;
	}

	.dashboard-mobile-toolbar-sheet-grabber {
		display: inline-flex;
		width: 2.6rem;
		height: 0.34rem;
		border-radius: 999px;
		background: color-mix(in oklab, var(--dashboard-fg) 18%, transparent);
	}

	.dashboard-mobile-toolbar-bar {
		display: flex;
		min-width: 0;
		align-items: center;
		gap: 0.35rem;
		padding: 0.45rem 0.8rem 0.65rem;
		overflow-x: auto;
		scrollbar-width: none;
	}

	.dashboard-mobile-toolbar-bar::-webkit-scrollbar {
		display: none;
	}

	.dashboard-mobile-toolbar-arrow {
		transition: transform 160ms ease;
	}

	.dashboard-mobile-toolbar-arrow.is-open {
		transform: rotate(180deg);
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

	.editor-toolbar-overlay.is-mobile {
		left: auto;
		display: none;
		max-width: 100%;
		max-height: min(48dvh, 24rem);
		margin-top: 0;
		padding:
			0.15rem
			0.8rem
			calc(env(safe-area-inset-bottom, 0px) + 0.8rem)
			0.8rem;
		transform: none;
		border: none;
		border-top: 1px solid color-mix(in oklab, var(--dashboard-fg) 8%, transparent);
		border-radius: 0;
		background: transparent;
		box-shadow: none;
		overflow-y: auto;
	}

	.editor-toolbar-overlay.is-mobile.is-expanded {
		display: flex;
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
		padding-bottom: 0.85rem;
		margin-bottom: -0.85rem;
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
		cursor: grab;
	}

	.handle-drag:active {
		cursor: grabbing;
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

	:global(.mention-command-menu) {
		position: fixed;
		z-index: 120;
		width: min(22rem, calc(100vw - 2rem));
		border: 1px solid color-mix(in oklab, var(--dashboard-accent) 16%, var(--dashboard-border));
		border-radius: calc(var(--dashboard-radius) * 0.78);
		background:
			linear-gradient(
				180deg,
				color-mix(in oklab, var(--dashboard-panel) 98%, white 2%),
				color-mix(in oklab, var(--dashboard-panel) 93%, var(--dashboard-bg))
			);
		padding: 0.55rem;
		box-shadow:
			0 28px 56px color-mix(in oklab, var(--dashboard-shadow-color) 90%, transparent),
			inset 0 1px 0 color-mix(in oklab, white 16%, transparent);
		backdrop-filter: blur(20px) saturate(1.1);
	}

	:global(.mention-menu-header) {
		padding: 0.35rem 0.45rem 0.55rem;
	}

	:global(.mention-menu-kicker) {
		color: var(--dashboard-fg);
		font-size: 0.8rem;
		font-weight: 900;
		letter-spacing: 0.02em;
	}

	:global(.mention-menu-subtitle) {
		margin-top: 0.18rem;
		color: var(--dashboard-soft-fg);
		font-size: 0.68rem;
		line-height: 1.35;
	}

	:global(.mention-command-menu .mention-command-item) {
		align-items: center;
		gap: 0.75rem;
		border: 1px solid transparent;
		border-radius: calc(var(--dashboard-radius) * 0.55);
		padding: 0.72rem 0.78rem;
		transition:
			transform 160ms ease,
			background-color 160ms ease,
			border-color 160ms ease,
			box-shadow 160ms ease;
	}

	:global(.mention-command-menu .mention-command-item:hover) {
		transform: translateY(-1px);
		border-color: color-mix(in oklab, var(--dashboard-accent) 16%, transparent);
		box-shadow: inset 0 1px 0 color-mix(in oklab, white 8%, transparent);
	}

	:global(.mention-command-main) {
		display: inline-flex;
		min-width: 0;
		flex: 1;
		align-items: center;
		gap: 0.72rem;
	}

	:global(.mention-command-emoji) {
		display: inline-flex;
		height: 2rem;
		width: 2rem;
		flex-shrink: 0;
		align-items: center;
		justify-content: center;
		border-radius: 0.8rem;
		background: color-mix(in oklab, var(--dashboard-accent) 12%, transparent);
		font-size: 1rem;
		box-shadow: inset 0 1px 0 color-mix(in oklab, white 16%, transparent);
	}

	:global(.mention-command-copy) {
		display: flex;
		min-width: 0;
		flex: 1;
		flex-direction: column;
	}

	:global(.mention-command-title) {
		color: var(--dashboard-fg);
		font-size: 0.82rem;
		font-weight: 800;
		line-height: 1.2;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	:global(.mention-command-meta) {
		margin-top: 0.14rem;
		color: var(--dashboard-soft-fg);
		font-size: 0.67rem;
		line-height: 1.25;
	}

	:global(.mention-command-shortcut) {
		display: inline-flex;
		height: 1.45rem;
		min-width: 1.45rem;
		align-items: center;
		justify-content: center;
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 8%, transparent);
		border-radius: 999px;
		background: color-mix(in oklab, var(--dashboard-fg) 4%, transparent);
		color: var(--dashboard-soft-fg);
		font-size: 0.68rem;
		font-weight: 900;
	}

	:global(.mention-command-menu .command-item.is-selected),
	:global(.mention-command-menu .mention-command-item.is-selected) {
		background:
			linear-gradient(
				180deg,
				color-mix(in oklab, var(--dashboard-accent) 16%, var(--dashboard-panel)),
				color-mix(in oklab, var(--dashboard-accent) 10%, var(--dashboard-panel))
			);
		border-color: color-mix(in oklab, var(--dashboard-accent) 28%, transparent);
		box-shadow:
			0 14px 28px color-mix(in oklab, var(--dashboard-shadow-color) 45%, transparent),
			inset 0 1px 0 color-mix(in oklab, white 12%, transparent);
	}

	:global(.doc-mention) {
		display: inline-flex;
		align-items: center;
		gap: 0.36rem;
		border: 1px solid color-mix(in oklab, var(--dashboard-accent) 18%, transparent);
		border-radius: 999px;
		background:
			linear-gradient(
				180deg,
				color-mix(in oklab, var(--dashboard-accent) 18%, transparent),
				color-mix(in oklab, var(--dashboard-accent) 10%, transparent)
			);
		padding: 0.14rem 0.56rem 0.14rem 0.46rem;
		color: color-mix(in oklab, var(--dashboard-accent) 48%, var(--dashboard-fg));
		text-decoration: none;
		font-weight: 800;
		line-height: 1.2;
		box-shadow:
			inset 0 1px 0 color-mix(in oklab, white 12%, transparent),
			0 4px 10px color-mix(in oklab, var(--dashboard-shadow-color) 22%, transparent);
	}

	:global(.doc-mention::before) {
		content: '@';
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1rem;
		height: 1rem;
		border-radius: 999px;
		background: color-mix(in oklab, var(--dashboard-accent) 22%, transparent);
		color: color-mix(in oklab, var(--dashboard-accent) 60%, var(--dashboard-fg));
		font-size: 0.68rem;
		font-weight: 900;
		line-height: 1;
	}

	:global(.doc-mention:hover) {
		transform: translateY(-1px);
		background:
			linear-gradient(
				180deg,
				color-mix(in oklab, var(--dashboard-accent) 24%, transparent),
				color-mix(in oklab, var(--dashboard-accent) 14%, transparent)
			);
		border-color: color-mix(in oklab, var(--dashboard-accent) 30%, transparent);
		box-shadow:
			inset 0 1px 0 color-mix(in oklab, white 12%, transparent),
			0 10px 18px color-mix(in oklab, var(--dashboard-shadow-color) 24%, transparent);
	}

	:global(.tiptap ul[data-type='taskList']) {
		list-style: none;
		margin-left: 0;
		padding-left: 0.35rem;
	}

	:global(.tiptap ul[data-type='taskList'] li) {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		min-height: 1.9rem;
	}

	:global(.tiptap ul[data-type='taskList'] li > label) {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		margin-top: 0;
		flex-shrink: 0;
	}

	:global(.tiptap ul[data-type='taskList'] li > div) {
		flex: 1;
		display: flex;
		align-items: center;
		min-height: 1.9rem;
	}

	:global(.tiptap ul[data-type='taskList'] li > div > p) {
		margin: 0;
		line-height: 1.6;
	}

	:global(.tiptap ul[data-type='taskList'] input[type='checkbox']) {
		appearance: none;
		width: 1.05rem;
		height: 1.05rem;
		margin: 0;
		border: 1px solid color-mix(in oklab, var(--dashboard-accent) 28%, var(--dashboard-border));
		border-radius: 0.35rem;
		background: color-mix(in oklab, var(--dashboard-panel) 96%, transparent);
		box-shadow: inset 0 1px 0 color-mix(in oklab, white 12%, transparent);
		cursor: pointer;
		position: relative;
		flex-shrink: 0;
		align-self: center;
		transition:
			background-color 160ms ease,
			border-color 160ms ease,
			box-shadow 160ms ease,
			transform 160ms ease;
	}

	:global(.tiptap ul[data-type='taskList'] input[type='checkbox']:hover) {
		transform: translateY(-1px);
		border-color: color-mix(in oklab, var(--dashboard-accent) 44%, transparent);
		box-shadow:
			inset 0 1px 0 color-mix(in oklab, white 16%, transparent),
			0 6px 12px color-mix(in oklab, var(--dashboard-shadow-color) 18%, transparent);
	}

	:global(.tiptap ul[data-type='taskList'] input[type='checkbox']:checked) {
		border-color: color-mix(in oklab, var(--dashboard-accent) 68%, transparent);
		background: color-mix(in oklab, var(--dashboard-accent) 68%, var(--dashboard-panel));
	}

	:global(.tiptap ul[data-type='taskList'] input[type='checkbox']:checked::after) {
		content: '';
		position: absolute;
		left: 0.31rem;
		top: 0.12rem;
		width: 0.26rem;
		height: 0.5rem;
		border-right: 2px solid white;
		border-bottom: 2px solid white;
		transform: rotate(45deg);
	}

	:global(.tiptap ul[data-type='taskList'] li[data-checked='true'] > div) {
		opacity: 0.72;
		text-decoration: line-through;
		text-decoration-thickness: 1.5px;
	}

	:global(.tiptap .tableWrapper) {
		/*margin: 1.25rem 0;*/
		overflow-x: auto;
		/*border: 1px solid var(--dashboard-border);*/
		/*border-radius: calc(var(--dashboard-radius) * 0.65);*/
		/*background: color-mix(in oklab, var(--dashboard-panel) 92%, transparent);*/
		/*box-shadow: inset 0 1px 0 color-mix(in oklab, white 10%, transparent);*/
	}

	:global(.tiptap table) {
		width: 100%;
		border-collapse: collapse;
		min-width: 100%;
		table-layout: fixed;
		overflow: hidden;
		border-radius: inherit;
	}

	:global(.tiptap th),
	:global(.tiptap td) {
		border: 1px solid var(--dashboard-border);
		padding: 0.42rem 0.6rem;
		min-height: 2.2rem;
		vertical-align: top;
		text-align: left;
		background: color-mix(in oklab, var(--dashboard-panel) 96%, transparent);
	}

	:global(.tiptap th) {
		background: color-mix(in oklab, var(--dashboard-accent) 10%, var(--dashboard-panel));
		font-weight: 800;
	}

	:global(.tiptap th p),
	:global(.tiptap td p) {
		margin: 0;
		min-height: 1.2em;
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

	.doc-menu-backdrop {
		position: fixed;
		inset: 0;
		z-index: 58;
		background: transparent;
	}

	.doc-menu {
		position: absolute;
		right: 0;
		top: calc(100% + 0.2rem);
		z-index: 60;
		display: flex;
		width: 12rem;
		max-width: 12rem;
		flex-direction: column;
		gap: 0.2rem;
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 10%, transparent);
		border-radius: calc(var(--dashboard-radius) * 0.6);
		background:
			linear-gradient(
				180deg,
				color-mix(in oklab, var(--dashboard-panel) 96%, white 4%),
				color-mix(in oklab, var(--dashboard-panel) 92%, var(--dashboard-bg))
			);
		padding: 0.45rem;
		box-shadow:
			0 24px 60px color-mix(in oklab, var(--dashboard-shadow-color) 90%, transparent),
			inset 0 1px 0 color-mix(in oklab, white 20%, transparent);
		backdrop-filter: blur(22px) saturate(1.2);
		transform-origin: top right;
		overflow: hidden;
	}

	.doc-menu-floating {
		position: fixed;
	}

	.doc-menu-headerline {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.15rem 0.3rem 0.45rem;
	}

	.doc-menu-kicker {
		font-size: 0.66rem;
		font-weight: 900;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--dashboard-soft-fg);
	}

	.doc-menu-caption {
		font-size: 0.7rem;
		color: color-mix(in oklab, var(--dashboard-fg) 38%, transparent);
	}

	.doc-menu-item {
		display: flex;
		width: 100%;
		align-items: center;
		gap: 0.6rem;
		border: 1px solid transparent;
		border-radius: calc(var(--dashboard-radius) * 0.42);
		background: transparent;
		padding: 0.55rem 0.6rem;
		text-align: left;
		cursor: pointer;
		transition:
			transform 180ms ease,
			background-color 180ms ease,
			border-color 180ms ease,
			box-shadow 180ms ease;
	}

	.doc-menu-item:hover {
		transform: translateX(2px);
		background: color-mix(in oklab, var(--dashboard-hover-bg) 82%, var(--dashboard-panel));
		border-color: color-mix(in oklab, var(--dashboard-accent) 18%, transparent);
		box-shadow: inset 0 1px 0 color-mix(in oklab, white 10%, transparent);
	}

	.doc-menu-icon {
		display: inline-flex;
		height: 1.7rem;
		width: 1.7rem;
		flex-shrink: 0;
		align-items: center;
		justify-content: center;
		border-radius: 0.7rem;
		background: color-mix(in oklab, var(--dashboard-fg) 6%, transparent);
		color: var(--dashboard-fg);
		font-size: 0.82rem;
		font-weight: 800;
	}

	.doc-menu-copy {
		display: flex;
		min-width: 0;
		flex: 1;
		flex-direction: column;
	}

	.doc-menu-title {
		font-size: 0.8rem;
		font-weight: 800;
		line-height: 1.1;
		color: var(--dashboard-fg);
	}

	.doc-menu-desc {
		margin-top: 0.12rem;
		font-size: 0.68rem;
		line-height: 1.2;
		color: var(--dashboard-soft-fg);
	}

	.doc-menu-divider {
		margin: 0.15rem 0.25rem;
		height: 1px;
		background: color-mix(in oklab, var(--dashboard-fg) 8%, transparent);
	}

	.doc-menu-item.is-danger .doc-menu-icon {
		background: color-mix(in oklab, oklch(0.62 0.24 24) 18%, transparent);
		color: color-mix(in oklab, oklch(0.62 0.24 24) 78%, var(--dashboard-fg));
	}

	.doc-menu-item.is-danger .doc-menu-title {
		color: color-mix(in oklab, oklch(0.62 0.24 24) 82%, var(--dashboard-fg));
	}

	.doc-menu-item.is-danger:hover {
		background: color-mix(in oklab, oklch(0.62 0.24 24) 10%, var(--dashboard-panel));
		border-color: color-mix(in oklab, oklch(0.62 0.24 24) 26%, transparent);
	}

	.dashboard-folder-header {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.dashboard-folder-group {
		display: grid;
		gap: 0.18rem;
	}

	.dashboard-folder-row {
		display: flex;
		align-items: center;
		min-height: 1.9rem;
		padding-left: 0.15rem;
	}

	.dashboard-folder-label {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		min-width: 0;
		width: 100%;
		padding: 0.2rem 0.45rem;
		border-radius: calc(var(--dashboard-radius) * 0.35);
		background: transparent;
		border: 1px solid transparent;
		color: var(--dashboard-soft-fg);
		font-size: 0.73rem;
		font-weight: 700;
		text-align: left;
		cursor: pointer;
	}

	.dashboard-folder-label:hover {
		background: var(--dashboard-hover-bg);
		border-color: var(--dashboard-border);
	}

	.dashboard-folder-children {
		display: grid;
		gap: 0.18rem;
		padding-left: 1rem;
		border-left: 1px dashed color-mix(in oklab, var(--dashboard-fg) 10%, transparent);
		margin-left: 0.7rem;
	}

	.space-context-menu {
		width: min(18rem, calc(100vw - 1.5rem));
	}

	.sidebar-drop-indicator {
		position: fixed;
		z-index: 48;
		height: 2px;
		border-radius: 999px;
		background: var(--dashboard-accent);
		box-shadow: 0 0 0 1px color-mix(in oklab, var(--dashboard-panel) 82%, transparent);
		pointer-events: none;
	}

	.folder-collapsed {
		transform: rotate(0deg);
		transition: transform 160ms ease;
	}

	.dashboard-folder-add-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.35rem;
		height: 1.35rem;
		border-radius: 999px;
		border: 1px solid transparent;
		background: transparent;
		color: var(--dashboard-soft-fg);
		font-size: 0.9rem;
		font-weight: 700;
		cursor: pointer;
		transition: all 160ms ease;
	}

	.dashboard-folder-add-btn:hover {
		background: var(--dashboard-hover-bg);
		border-color: var(--dashboard-border);
		color: var(--dashboard-fg);
	}

	.dashboard-space-pill {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 999px;
		padding: 0.1rem 0.4rem;
		font-size: 0.62rem;
		font-weight: 800;
		letter-spacing: 0.02em;
		color: var(--dashboard-soft-fg);
		background: var(--dashboard-soft-bg);
		border: 1px solid var(--dashboard-border);
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
		-webkit-appearance: none;
		appearance: none;
		width: 100%;
		height: 1.35rem;
		border: none;
		outline: none;
		background: transparent;
		padding: 0;
		cursor: pointer;
		touch-action: pan-x;
		position: relative;
		z-index: 1;
	}

	.theme-range:focus-visible {
		outline: 2px solid color-mix(in oklab, var(--dashboard-accent) 42%, transparent);
		outline-offset: 0.2rem;
		border-radius: 999px;
	}

	.theme-range::-webkit-slider-runnable-track {
		height: 0.95rem;
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 12%, transparent);
		border-radius: 999px;
		background:
			linear-gradient(
				90deg,
				color-mix(in oklab, var(--dashboard-bg) 92%, black 8%),
				color-mix(in oklab, var(--dashboard-panel) 72%, var(--dashboard-accent)),
				color-mix(in oklab, white 84%, var(--dashboard-accent))
			);
		box-shadow:
			inset 0 1px 2px color-mix(in oklab, black 10%, transparent),
			0 1px 0 color-mix(in oklab, white 10%, transparent);
	}

	.theme-range::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		margin-top: -0.08rem;
		width: 1.2rem;
		height: 1.2rem;
		border-radius: 999px;
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 14%, transparent);
		background:
			radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.18) 42%, rgba(255, 255, 255, 0) 43%),
			color-mix(in oklab, var(--dashboard-panel) 92%, white 8%);
		box-shadow:
			0 4px 12px color-mix(in oklab, var(--dashboard-shadow-color) 55%, transparent),
			0 1px 0 rgba(255, 255, 255, 0.35);
	}

	.theme-range::-moz-range-track {
		height: 0.95rem;
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 12%, transparent);
		border-radius: 999px;
		background:
			linear-gradient(
				90deg,
				color-mix(in oklab, var(--dashboard-bg) 92%, black 8%),
				color-mix(in oklab, var(--dashboard-panel) 72%, var(--dashboard-accent)),
				color-mix(in oklab, white 84%, var(--dashboard-accent))
			);
		box-shadow:
			inset 0 1px 2px color-mix(in oklab, black 10%, transparent),
			0 1px 0 color-mix(in oklab, white 10%, transparent);
	}

	.theme-range::-moz-range-thumb {
		width: 1.2rem;
		height: 1.2rem;
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 14%, transparent);
		border-radius: 999px;
		background:
			radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.18) 42%, rgba(255, 255, 255, 0) 43%),
			color-mix(in oklab, var(--dashboard-panel) 92%, white 8%);
		box-shadow:
			0 4px 12px color-mix(in oklab, var(--dashboard-shadow-color) 55%, transparent),
			0 1px 0 rgba(255, 255, 255, 0.35);
	}

	.lightness-range::-webkit-slider-runnable-track {
		background: linear-gradient(90deg, oklch(0.18 0 0), oklch(1 0 0));
	}

	.lightness-range::-moz-range-track {
		background: linear-gradient(90deg, oklch(0.18 0 0), oklch(1 0 0));
	}

	.chroma-range::-webkit-slider-runnable-track {
		background: linear-gradient(
			90deg,
			oklch(0.72 0 25),
			oklch(0.72 0.08 25),
			oklch(0.72 0.16 25),
			oklch(0.72 0.24 25),
			oklch(0.72 0.32 25)
		);
	}

	.chroma-range::-moz-range-track {
		background: linear-gradient(
			90deg,
			oklch(0.72 0 25),
			oklch(0.72 0.08 25),
			oklch(0.72 0.16 25),
			oklch(0.72 0.24 25),
			oklch(0.72 0.32 25)
		);
	}

	.hue-range::-webkit-slider-runnable-track {
		background: linear-gradient(
			90deg,
			oklch(0.72 0.22 20),
			oklch(0.72 0.22 60),
			oklch(0.72 0.22 120),
			oklch(0.72 0.22 180),
			oklch(0.72 0.22 240),
			oklch(0.72 0.22 300),
			oklch(0.72 0.22 360)
		);
	}

	.hue-range::-moz-range-track {
		background: linear-gradient(
			90deg,
			oklch(0.72 0.22 20),
			oklch(0.72 0.22 60),
			oklch(0.72 0.22 120),
			oklch(0.72 0.22 180),
			oklch(0.72 0.22 240),
			oklch(0.72 0.22 300),
			oklch(0.72 0.22 360)
		);
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

	@media (max-width: 900px) {
		.dashboard-shell {
			position: relative;
		}

		.dashboard-sidebar-mobile {
			position: fixed;
			inset: 0 auto 0 0;
			width: min(22rem, calc(100vw - 2.25rem));
			max-width: calc(100vw - 2.25rem);
			height: 100dvh;
			transform: translateX(-108%);
			transition: transform 220ms ease;
			z-index: 45;
			box-shadow: 0 24px 72px var(--dashboard-shadow-color);
		}

		.dashboard-sidebar-mobile.is-open {
			transform: translateX(0);
		}

		.dashboard-main {
			min-width: 0;
		}

		.dashboard-topbar {
			height: auto;
			padding: 0.8rem 0.9rem;
			gap: 0.8rem;
		}

		.dashboard-cover {
			height: 8rem;
		}

		.dashboard-main > :global(div.mx-auto.w-full.max-w-4xl) {
			transform: none;
			padding-top: 1rem;
			padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 8.75rem);
		}

		.dashboard-page-title {
			font-size: clamp(2rem, 8vw, 2.8rem) !important;
		}

		.dashboard-emoji-trigger {
			height: 4.2rem;
			width: 4.2rem;
			font-size: 2.9rem;
		}

		.editor-shell {
			padding: 0;
		}

		.dashboard-mobile-toolbar-sheet {
			display: flex;
		}

		.dashboard-mobile-toolbar-bar .dashboard-toolbar-btn {
			min-width: 2.2rem;
			min-height: 2rem;
			padding: 0.35rem 0.5rem;
			flex-shrink: 0;
		}

		.dashboard-mobile-toolbar-sheet .editor-toolbar-overlay.is-mobile {
			display: none;
		}

		.dashboard-mobile-toolbar-sheet.is-expanded .editor-toolbar-overlay.is-mobile {
			display: flex;
		}

		.markdown-split-view {
			grid-template-columns: minmax(0, 1fr);
			gap: 1rem;
			min-height: 0;
			padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 9rem);
		}

		.markdown-preview {
			padding-left: 0;
			padding-top: 0.5rem;
		}

		.dashboard-empty-state,
		.dashboard-main > :global(div.mx-auto.flex.h-full.max-w-3xl) {
			padding:
				2rem
				1.2rem
				calc(env(safe-area-inset-bottom, 0px) + 8.25rem);
		}

		.dashboard-modal-backdrop {
			align-items: flex-end;
			padding: 0;
		}

		.dashboard-modal-box {
			width: 100%;
			max-height: min(88dvh, 88dvh);
			border-right: none;
			border-bottom: none;
			border-left: none;
			border-radius: 1.35rem 1.35rem 0 0;
			padding:
				1rem
				1rem
				calc(env(safe-area-inset-bottom, 0px) + 1rem)
				1rem;
		}

		.dashboard-modal-actions {
			flex-wrap: wrap;
			justify-content: stretch;
		}

		.dashboard-modal-actions :global(.dashboard-btn) {
			flex: 1 1 10rem;
		}

		.doc-menu-backdrop {
			background: color-mix(in oklab, black 32%, transparent);
			backdrop-filter: blur(10px);
		}

		.doc-menu,
		.doc-menu.doc-menu-floating,
		.space-context-menu {
			position: fixed;
			top: auto !important;
			right: 0.75rem;
			bottom: calc(env(safe-area-inset-bottom, 0px) + 0.75rem);
			left: 0.75rem !important;
			width: auto !important;
			max-width: none;
			border-radius: 1.2rem;
			padding: 0.55rem;
		}

		.page-settings-fab {
			display: none;
		}
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
