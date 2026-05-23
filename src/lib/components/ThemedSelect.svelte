<script lang="ts">
	import { animate } from 'animejs';
	import { onMount } from 'svelte';

	export type ThemedSelectOption = {
		value: string;
		label: string;
		hint?: string;
		disabled?: boolean;
	};

	let {
		value = $bindable(''),
		options = [],
		placeholder = '请选择',
		disabled = false,
		positioning = 'fixed',
		className = '',
		panelClassName = '',
		onChange = (_value: string) => {}
	}: {
		value?: string;
		options?: ThemedSelectOption[];
		placeholder?: string;
		disabled?: boolean;
		positioning?: 'fixed' | 'absolute';
		className?: string;
		panelClassName?: string;
		onChange?: (value: string) => void;
	} = $props();

	let open = $state(false);
	let triggerNode = $state<HTMLButtonElement | null>(null);
	let panelNode = $state<HTMLDivElement | null>(null);
	let panelStyle = $state('');
	let mobileSheet = $state(false);

	let selectedOption = $derived(
		options.find((option) => String(option.value) === String(value)) ?? null
	);

	function syncPanelPosition() {
		if (!triggerNode) return;
		if (typeof window !== 'undefined' && window.innerWidth <= 900) {
			mobileSheet = true;
			panelStyle = `left:12px; right:12px; bottom:calc(env(safe-area-inset-bottom, 0px) + 12px); width:auto;`;
			return;
		}
		mobileSheet = false;
		if (positioning === 'absolute') {
			panelStyle = `left:0; top:calc(100% + 8px); width:100%;`;
			return;
		}
		const rect = triggerNode.getBoundingClientRect();
		const width = Math.max(rect.width, 220);
		const left = Math.min(
			Math.max(12, rect.left),
			window.innerWidth - width - 12
		);
		const top = Math.min(rect.bottom + 8, window.innerHeight - 16);
		panelStyle = `left:${left}px; top:${top}px; width:${width}px;`;
	}

	function animateOpen() {
		if (!panelNode) return;
		animate(panelNode, {
			opacity: [0, 1],
			duration: 160,
			ease: 'outQuad'
		});

		const items = Array.from(panelNode.querySelectorAll('.themed-select-option'));
		if (items.length > 0) {
			animate(items, {
				opacity: [0, 1],
				translateY: [-3, 0],
				delay: (_el: Element, index: number) => 20 + index * 18,
				duration: 180,
				ease: 'outExpo'
			});
		}
	}

	function openMenu() {
		if (disabled) return;
		open = true;
		syncPanelPosition();
		requestAnimationFrame(() => {
			syncPanelPosition();
			animateOpen();
		});
	}

	function closeMenu() {
		open = false;
	}

	function toggleMenu() {
		if (open) {
			closeMenu();
			return;
		}
		openMenu();
	}

	function chooseOption(option: ThemedSelectOption) {
		if (option.disabled) return;
		value = option.value;
		onChange(option.value);
		closeMenu();
		if (triggerNode) {
			animate(triggerNode, {
				boxShadow: [
					'0 0 0 0 color-mix(in oklab, var(--dashboard-accent) 0%, transparent)',
					'0 0 0 3px color-mix(in oklab, var(--dashboard-accent) 14%, transparent)',
					'0 0 0 0 color-mix(in oklab, var(--dashboard-accent) 0%, transparent)'
				],
				duration: 260,
				ease: 'outQuad'
			});
		}
	}

	function handleWindowPointerDown(event: MouseEvent) {
		if (!open) return;
		const target = event.target;
		if (
			triggerNode?.contains(target as Node) ||
			panelNode?.contains(target as Node)
		) {
			return;
		}
		closeMenu();
	}

	function handleWindowResize() {
		if (!open) return;
		syncPanelPosition();
	}

	function handleWindowKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			closeMenu();
		}
	}

	function handleTriggerKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			toggleMenu();
		}
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			openMenu();
		}
	}

	onMount(() => {
		window.addEventListener('mousedown', handleWindowPointerDown);
		window.addEventListener('resize', handleWindowResize);
		window.addEventListener('scroll', handleWindowResize, true);
		window.addEventListener('keydown', handleWindowKeydown);

		return () => {
			window.removeEventListener('mousedown', handleWindowPointerDown);
			window.removeEventListener('resize', handleWindowResize);
			window.removeEventListener('scroll', handleWindowResize, true);
			window.removeEventListener('keydown', handleWindowKeydown);
		};
	});
