<script lang="ts">
	import { animate } from 'animejs';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { toast } from '$lib/toastQueue.svelte';
	import { registerWithInvite } from '$lib/auth/authService';
	import { userState } from '$lib/userData.svelte';
	import { deriveDocEncryptionKey } from '$lib/crypto/appCrypto';

	let panel = $state<HTMLElement | null>(null);
	let username = $state('');
	let password = $state('');
	let inviteCode = $state('');
	let loading = $state(false);

	async function handleRegister(e: Event) {
		e.preventDefault();
		if (!username || !password || !inviteCode) {
			toast.warning('请完整填写用户名、密码与邀请码');
			return;
		}
		loading = true;
		const result = await registerWithInvite({ username, password, inviteCode });
		loading = false;
		if (!result.success) {
			toast.error(result.message);
			return;
		}
		toast.success(result.message);
		if (result.user) {
			userState.setSession({
				user: {
					id: result.user.id,
					username: result.user.username,
					role: result.user.systemRole,
					encryptionReady: result.user.encryptionReady,
					encryptionNoticeAccepted: result.user.encryptionNoticeAccepted,
					docEncryptionKey: await deriveDocEncryptionKey(password),
					avatarSeed: result.user.avatarSeed ?? result.user.username,
					avatarUrl: result.user.avatarUrl ?? null
				}
			});
		}
		goto('/dashboard', { replaceState: true });
	}

	onMount(() => {
		if (userState.session) {
			goto('/dashboard', { replaceState: true });
			return;
		}
		if (panel) {
			animate(panel, {
				translateY: [60, 0],
				opacity: [0, 1],
				duration: 900,
				ease: 'outExpo'
			});
		}
	});
</script>

<svelte:head>
	<title>注册 - Amnesia</title>
</svelte:head>

<div class="relative min-h-[92vh] flex items-center justify-center px-4 overflow-hidden">
	<div class="grid-bg-white absolute inset-0 z-0 pointer-events-none"></div>
	<div bind:this={panel} class="z-10 bg-white border border-black/10 rounded-3xl shadow-2xl p-8 max-w-md w-full opacity-0">
		<h1 class="text-3xl font-extrabold tracking-tight text-black text-center mb-6">注册</h1>
		<form onsubmit={handleRegister} class="space-y-4">
			<input bind:value={username} class="w-full bg-neutral-50 border border-black/10 text-sm rounded-xl px-4 py-3 outline-none focus:border-black focus:bg-white transition-all" placeholder="用户名" />
			<input bind:value={password} type="password" class="w-full bg-neutral-50 border border-black/10 text-sm rounded-xl px-4 py-3 outline-none focus:border-black focus:bg-white transition-all" placeholder="密码" />
			<input bind:value={inviteCode} class="w-full bg-neutral-50 border border-black/10 text-sm rounded-xl px-4 py-3 outline-none focus:border-black focus:bg-white transition-all" placeholder="邀请码" />
			<button type="submit" disabled={loading} class="w-full btn btn-neutral rounded-xl font-bold py-3 mt-2 shadow-md cursor-pointer disabled:opacity-50">
				{#if loading}注册中...{:else}注册{/if}
			</button>
			<a href="/login" class="block text-center text-xs text-black/55 font-semibold pt-2">已有账号？前往登录</a>
		</form>
	</div>
</div>
