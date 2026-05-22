<script lang="ts">
	import { userState } from '$lib/userData.svelte';
	import { toast } from '$lib/toastQueue.svelte';
	import { onMount } from 'svelte';
	import { animate } from 'animejs';
	import { goto } from '$app/navigation';
	import { getUsers, addUser, deleteUser, type UserRecord } from '$lib/userDatabase';

	let sidebarNode = $state<HTMLElement | null>(null);
	let mainContentNode = $state<HTMLElement | null>(null);

	// 当前选中的模拟文档
	let activeDocIndex = $state(0);

	// 树形文档树列表
	const mockDocs = [
		{ emoji: '🎨', title: '团队视觉与动效风格指南', category: '团队工作区' },
		{ emoji: '📝', title: 'Amnesia 核心架构与同步方案', category: '团队工作区' },
		{ emoji: '🚀', title: '本地数据持久化扩展规范', category: '个人笔记' },
		{ emoji: '📅', title: '2026 开发迭代时间表', category: '个人笔记' }
	];

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

	onMount(async () => {
		// 路由保护：如果未登录，自动去登录页
		userState.loadFromLocalStorage();
		if (!userState.session) {
			goto('/login');
			return;
		}

		// 首屏骨架滑入动画
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

	function handleDocClick(index: number, docTitle: string) {
		activeDocIndex = index;
		toast.info(`正在打开: ${docTitle}`);
	}
</script>

<svelte:head>
	<title>工作台 - Amnesia</title>
</svelte:head>

<div class="flex h-[92vh] w-screen overflow-hidden bg-[#fafafa] text-black/80 text-sm font-sans select-none">
	
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
						{#each mockDocs.filter(d => d.category === '团队工作区') as doc, i}
							{@const index = mockDocs.findIndex(d => d.title === doc.title)}
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
						{#each mockDocs.filter(d => d.category === '个人笔记') as doc, i}
							{@const index = mockDocs.findIndex(d => d.title === doc.title)}
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
		class="flex-1 h-full overflow-y-auto flex flex-col items-center bg-white opacity-0"
	>
		
		<!-- 顶部面包屑与在线协作组 -->
		<div class="w-full h-11 border-b border-black/5 px-6 flex items-center justify-between shrink-0 bg-white/80 backdrop-blur-sm sticky top-0 z-20">
			<div class="flex items-center gap-1.5 text-xs text-black/50 font-medium">
				<span>工作台</span>
				<span>/</span>
				<span>{mockDocs[activeDocIndex].category}</span>
				<span>/</span>
				<span class="text-black font-semibold flex items-center gap-1">
					<span>{mockDocs[activeDocIndex].emoji}</span>
					<span>{mockDocs[activeDocIndex].title}</span>
				</span>
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

		<!-- 文档核心画布 -->
		<div class="max-w-3xl w-full px-12 pb-24 relative mt-[-2.5rem]">
			
			<!-- 超大 Emoji -->
			<div class="text-6xl mb-6 relative z-10 w-20 h-20 rounded-2xl bg-white border border-black/5 shadow-md flex items-center justify-center cursor-pointer hover:scale-105 transition-transform duration-200">
				{mockDocs[activeDocIndex].emoji}
			</div>

			<!-- 交互式超大标题 -->
			<h1 class="text-4xl font-extrabold text-black tracking-tight mb-8 outline-none" contenteditable="true" spellcheck="false">
				{mockDocs[activeDocIndex].title}
			</h1>

			<!-- 编辑内容区 -->
			<div class="space-y-6 text-[15px] leading-relaxed text-black/80 font-normal">
				
				<!-- 精致的 Notion Callout -->
				<div class="bg-neutral-50 border border-black/5 rounded-2xl p-5 flex gap-3.5 relative overflow-hidden group">
					<div class="absolute top-0 left-0 w-1.5 h-full bg-black"></div>
					<div class="text-2xl select-none">📢</div>
					<div>
						<h4 class="font-bold text-xs text-black/40 font-mono tracking-wider mb-1 uppercase">公告板 / BULLETIN</h4>
						<p class="text-[13px] text-black/70 leading-relaxed font-medium noto">
							您目前处于 **Amnesia 工作台** 占位阶段。在未来的版本里，这里将提供块级富文本编辑器，并支持实时文档共享。
						</p>
					</div>
				</div>

				<!-- 普通段落 Block -->
				<p class="noto">
					**Amnesia** 是一款知识管理工具，旨在帮助您记录个人思考片段和团队知识库。
				</p>

				<!-- 模拟多人实时编辑 -->
				<div class="relative bg-neutral-50/50 border border-black/5 rounded-2xl p-6 space-y-3">
					<div class="flex items-center justify-between border-b border-black/5 pb-2">
						<span class="text-[10px] text-black/40 font-mono tracking-wider font-bold">实时同步测试区</span>
						<span class="badge badge-sm badge-success text-[10px] font-bold text-white">实时同步中</span>
					</div>

					<p class="relative inline-block leading-relaxed noto select-all text-black/90">
						Amnesia 支持实时多人协同编辑。当其他协作者对块进行编辑时，
						<span class="relative bg-pink-100/60 px-1 rounded inline-block text-black">
							Alice 正在高亮此段文字进行复核
							<!-- Alice 协作光标 -->
							<span class="absolute top-0 right-[-1px] w-0.5 h-full bg-pink-500 animate-pulse"></span>
							<span class="absolute top-[-16px] right-[-20px] bg-pink-500 text-white text-[8px] font-bold px-1 rounded-sm leading-none py-0.5 select-none shadow-sm pointer-events-none font-mono">Alice</span>
						</span>
						。这种无缝交互能够让团队高效沟通，确保思想能保持绝对的
						<span class="relative border-b-2 border-blue-400 inline-block">
							同步状态
							<!-- Bob 协作光标 -->
							<span class="absolute top-0 right-[-1px] w-0.5 h-full bg-blue-500 animate-pulse"></span>
							<span class="absolute bottom-[-16px] right-[-12px] bg-blue-500 text-white text-[8px] font-bold px-1 rounded-sm leading-none py-0.5 select-none shadow-sm pointer-events-none font-mono">Bob</span>
						</span>。
					</p>
				</div>

				<!-- 任务列表 Block -->
				<div class="space-y-2">
					<h3 class="text-sm font-bold text-black/40 font-mono tracking-wider uppercase mb-1">开发计划清单</h3>
					<div class="flex items-center gap-2.5">
						<input type="checkbox" checked class="checkbox checkbox-xs rounded-md" disabled />
						<span class="line-through text-black/40 text-xs">构建 Amnesia 视觉规范与动画系统</span>
					</div>
					<div class="flex items-center gap-2.5">
						<input type="checkbox" checked class="checkbox checkbox-xs rounded-md" disabled />
						<span class="line-through text-black/40 text-xs">通过本地/云端认证机制保障数据安全</span>
					</div>
					<div class="flex items-center gap-2.5">
						<input type="checkbox" class="checkbox checkbox-xs rounded-md" disabled />
						<span class="text-xs font-semibold">实现块级富文本协作编辑器开发</span>
					</div>
				</div>

				<!-- 代码块 Block -->
				<div class="space-y-1">
					<div class="flex items-center justify-between text-[10px] text-black/40 font-mono tracking-wider px-2 uppercase">
						<span>AmnesiaCore.ts</span>
						<span>typescript</span>
					</div>
					<pre class="bg-neutral-900 text-neutral-200 rounded-xl p-5 overflow-x-auto text-xs font-mono select-text shadow-inner"><code><span class="text-pink-400">import</span> &#123; <span class="text-yellow-300">syncData</span> &#125; <span class="text-pink-400">from</span> <span class="text-green-300">'$lib/sync'</span>;
317: 
318: <span class="text-gray-400">// 触发同步</span>
319: <span class="text-pink-400">export</span> <span class="text-blue-400">async</span> <span class="text-blue-400">function</span> <span class="text-yellow-300">triggerAmnesiaSync</span>(blockId: <span class="text-blue-300">string</span>) &#123;
320:   <span class="text-pink-400">const</span> response = <span class="text-pink-400">await</span> <span class="text-yellow-300">syncData</span>(blockId);
321:   <span class="text-pink-400">if</span> (response.status === <span class="text-green-300">'success'</span>) &#123;
322:     console.<span class="text-yellow-300">log</span>(<span class="text-green-300">'数据同步成功。'</span>);
323:   &#125;
324: &#125;</code></pre>
				</div>

			</div>
		</div>

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
</style>
