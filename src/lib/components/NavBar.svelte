<script lang="ts">
	import { onMount } from 'svelte';
	import { animate, splitText, stagger, spring, utils, svg } from 'animejs';
	import { isBrowserSupportSuperAnimation } from '$lib/utils/broswerCheck';
	import { userState } from '$lib/userData.svelte';

	let titleNode = $state<HTMLElement | null>(null);
	let titleSplit = $state<any>(null);
	let containerNode = $state<HTMLElement | null>(null);

	let link1Node = $state<HTMLElement | null>(null);
	let link2Node = $state<HTMLElement | null>(null);

	let svgPath1 = $state<SVGPolygonElement | null>(null);
	let svgPath2 = $state<SVGPolygonElement | null>(null);

	let isBrowserSupported = $state(true);
	let isMobileViewport = $state(false);

	function syncViewportState() {
		if (typeof window === 'undefined') return;
		isMobileViewport = window.innerWidth < 768;
	}

	const initAnime = () => {
		if (containerNode) {
			animate(containerNode, {
				opacity: [0, 1],
				x: [{ from: '-20rem', ease: 'outBounce', duration: 1145 }],
				duration: 1000
			});
		}

		if (titleSplit) titleSplit.revert();

		if (titleNode) {
			titleSplit = splitText(titleNode, {
				words: { wrap: 'clip' },
				chars: true,
				debug: false
			});

			if (titleSplit && titleSplit.words) {
				animate(titleSplit.words, {
					y: [{ to: ['100%', '0%'] }, { to: '-100%', delay: 1145, ease: 'in(3)' }],
					duration: 1145,
					ease: 'out(3)',
					delay: stagger(100),
					loop: true
				});
			}
		}

		const targets = [link1Node, link2Node].filter(Boolean) as HTMLElement[];
		if (targets.length > 0) {
			animate(targets, {
				opacity: [0, 1],
				duration: 100,
				delay: stagger(100, { start: 1000 })
			});

			animate(targets, {
				fontSize: [{ from: '2rem', to: '1rem' }],
				duration: 100,
				delay: stagger(100, { start: 1200 }),
				ease: spring({
					bounce: 0.15,
					duration: 300
				})
			});
		}

		animate('.motion-svg', {
			rotate: [0, 180],
			duration: 5000,
			loop: true,
			ease: 'linear'
		});
	};

	onMount(() => {
		isBrowserSupported = isBrowserSupportSuperAnimation();
		syncViewportState();
		window.addEventListener('resize', syncViewportState);

		initAnime();

		function animateRandomPoints() {
			if (!svgPath1 || !svgPath2) return;

			utils.set(svgPath2, { points: generatePoints() });

			animate(svgPath1, {
				points: svg.morphTo(svgPath2),
				ease: 'inOutCirc',
				duration: 500,
				onComplete: animateRandomPoints
			});
		}

		animateRandomPoints();

		return () => {
			window.removeEventListener('resize', syncViewportState);
		};
	});

	const handleMouseEnter = () => {
		if (!isBrowserSupported || !containerNode || !titleNode) return;

		animate(containerNode, {
			height: '50vh',
			duration: 400,
			ease: 'outExpo'
		});

		animate(titleNode, {
			scale: 1.1,
			x: '8vw',
			y: '25vh',
			color: 'black',
			backgroundColor: 'var(--color-base-200)',
			duration: 400,
			ease: 'outExpo'
		});

		if (titleSplit && titleSplit.words && titleSplit.words[0]) {
			// @ts-ignore
			if (titleNode.children[1]) {
				// @ts-ignore
				titleNode.children[1].style.overflow = 'visible';
			}

			animate(titleSplit.words[0], {
				translateY: '-6vh',
				translateX: '4vw',
				scale: 1.4,
				color: 'var(--color-base-200)',
				duration: 400,
				ease: 'outExpo'
			});

			if (titleSplit.words[1]) {
				animate(titleSplit.words[1], {
					y: [{ to: ['100%', '0%'] }, { to: '-100%', delay: 500, ease: 'in(3)' }],
					duration: 500,
					ease: 'out(3)',
					delay: stagger(100),
					loop: true
				});
			}

			animate(titleSplit.words[0], {
				rotate: ['-2deg', '2deg'],
				delay: stagger(100),
				ease: 'out(3)',
				loop: true,
				reversed: true,
				alternate: true
			});
		}

		if (link1Node) {
			animate(link1Node, {
				y: '21vh',
				duration: 400,
				ease: 'outExpo',
				scale: 2
			});
		}

		if (link2Node) {
			animate(link2Node, {
				y: '24vh',
				x: '-5vw',
				duration: 400,
				ease: 'outExpo',
				scale: 2
			});
		}
	};

	const handleMouseLeave = () => {
		if (!isBrowserSupported || !containerNode || !titleNode) return;

		animate(containerNode, {
			height: '3.125rem',
			duration: 600,
			ease: 'outElastic(1, .6)'
		});

		animate(titleNode, {
			scale: 1,
			x: '0vw',
			y: '0',
			color: 'var(--color-base-200)',
			backgroundColor: 'black',
			duration: 600,
			ease: 'outElastic(1, .6)'
		});

		if (titleSplit && titleSplit.words && titleSplit.words[0]) {
			// @ts-ignore
			if (titleNode.children[1]) {
				// @ts-ignore
				titleNode.children[1].style.overflow = 'clip';
			}

			animate(titleSplit.words[0], {
				translateY: '0vh',
				translateX: '0vw',
				scale: 1,
				duration: 400,
				ease: 'outExpo'
			});

			animate(titleSplit.words, {
				y: [{ to: ['100%', '0%'] }, { to: '-100%', delay: 1145, ease: 'in(3)' }],
				duration: 1145,
				ease: 'out(3)',
				delay: stagger(100),
				loop: true
			});

			animate(titleSplit.words[0], {
				rotate: 0
			});
		}

		if (link1Node) {
			animate(link1Node, {
				y: '0vh',
				duration: 400,
				ease: 'outExpo',
				scale: 1
			});
		}

		if (link2Node) {
			animate(link2Node, {
				y: '0vh',
				x: '0vw',
				duration: 400,
				ease: 'outExpo',
				scale: 1
			});
		}
	};

	function handleLink1Enter() {
		if (!isBrowserSupported || !link1Node) return;
		animate(link1Node, {
			fontSize: '2.5rem',
			duration: 400,
			ease: 'outExpo'
		});
	}

	function handleLink1Leave() {
		if (!link1Node) return;
		animate(link1Node, {
			fontSize: '1rem',
			duration: 400,
			ease: 'outExpo'
		});
	}

	function handleLink2Enter() {
		if (!isBrowserSupported || !link2Node) return;
		animate(link2Node, {
			fontSize: '2.5rem',
			duration: 400,
			ease: 'outExpo'
		});
	}

	function handleLink2Leave() {
		if (!isBrowserSupported || !link2Node) return;
		animate(link2Node, {
			fontSize: '1rem',
			duration: 400,
			ease: 'outExpo'
		});
	}

	function generatePoints() {
		const total = utils.random(4, 64);
		const r1 = utils.random(4, 56);
		const r2 = 56;
		const isOdd = (n: number) => n % 2;
		let points = '';
		for (let i = 0, l = isOdd(total) ? total + 1 : total; i < l; i++) {
			const r = isOdd(i) ? r1 : r2;
			const a = (2 * Math.PI * i) / l - Math.PI / 2;
			const x = 152 + utils.round(r * Math.cos(a), 0);
			const y = 56 + utils.round(r * Math.sin(a), 0);
			points += `${x},${y} `;
		}
		return points;
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	bind:this={containerNode}
	onpointerenter={handleMouseEnter}
	onpointerleave={handleMouseLeave}
	class="grid-bg z-30 h-12.5 overflow-visible bg-black md:overflow-hidden fixed top-0 left-0 w-full"
>
	<a href="/">
		<h1
			bind:this={titleNode}
			class="bbh-bartle-regular m-0 bg-black p-0 text-[32px] font-bold tracking-wide text-base-200 md:text-5xl inline-block cursor-pointer"
		>
			AMNESIA
		</h1>
	</a>

	{#if !isBrowserSupported}
		<div class="justifty-end jetbrains-mono absolute top-14 right-4 h-full md:top-0">
			{#if userState.session}
				<a
					bind:this={link1Node}
					class="link-node inline-block text-base-100/80 mr-4"
					href="/dashboard">DASHBOARD</a
				>
				<a bind:this={link2Node} class="link-node inline-block text-base-100/80" href="/logout">LOGOUT</a>
			{:else}
				<a
					bind:this={link1Node}
					class="link-node inline-block text-base-100/80 mr-4"
					href="/">HOME</a
				>
				<a bind:this={link2Node} class="link-node inline-block text-base-100/80" href="/login">LOGIN</a>
			{/if}
		</div>
	{/if}

	<svg
		viewBox="0 0 304 112"
		class="motion-svg pointer-events-none absolute top-[10vh] -right-50 hidden size-150 md:block"
	>
		<g
			stroke-width="2"
			stroke="var(--color-base-200)"
			stroke-linejoin="round"
			fill="none"
			fill-rule="evenodd"
		>
			<polygon
				bind:this={svgPath1}
				id="path-1"
				points="152,4 170,38 204,56 170,74 152,108 134,74 100,56 134,38"
			></polygon>
			<polygon
				bind:this={svgPath2}
				style="opacity: 0"
				id="path-2"
				points="152,4 170,38 204,56 170,74 152,108 134,74 100,56 134,38"
			></polygon>
		</g>
	</svg>
</div>

{#if isBrowserSupported && !isMobileViewport}
	<div class="justifty-end jetbrains-mono fixed z-40 top-3.5 right-4 h-full md:top-3">
		{#if userState.session}
			<a
				bind:this={link1Node}
				onpointerenter={handleLink1Enter}
				onpointerleave={handleLink1Leave}
				class="link-node inline-block text-base-100/80 mr-4 cursor-pointer"
				href="/dashboard">DASHBOARD</a
			>
			<a
				bind:this={link2Node}
				onpointerenter={handleLink2Enter}
				onpointerleave={handleLink2Leave}
				class="link-node inline-block text-base-100/80 cursor-pointer"
				href="/logout">LOGOUT</a
			>
		{:else}
			<a
				bind:this={link1Node}
				onpointerenter={handleLink1Enter}
				onpointerleave={handleLink1Leave}
				class="link-node inline-block text-base-100/80 mr-4 cursor-pointer"
				href="/">HOME</a
			>
			<a
				bind:this={link2Node}
				onpointerenter={handleLink2Enter}
				onpointerleave={handleLink2Leave}
				class="link-node inline-block text-base-100/80 cursor-pointer"
				href="/login">LOGIN</a
			>
		{/if}
	</div>
{/if}

<style>
	.link-node {
		text-shadow: 0 2px 4px rgba(0,0,0,0.5);
		transition: color 0.3s;
	}
	.link-node:hover {
		color: #ffffff;
	}
</style>
