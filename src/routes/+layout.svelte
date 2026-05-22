<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import NavBar from '$lib/components/NavBar.svelte';
	import { onMount } from 'svelte';
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
	<!-- 顶部留出导航栏高度 -->
	<NavBar />
	
	<div class="flex-1 mt-12.5 flex flex-col">
		{@render children()}
	</div>

	<ToastContainer />
</main>
