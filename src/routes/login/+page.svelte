<script lang="ts">
	import { animate } from 'animejs';
	import { onMount } from 'svelte';
	import { toast } from '$lib/toastQueue.svelte';
	import { goto } from '$app/navigation';
	import { userState } from '$lib/userData.svelte';
	import { verifyUser } from '$lib/userDatabase';

	let loginPanel = $state<HTMLElement | null>(null);
	let backButton = $state<HTMLElement | null>(null);

	let username = $state('');
	let password = $state('');
	let loading = $state(false);

	function handleBackButtonEnter() {
		if (backButton) {
			animate(backButton, {
				scale: 1.2,
				duration: 600,
				rotate: -5,
				ease: 'outElastic'
			});
		}
	}

	function handleBackButtonLeave() {
		if (backButton) {
			animate(backButton, {
				scale: 1,
				duration: 1000,
				rotate: 0,
				ease: 'outElastic'
			});
		}
	}

	// 密码登录
	const handlePasswordAuth = async (e: Event) => {
		e.preventDefault();
		if (!username || !password) {
			toast.warning('请输入用户名和密码');
			return;
		}

		try {
			loading = true;
			// 延迟一小会儿提供更好视觉交互反馈
			await new Promise((resolve) => setTimeout(resolve, 600));

			// 匹配云端 Supabase 数据库用户
			let matched = await verifyUser(username, password);
			// 硬编码默认管理员 sout 兜底匹配以防因网络或初始化问题无法登录
			if (!matched && username === 'sout' && password === 'Wgc123456.') {
				matched = { username: 'sout', role: 'root' };
			}

			if (matched) {
				userState.setSession({
					user: {
						username: matched.username,
						role: matched.role
					}
				});
				toast.success('登录成功！已加载工作台');
				goto('/dashboard');
			} else {
				toast.error('用户名或密码错误', 4000);
			}
		} catch (error: any) {
			toast.error('登录失败: ' + error.message, 4000);
		} finally {
			loading = false;
		}
	};

	onMount(() => {
		if (loginPanel) {
			animate(loginPanel, {
				translateY: [80, 0],
				opacity: [0, 1],
				duration: 1000,
				ease: 'outElastic(1, 0.75)'
			});
		}

		// 若已登录则自动前往 Dashboard
		if (userState.session) {
			goto('/dashboard');
		}
	});
</script>

<svelte:head>
	<title>登录 - Amnesia</title>
</svelte:head>

<div class="relative min-h-[92vh] flex flex-col justify-center items-center px-4 overflow-hidden select-none">
	<div class="grid-bg-white absolute inset-0 z-0 pointer-events-none"></div>

	<!-- 登录卡片容器 -->
	<div
		bind:this={loginPanel}
		class="z-10 bg-white border border-black/10 rounded-3xl shadow-2xl p-8 max-w-md w-full transition-all duration-300 opacity-0 select-none"
	>
		<div class="text-center mb-8">
			<h2 class="text-3xl font-extrabold tracking-tight text-black leading-none">
				登录
			</h2>
		</div>

		<form onsubmit={handlePasswordAuth} class="space-y-4">
			<div class="space-y-1">
				<label for="username" class="text-xs font-bold text-black/50 tracking-wider">用户名 / USERNAME</label>
				<input
					id="username"
					type="text"
					placeholder="输入您的用户名"
					bind:value={username}
					disabled={loading}
					required
					class="w-full bg-neutral-50 border border-black/10 text-sm rounded-xl px-4 py-3 outline-none focus:border-black focus:bg-white transition-all"
				/>
			</div>

			<div class="space-y-1">
				<div class="flex justify-between items-center">
					<label for="password" class="text-xs font-bold text-black/50 tracking-wider">密码 / SECURITY CODE</label>
				</div>
				<input
					id="password"
					type="password"
					placeholder="••••••••"
					bind:value={password}
					disabled={loading}
					required
					class="w-full bg-neutral-50 border border-black/10 text-sm rounded-xl px-4 py-3 outline-none focus:border-black focus:bg-white transition-all"
				/>
			</div>

			<!-- 提交按钮 -->
			<button
				type="submit"
				disabled={loading}
				class="w-full btn btn-neutral rounded-xl font-bold py-3 mt-2 shadow-md cursor-pointer disabled:opacity-50"
			>
				{#if loading}
					<span class="loading loading-spinner scale-75"></span>
					正在登录...
				{:else}
					登录
				{/if}
			</button>
		</form>
	</div>

	<!-- 固定右下角返回大按钮 -->
	<a
		bind:this={backButton}
		href="/"
		class="btn fixed right-4 bottom-4 btn-neutral rounded-full px-6 shadow-xl flex items-center gap-2 cursor-pointer font-bold"
		onpointerenter={handleBackButtonEnter}
		onpointerleave={handleBackButtonLeave}
	>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			width="12"
			height="24"
			viewBox="0 0 12 24"
			class="translate-y-[0.5px] scale-80 fill-current"
		>
			<path fill-rule="evenodd" d="m3.343 12l7.071 7.071L9 20.485l-7.778-7.778a1 1 0 0 1 0-1.414L9 3.515l1.414 1.414z"/>
		</svg>
		返回首页
	</a>
</div>
