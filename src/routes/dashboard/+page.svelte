<script lang="ts">
	import { userState } from '$lib/userData.svelte';
	import { toast } from '$lib/toastQueue.svelte';
	import { onMount } from 'svelte';
	import { animate, stagger } from 'animejs';

	let sidebarNode = $state<HTMLElement | null>(null);
	let mainContentNode = $state<HTMLElement | null>(null);

	// 当前选中的模拟文档
	let activeDocIndex = $state(0);

	// 树形文档树列表
	const mockDocs = [
		{ emoji: '🎨', title: '团队视觉与动效风格指南', category: '团队工作区' },
		{ emoji: '📝', title: 'Amnesia 核心架构与同步方案', category: '团队工作区' },
		{ emoji: '🚀', title: 'Supabase 神经存储扩展规范', category: '个人笔记' },
		{ emoji: '📅', title: '2026 开发迭代时间表', category: '个人笔记' }
	];

	// 树形折叠状态
	let teamWorkspaceOpen = $state(true);
	let personalNotesOpen = $state(true);

	onMount(() => {
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

		toast.success('🧠 工作台神经突触装载完毕');
	});

	function handleDocClick(index: number, docTitle: string) {
		activeDocIndex = index;
		toast.info(`📡 正在调取记忆块: ${docTitle}`);
	}
</script>

