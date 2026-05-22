<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import NavBar from '$lib/components/NavBar.svelte';
	import { onMount } from 'svelte';
	import { supabase } from '$lib/supabaseClient';
	import { userState } from '$lib/userData.svelte';
	import ToastContainer from '$lib/components/ToastContainer.svelte';
	import { toast } from '$lib/toastQueue.svelte';
	import { random } from 'animejs';

	let { children } = $props();

	onMount(() => {
		// 初始化读取 Session
		supabase.auth.getSession().then(({ data }) => {
			userState.setSession(data.session);
		});

		// 监听 Auth 状态变动
		const {
			data: { subscription }
		} = supabase.auth.onAuthStateChange((event, session) => {
			userState.setSession(session);

			if (event === 'SIGNED_OUT') {
				toast.info('⚡ 记忆云端已断开连接');
			} else if (event === 'SIGNED_IN') {
				let randomNum = random(1, 4);

				if (randomNum === 1) {
					toast.success('🧠 记忆突触已同步成功');
				} else if (randomNum === 2) {
					toast.success('✨ 欢迎回到 Amnesia 神经中枢');
				} else if (randomNum === 3) {
					toast.info('📡 正在加载您的个人文档时空...');
				} else {
					toast.wtf('🚀 欢迎访问您的第二大脑！');
				}
			}
		});

		return () => {
			subscription.unsubscribe();
		};
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<main class="min-h-screen flex flex-col bg-white text-black">
	<!-- 顶部留出导航栏高度 -->
	<NavBar />
	
	<div class="flex-1 mt-12.5 flex flex-col">
		{@render children()}
	</div>

	<ToastContainer />
</main>
