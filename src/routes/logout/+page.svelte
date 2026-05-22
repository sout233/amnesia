<script lang="ts">
	import { supabase } from '$lib/supabaseClient';
	import { goto } from '$app/navigation';
	import LoadingSvg from '$lib/components/LoadingSvg.svelte';
	import { onMount } from 'svelte';
	import { toast } from '$lib/toastQueue.svelte';
	import { userState } from '$lib/userData.svelte';

	async function handleLogout() {
		try {
			const { error } = await supabase.auth.signOut();
			if (error) throw error;

			userState.setSession(null);
			goto('/login');
		} catch (error: any) {
			console.error('登出失败:', error.message);
			toast.error('释放神经连接遇到问题，请重试');
		}
	}

	onMount(() => {
		handleLogout();
	});
</script>

<div class="noto flex h-[90vh] w-screen flex-col items-center justify-center relative select-none">
	<div class="z-10 text-center">
		<h1 class="text-4xl font-extrabold tracking-tight text-black">释放神经键</h1>
		<p class="text-black/50 text-sm mt-3 font-mono">正在安全断开您的思维中枢...</p>
	</div>
	
	<LoadingSvg className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 scale-150 z-0 opacity-40" strokeColor="#000000" />
</div>
