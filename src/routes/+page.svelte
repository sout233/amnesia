<script lang="ts">
	import AniButton from '$lib/components/AniButton.svelte';
	import { userState } from '$lib/userData.svelte';
	import { onMount } from 'svelte';
	import { animate, stagger } from 'animejs';
	import { getBrowserInfo } from '$lib/utils/broswerCheck';
	import { toast } from '$lib/toastQueue.svelte';

	let entryButtonIcon = `
    <svg
		xmlns="http://www.w3.org/2000/svg"
		width="24"
		height="24"
		viewBox="0 0 24 24"
		class="translate-y-[0.5px] scale-80 mr-2"
		><path
			fill="currentColor"
			d="M13 21q-.425 0-.712-.288T12 20t.288-.712T13 19h6V5h-6q-.425 0-.712-.288T12 4t.288-.712T13 3h6q.825 0 1.413.588T21 5v14q0 .825-.587 1.413T19 21zm-1.825-8H4q-.425 0-.712-.288T3 12t.288-.712T4 11h7.175L9.3 9.125q-.275-.275-.275-.675t.275-.7t.7-.313t.725.288L14.3 11.3q.3.3.3.7t-.3.7l-3.575 3.575q-.3.3-.712.288T9.3 16.25q-.275-.3-.262-.712t.287-.688z"
		/></svg
	>
    `;

	let heroTitleNode = $state<HTMLElement | null>(null);
	let subtitleNode = $state<HTMLElement | null>(null);
	let cardContainerNode = $state<HTMLElement | null>(null);

	onMount(() => {
		const info = getBrowserInfo();

		if (info.isMobile) {
			toast.info('📱 已为您优化移动端显示与手势交互');
		}

		// 页面首屏动画
		if (heroTitleNode) {
			animate(heroTitleNode, {
				opacity: [0, 1],
				translateY: [40, 0],
				duration: 1200,
				ease: 'outExpo'
			});
		}

		if (subtitleNode) {
			animate(subtitleNode, {
				opacity: [0, 1],
				translateY: [30, 0],
				duration: 1200,
				delay: 200,
				ease: 'outExpo'
			});
		}

		if (cardContainerNode) {
			const cards = cardContainerNode.querySelectorAll('.feature-card');
			animate(cards, {
				opacity: [0, 1],
				translateY: [50, 0],
				delay: stagger(150, { start: 400 }),
				duration: 1000,
				ease: 'outElastic(1, 0.7)'
			});
		}
	});

	// 卡片悬停三维倾斜特效
	function handleCardMouseMove(e: MouseEvent, card: HTMLDivElement) {
		const rect = card.getBoundingClientRect();
		const x = e.clientX - rect.left;
		const y = e.clientY - rect.top;
		const xc = rect.width / 2;
		const yc = rect.height / 2;
		const angleX = (yc - y) / 10;
		const angleY = (x - xc) / 10;

		card.style.transform = `perspective(1000px) rotateX(${angleX}deg) rotateY(${angleY}deg) scale3d(1.05, 1.05, 1.05)`;
		card.style.boxShadow = `${-angleY * 2}px ${angleX * 2}px 30px rgba(0, 0, 0, 0.15)`;
	}

	function handleCardMouseLeave(card: HTMLDivElement) {
		card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)';
		card.style.boxShadow = '0 10px 20px rgba(0, 0, 0, 0.05)';
	}
</script>

<svelte:head>
	<title>Amnesia - 唤醒你的第二大脑</title>
</svelte:head>

<div class="relative min-h-[92vh] flex flex-col justify-between items-center px-4 overflow-hidden select-none">
	<!-- 极致柔和的动态网格背景 -->
	<div class="grid-bg-white absolute inset-0 z-0 pointer-events-none"></div>

	<div class="flex-1 flex flex-col justify-center items-center max-w-6xl w-full z-10 py-16">
		<div class="text-center space-y-6">
			<h1
				bind:this={heroTitleNode}
				class="text-6xl md:text-8xl font-extrabold tracking-tight text-black opacity-0 leading-none select-none"
			>
				AMNESIA
			</h1>

			<p
				bind:this={subtitleNode}
				class="text-xl md:text-2xl text-black/60 font-medium max-w-2xl mx-auto opacity-0 select-none noto leading-relaxed"
			>
			我要干啥来着。
			</p>
		</div>
	</div>

	<div class="pb-12 z-20">
		{#if !userState.session}
			<AniButton
				text="登录"
				href="/login"
				className="btn btn-neutral btn-lg rounded-full font-bold px-8 shadow-xl flex items-center gap-2 cursor-pointer"
			>
				{#snippet icon()}
					{@html entryButtonIcon}
				{/snippet}
			</AniButton>
		{:else}
			<AniButton
				text="进入您的神经工作区"
				href="/dashboard"
				className="btn btn-neutral btn-lg rounded-full font-bold px-8 shadow-xl flex items-center gap-2 cursor-pointer"
			>
				{#snippet icon()}
					<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" class="translate-y-[0.5px] scale-80 mr-2"><path fill="currentColor" d="M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83l1.41 1.41L19 6.41V10h2V3h-7z"/></svg>
				{/snippet}
			</AniButton>
		{/if}
	</div>
</div>

<style>
	.feature-card {
		transform-style: preserve-3d;
		backface-visibility: hidden;
		transition: transform 0.1s ease, box-shadow 0.2s ease;
	}
</style>