</script>

<div class={`themed-select ${className}`}>
	<button
		bind:this={triggerNode}
		type="button"
		class:open
		class="themed-select-trigger"
		aria-haspopup="listbox"
		aria-expanded={open}
		disabled={disabled}
		onclick={toggleMenu}
		onkeydown={handleTriggerKeydown}
	>
		<span class="themed-select-label" title={selectedOption?.label || placeholder}>
			{selectedOption?.label || placeholder}
		</span>
		<svg class="themed-select-arrow" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
			<path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m6 9l6 6l6-6"/>
		</svg>
	</button>

	{#if open}
		<div
			bind:this={panelNode}
			class:absolute-panel={positioning === 'absolute'}
			class:mobile-sheet={mobileSheet}
			class={`themed-select-panel ${panelClassName}`}
			style={panelStyle}
			role="listbox"
		>
			{#each options as option}
				<button
					type="button"
					class:disabled={option.disabled}
					class:selected={String(option.value) === String(value)}
					class="themed-select-option"
					role="option"
					aria-selected={String(option.value) === String(value)}
					disabled={option.disabled}
					onclick={() => chooseOption(option)}
				>
					<span class="themed-select-option-copy">
						<span class="themed-select-option-label">{option.label}</span>
						{#if option.hint}
							<span class="themed-select-option-hint">{option.hint}</span>
						{/if}
					</span>
					{#if String(option.value) === String(value)}
						<span class="themed-select-check">✓</span>
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.themed-select {
		position: relative;
		width: 100%;
	}

	.themed-select-trigger {
		display: flex;
		width: 100%;
		min-height: 2.6rem;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		border: 1px solid var(--dashboard-border);
		border-radius: calc(var(--dashboard-radius) * 0.55);
		background: color-mix(in oklab, var(--dashboard-panel) 88%, var(--dashboard-bg));
		padding: 0.65rem 0.85rem;
		color: var(--dashboard-fg);
		font-size: 0.8rem;
		text-align: left;
		outline: none;
		box-shadow:
			0 10px 24px color-mix(in oklab, var(--dashboard-shadow-color) 26%, transparent),
			inset 0 1px 0 color-mix(in oklab, white 12%, transparent);
		cursor: pointer;
		transition:
			border-color 160ms ease,
			background-color 160ms ease,
			box-shadow 160ms ease,
			transform 160ms ease;
	}

	.themed-select-trigger:hover {
		background: color-mix(in oklab, var(--dashboard-panel) 94%, var(--dashboard-bg));
		border-color: var(--dashboard-border-strong);
	}

	.themed-select-trigger:focus-visible,
	.themed-select-trigger.open {
		border-color: color-mix(in oklab, var(--dashboard-accent) 46%, var(--dashboard-fg));
		box-shadow: 0 0 0 3px color-mix(in oklab, var(--dashboard-accent) 14%, transparent);
	}

	.themed-select-trigger:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}

	.themed-select-label {
		min-width: 0;
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.themed-select-arrow {
		flex-shrink: 0;
		color: color-mix(in oklab, var(--dashboard-fg) 62%, transparent);
		transition: transform 180ms ease, color 180ms ease;
	}

	.themed-select-trigger.open .themed-select-arrow {
		transform: rotate(180deg);
		color: color-mix(in oklab, var(--dashboard-accent) 68%, var(--dashboard-fg));
	}

	.themed-select-panel {
		position: fixed;
		z-index: 90;
		display: flex;
		max-height: min(22rem, calc(100vh - 2rem));
		flex-direction: column;
		gap: 0.2rem;
		overflow-y: auto;
		border: 1px solid color-mix(in oklab, var(--dashboard-fg) 10%, transparent);
		border-radius: calc(var(--dashboard-radius) * 0.7);
		background:
			linear-gradient(
				180deg,
				color-mix(in oklab, var(--dashboard-panel) 96%, white 4%),
				color-mix(in oklab, var(--dashboard-panel) 92%, var(--dashboard-bg))
			);
		padding: 0.45rem;
		box-shadow:
			0 24px 60px color-mix(in oklab, var(--dashboard-shadow-color) 90%, transparent),
			inset 0 1px 0 color-mix(in oklab, white 18%, transparent);
		backdrop-filter: blur(20px) saturate(1.15);
	}

	.themed-select-panel.absolute-panel {
		position: absolute;
		inset: auto auto auto 0;
		max-height: 18rem;
	}

	.themed-select-panel.mobile-sheet {
		position: fixed;
		inset: auto 12px calc(env(safe-area-inset-bottom, 0px) + 12px) 12px;
		width: auto !important;
		max-height: min(58vh, 28rem);
		border-radius: calc(var(--dashboard-radius) * 0.9);
		padding: 0.55rem;
	}

	.themed-select-option {
		display: flex;
		width: 100%;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		border: 1px solid transparent;
		border-radius: calc(var(--dashboard-radius) * 0.42);
		background: transparent;
		padding: 0.62rem 0.7rem;
		color: var(--dashboard-fg);
		text-align: left;
		cursor: pointer;
		transition:
			transform 160ms ease,
			background-color 160ms ease,
			border-color 160ms ease;
	}

	.themed-select-option:hover {
		transform: translateX(2px);
		background: color-mix(in oklab, var(--dashboard-hover-bg) 82%, var(--dashboard-panel));
		border-color: color-mix(in oklab, var(--dashboard-accent) 18%, transparent);
	}

	.themed-select-option.selected {
		background: var(--dashboard-active-bg);
		border-color: color-mix(in oklab, var(--dashboard-accent) 22%, transparent);
	}

	.themed-select-option.disabled {
		cursor: not-allowed;
		opacity: 0.45;
	}

	.themed-select-option-copy {
		display: flex;
		min-width: 0;
		flex: 1;
		flex-direction: column;
	}

	.themed-select-option-label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.8rem;
		font-weight: 700;
		line-height: 1.2;
	}

	.themed-select-option-hint {
		margin-top: 0.15rem;
		font-size: 0.68rem;
		line-height: 1.2;
		color: var(--dashboard-soft-fg);
	}

	.themed-select-check {
		flex-shrink: 0;
		font-size: 0.76rem;
		font-weight: 900;
		color: color-mix(in oklab, var(--dashboard-accent) 72%, var(--dashboard-fg));
	}

	@media (max-width: 900px) {
		.themed-select-trigger {
			min-height: 2.85rem;
			padding: 0.8rem 0.95rem;
			font-size: 0.9rem;
		}

		.themed-select-panel.mobile-sheet {
			inset: auto 0 0 0;
			max-height: min(70dvh, 34rem);
			border-right: none;
			border-bottom: none;
			border-left: none;
			border-radius: 1.35rem 1.35rem 0 0;
			padding:
				0.7rem
				0.7rem
				calc(env(safe-area-inset-bottom, 0px) + 0.7rem)
				0.7rem;
		}

		.themed-select-option {
			min-height: 3rem;
			padding: 0.8rem 0.9rem;
		}

		.themed-select-option-label {
			font-size: 0.88rem;
		}

		.themed-select-option-hint {
			font-size: 0.72rem;
		}
	}
</style>
