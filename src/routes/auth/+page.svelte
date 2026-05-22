<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { userState } from '$lib/userData.svelte';
	import LoadingSvg from '$lib/components/LoadingSvg.svelte';

	onMount(() => {
		userState.loadFromLocalStorage();
		if (userState.session) {
			goto('/dashboard', { replaceState: true });
		} else {
			goto('/login');
		}
	});
</script>

<div class="noto flex h-[90vh] w-screen flex-col items-center justify-center relative select-none">
	<div class="z-10 text-center">
		<h1 class="text-4xl font-extrabold tracking-tight text-black">身份验证中</h1>
		<p class="text-black/50 text-sm mt-3 font-mono">正在验证登录凭证，请稍候...</p>
	</div>
	
	<LoadingSvg className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 scale-150 z-0 opacity-40" strokeColor="#000000" />
</div>
