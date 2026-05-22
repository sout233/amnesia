<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { supabase } from '$lib/supabaseClient';
	import LoadingSvg from '$lib/components/LoadingSvg.svelte';

	onMount(() => {
		const {
			data: { subscription }
		} = supabase.auth.onAuthStateChange((event, session) => {
			if (event === 'SIGNED_IN' || event === 'INITIAL_SESSION') {
				if (session) {
					goto('/dashboard', { replaceState: true });
				}
			} else if (event === 'SIGNED_OUT') {
				goto('/login');
			}
		});

		supabase.auth.getSession().then(({ data: { session } }) => {
			if (session) {
				goto('/dashboard', { replaceState: true });
			}
		});

		return () => {
			subscription.unsubscribe();
		};
	});
</script>

<div class="noto flex h-[90vh] w-screen flex-col items-center justify-center relative select-none">
	<div class="z-10 text-center">
		<h1 class="text-4xl font-extrabold tracking-tight text-black">突触突变中</h1>
		<p class="text-black/50 text-sm mt-3 font-mono">正在连接到 Amnesia 神经网络，请稍候...</p>
	</div>
	
	<!-- 极致变形加载动画 -->
	<LoadingSvg className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 scale-150 z-0 opacity-40" strokeColor="#000000" />
</div>
