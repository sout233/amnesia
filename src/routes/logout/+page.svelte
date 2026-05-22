<script lang="ts">
	import { goto } from '$app/navigation';
	import LoadingSvg from '$lib/components/LoadingSvg.svelte';
	import { onMount } from 'svelte';
	import { toast } from '$lib/toastQueue.svelte';
	import { userState } from '$lib/userData.svelte';

	async function handleLogout() {
		try {
			// 延迟一小会儿提供更好视觉交互反馈
			await new Promise((resolve) => setTimeout(resolve, 600));

			userState.setSession(null);
			toast.info('已安全登出');
			goto('/login');
		} catch (error: any) {
			console.error('登出失败:', error.message);
			toast.error('登出遇到问题，请重试');
		}
	}

	onMount(() => {
		handleLogout();
	});
</script>

<div class="noto flex h-[90vh] w-screen flex-col items-center justify-center relative select-none">
	<div class="z-10 text-center">
		<h1 class="text-4xl font-extrabold tracking-tight text-black">正在登出</h1>
		<p class="text-black/50 text-sm mt-3 font-mono">正在安全断开连接，请稍候...</p>
	</div>
	
	<LoadingSvg className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 scale-150 z-0 opacity-40" strokeColor="#000000" />
</div>
