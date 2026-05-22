<script lang="ts">
	import { supabase } from '$lib/supabaseClient';
	import { animate } from 'animejs';
	import { onMount } from 'svelte';
	import { toast } from '$lib/toastQueue.svelte';
	import { goto } from '$app/navigation';
	import { userState } from '$lib/userData.svelte';

	let loginPanel = $state<HTMLElement | null>(null);
	let backButton = $state<HTMLElement | null>(null);

	// 当前是在登录(signin)还是注册(signup)模式
	let isRegisterMode = $state(false);

	let email = $state('');
	let password = $state('');
	let username = $state(''); // 注册时可选输入

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
		if (!email || !password) {
			toast.warning('请输入完整的邮箱和密码');
			return;
		}

		try {
			loading = true;
			if (isRegisterMode) {
				// 注册
				const { data, error } = await supabase.auth.signUp({
					email,
					password,
					options: {
						data: {
							display_name: username || email.split('@')[0],
						}
					}
				});
				if (error) throw error;

				if (data.user && data.session === null) {
					toast.success('📨 镌刻成功！请查看您的邮箱进行二次确认。', 5000);
				} else if (data.session) {
					userState.setSession(data.session);
					toast.success('🧠 镌刻成功！已自动加载记忆工作台');
					goto('/dashboard');
				}
			} else {
				// 登录
				const { data, error } = await supabase.auth.signInWithPassword({
					email,
					password
				});
				if (error) throw error;

				if (data.session) {
					userState.setSession(data.session);
					toast.success('✨ 记忆已唤醒，欢迎回来！');
					goto('/dashboard');
				}
			}
		} catch (error: any) {
			toast.error('验证失败: ' + error.message, 4000);
		} finally {
			loading = false;
		}
	};

	// GitHub OAuth 登录
	const handleGithubLogin = async () => {
		try {
			loading = true;
			const { error } = await supabase.auth.signInWithOAuth({
				provider: 'github',
				options: {
					redirectTo: `${window.location.origin}/auth`
				}
			});
			if (error) throw error;
		} catch (error: any) {
			loading = false;
			toast.error('GitHub 认证失败: ' + error.message, 4000);
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
	<title>{isRegisterMode ? '镌刻新大脑 - Amnesia' : '唤醒第二大脑 - Amnesia'}</title>
</svelte:head>

<div class="relative min-h-[92vh] flex flex-col justify-center items-center px-4 overflow-hidden select-none">
	<div class="grid-bg-white absolute inset-0 z-0 pointer-events-none"></div>

	<!-- 登录/注册 卡片容器 -->
	<div
		bind:this={loginPanel}
		class="z-10 bg-white border border-black/10 rounded-3xl shadow-2xl p-8 max-w-md w-full transition-all duration-300 opacity-0 select-none"
	>
		<div class="text-center mb-8">
			<h2 class="text-3xl font-extrabold tracking-tight text-black leading-none">
				{isRegisterMode ? 'ENGRAVE' : '登录'}
			</h2>
		</div>


		<form onsubmit={handlePasswordAuth} class="space-y-4">
			{#if isRegisterMode}
				<div class="space-y-1">
					<label for="username" class="text-xs font-bold text-black/50 tracking-wider">用户名 / USERNAME</label>
					<input
						id="username"
						type="text"
						placeholder="用户名或邮箱"
						bind:value={username}
						disabled={loading}
						class="w-full bg-neutral-50 border border-black/10 text-sm rounded-xl px-4 py-3 outline-none focus:border-black focus:bg-white transition-all"
					/>
				</div>
			{/if}

			<div class="space-y-1">
				<label for="email" class="text-xs font-bold text-black/50 tracking-wider">邮箱 / EMAIL ADDRESS</label>
				<input
					id="email"
					type="email"
					placeholder="your.mind@example.com"
					bind:value={email}
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
					正在构建神经元连接...
				{:else if isRegisterMode}
					镌刻思维突触 (注册)
				{:else}
				登录
				{/if}
			</button>
		</form>

		<div class="relative flex items-center justify-center my-6">
			<div class="absolute w-full border-t border-black/5"></div>
		</div>

		<button
			disabled={true}
			class="w-full btn btn-outline border-black/10 hover:bg-black hover:text-white rounded-xl py-3 flex items-center justify-center gap-2 cursor-pointer font-bold disabled:opacity-50"
			onclick={handleGithubLogin}
		>
			<svg
				aria-label="GitHub logo"
				width="18"
				height="18"
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 24 24"
				class="fill-current"
			>
				<path d="M12,2A10,10 0 0,0 2,12C2,16.42 4.87,20.17 8.84,21.5C9.34,21.58 9.5,21.27 9.5,21C9.5,20.77 9.5,20.14 9.5,19.31C6.73,19.91 6.14,17.97 6.14,17.97C5.68,16.81 5.03,16.5 5.03,16.5C4.12,15.88 5.1,15.9 5.1,15.9C6.1,15.97 6.63,16.93 6.63,16.93C7.5,18.45 8.97,18 9.54,17.76C9.63,17.11 9.89,16.67 10.17,16.42C7.95,16.17 5.62,15.31 5.62,11.5C5.62,10.39 6,9.5 6.65,8.79C6.55,8.54 6.2,7.5 6.75,6.15C6.75,6.15 7.59,5.88 9.5,7.17C10.29,6.95 11.15,6.84 12,6.84C12.85,6.84 13.71,6.95 14.5,7.17C16.41,5.88 17.25,6.15 17.25,6.15C17.8,7.5 17.45,8.54 17.35,8.79C18,9.5 18.38,10.39 18.38,11.5C18.38,15.32 16.04,16.16 13.81,16.41C14.17,16.72 14.5,17.33 14.5,18.26C14.5,19.6 14.5,20.68 14.5,21C14.5,21.27 14.66,21.59 15.17,21.5C19.14,20.16 22,16.42 22,12A10,10 0 0,0 12,2Z"/>
			</svg>
			使用 GitHub 登录
		</button>
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
		返回地球主页
	</a>
</div>
