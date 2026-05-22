<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import NavBar from '$lib/components/NavBar.svelte';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { userState } from '$lib/userData.svelte';
	import ToastContainer from '$lib/components/ToastContainer.svelte';

	let { children } = $props();

	onMount(() => {
		// 初始化读取本地 Session
		userState.loadFromLocalStorage();
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<main class="min-h-screen flex flex-col bg-white text-black">
	{#if !page.url.pathname.startsWith('/dashboard')}
		<NavBar />
	{/if}

	<div class="flex-1 flex flex-col {page.url.pathname.startsWith('/dashboard') ? '' : 'mt-12.5'}">
		{@render children()}
	</div>

	<ToastContainer />
</main>