<svelte:head>
	<title>神经工作台 - Amnesia</title>
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
						{userState.session?.user?.user_metadata?.display_name || userState.session?.user?.email || '游客大脑'}
					</p>
					<p class="text-[9px] text-black/40 font-mono tracking-wider mt-0.5 uppercase">
						{userState.session ? '神经连结中' : '游客暂存态'}
					</p>
				</div>
			</div>

			<!-- 快速导航区 -->
			<div class="space-y-0.5">
				<button 
					type="button"
					onclick={() => toast.info('🔍 检索神经突触服务正在筹备中...')}
					class="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-black/5 rounded-lg text-left text-xs font-medium text-black/70 cursor-pointer"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="opacity-60"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0-14 0m18 11l-6-6"/></svg>
					快速检索
				</button>
				<button 
					type="button"
					onclick={() => toast.info('⚙️ 核心设置仍在镌刻...')}
					class="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-black/5 rounded-lg text-left text-xs font-medium text-black/70 cursor-pointer"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="opacity-60"><g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"><path d="M12 14a2 2 0 1 0 0-4a2 2 0 0 0 0 4"/><path d="M14.2 17.95a8.95 8.95 0 0 0 1.95-1.95m.1-5.1a8.95 8.95 0 0 0-1.95-1.95m-5.1-.1A8.95 8.95 0 0 0 7.25 11m-.1 5.1A8.95 8.95 0 0 0 9.1 18.05m6-1.1l2.3 2.3m-8.3-2.3l-2.3 2.3m8.3-8.3l2.3-2.3m-8.3 8.3l-2.3-2.3m2.3-6l-2.3-2.3"/></g></svg>
					设置与成员
				</button>
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
					<span>🧠 个人记忆流</span>
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
				断开神经中枢 (登出)
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
				<span>神经网络主枢</span>
				<span>/</span>
				<span>{mockDocs[activeDocIndex].category}</span>
				<span>/</span>
				<span class="text-black font-semibold flex items-center gap-1">
					<span>{mockDocs[activeDocIndex].emoji}</span>
					<span>{mockDocs[activeDocIndex].title}</span>
				</span>
			</div>

			<!-- 极高保真的“团队协作在线用户”头像堆叠 -->
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
					<span class="text-[10px] text-black/40 font-mono font-bold ml-2">2 人在线协同</span>
				</div>

				<div class="h-4 w-px bg-black/10"></div>
				<button 
					type="button" 
					class="btn btn-xs btn-neutral rounded-full font-bold px-3 cursor-pointer"
					onclick={() => toast.success('🔗 已生成协同突触共享链接！已复制到剪贴板。')}
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
				<button type="button" class="btn btn-xs bg-white/15 text-white border-none hover:bg-white/30 rounded-md font-bold cursor-pointer">🎨 更改记忆外壳</button>
				<button type="button" class="btn btn-xs bg-white/15 text-white border-none hover:bg-white/30 rounded-md font-bold cursor-pointer">📍 重新对齐</button>
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

			<!-- 编辑内容区（高保真占位） -->
			<div class="space-y-6 text-[15px] leading-relaxed text-black/80 font-normal">
				
				<!-- 精致的 Notion Callout -->
				<div class="bg-neutral-50 border border-black/5 rounded-2xl p-5 flex gap-3.5 relative overflow-hidden group">
					<div class="absolute top-0 left-0 w-1.5 h-full bg-black"></div>
					<div class="text-2xl select-none">🧠</div>
					<div>
						<h4 class="font-bold text-xs text-black/40 font-mono tracking-wider mb-1 uppercase">协作中枢公告板 / BULLETIN</h4>
						<p class="text-[13px] text-black/70 leading-relaxed font-medium noto">
							您此刻身处 **Amnesia 神经中枢工作台** 骨架占位中。在未来的版本里，这里将呈现极致顺滑的块级富文本编辑器（Block Editor），支持实时文档共享以及脑图共振。
						</p>
					</div>
				</div>

				<!-- 普通段落 Block -->
				<p class="noto">
					在数字化遗忘速度快于创造速度的今天，**Amnesia** 被设计为对抗遗忘的终极工具。无论是您转瞬即逝的个人思考片段，还是团队之间复杂的多维知识数据库，都在此获得永久性的印刻。
				</p>

				<!-- 模拟多人实时编辑的高保真协作光标 -->
				<div class="relative bg-neutral-50/50 border border-black/5 rounded-2xl p-6 space-y-3">
					<div class="flex items-center justify-between border-b border-black/5 pb-2">
						<span class="text-[10px] text-black/40 font-mono tracking-wider font-bold">🧠 神经电波同步测试区 (模拟实时文档)</span>
						<span class="badge badge-sm badge-success text-[10px] font-bold text-white">实时同步中</span>
					</div>

					<p class="relative inline-block leading-relaxed noto select-all text-black/90">
						Amnesia 采用了最前沿的神经网络多维同步模型。在此区域内，当其他协作者对块进行编辑时，
						<span class="relative bg-pink-100/60 px-1 rounded inline-block text-black">
							Alice 正在高亮此段文字进行复核
							<!-- Alice 协作光标 -->
							<span class="absolute top-0 right-[-1px] w-0.5 h-full bg-pink-500 animate-pulse"></span>
							<span class="absolute top-[-16px] right-[-20px] bg-pink-500 text-white text-[8px] font-bold px-1 rounded-sm leading-none py-0.5 select-none shadow-sm pointer-events-none font-mono">Alice</span>
						</span>
						。这种无缝的交互，确保了团队在跨物理维度进行脑力风暴时，思想能保持绝对的
						<span class="relative border-b-2 border-blue-400 inline-block">
							共鸣状态
							<!-- Bob 协作光标 -->
							<span class="absolute top-0 right-[-1px] w-0.5 h-full bg-blue-500 animate-pulse"></span>
							<span class="absolute bottom-[-16px] right-[-12px] bg-blue-500 text-white text-[8px] font-bold px-1 rounded-sm leading-none py-0.5 select-none shadow-sm pointer-events-none font-mono">Bob</span>
						</span>。
					</p>
				</div>

				<!-- 任务列表 Block -->
				<div class="space-y-2">
					<h3 class="text-sm font-bold text-black/40 font-mono tracking-wider uppercase mb-1">开发计划清单 / MILESTONES</h3>
					<div class="flex items-center gap-2.5">
						<input type="checkbox" checked class="checkbox checkbox-xs rounded-md" disabled />
						<span class="line-through text-black/40 text-xs">构建 Amnesia 极致视觉规范与动画系统</span>
					</div>
					<div class="flex items-center gap-2.5">
						<input type="checkbox" checked class="checkbox checkbox-xs rounded-md" disabled />
						<span class="line-through text-black/40 text-xs">通过 Supabase 打造安全的记忆通道 (OAuth + 密码)</span>
					</div>
					<div class="flex items-center gap-2.5">
						<input type="checkbox" class="checkbox checkbox-xs rounded-md" disabled />
						<span class="text-xs font-semibold">实现块级富文本协作编辑器开发</span>
					</div>
				</div>

				<!-- 代码块 Block -->
				<div class="space-y-1">
					<div class="flex items-center justify-between text-[10px] text-black/40 font-mono tracking-wider px-2 uppercase">
						<span>AmnesiaNeuralCore.ts</span>
						<span>typescript</span>
					</div>
					<pre class="bg-neutral-900 text-neutral-200 rounded-xl p-5 overflow-x-auto text-xs font-mono select-text shadow-inner"><code><span class="text-pink-400">import</span> &#123; <span class="text-yellow-300">syncSynapse</span> &#125; <span class="text-pink-400">from</span> <span class="text-green-300">'$lib/synapse'</span>;

<span class="text-gray-400">// 触发神经网络记忆同步</span>
<span class="text-pink-400">export</span> <span class="text-blue-400">async</span> <span class="text-blue-400">function</span> <span class="text-yellow-300">triggerAmnesiaSync</span>(blockId: <span class="text-blue-300">string</span>) &#123;
  <span class="text-pink-400">const</span> response = <span class="text-pink-400">await</span> <span class="text-yellow-300">syncSynapse</span>(blockId);
  <span class="text-pink-400">if</span> (response.status === <span class="text-green-300">'resonant'</span>) &#123;
    console.<span class="text-yellow-300">log</span>(<span class="text-green-300">'🧠 思维突触瞬间共鸣，记忆已牢固。'</span>);
  &#125;
&#125;</code></pre>
				</div>

			</div>
		</div>

	</div>

</div>

<style>
	/* 隐藏浏览器原装选区，让协作光标显得更加纯粹 */
	::selection {
		background: rgba(0, 0, 0, 0.08);
	}
</style>
