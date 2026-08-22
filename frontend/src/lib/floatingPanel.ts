import { createOverrideStore } from "$lib/overrideStore.svelte";

/**
 * Persisted geometry for a floating panel.
 *
 * Two panels use this -- Ask THRIVE and the quick list -- so the shape and the
 * storage live here rather than once per widget. Each gets its own
 * `localStorage` key and its own independent position, size, and open state.
 *
 * Built on `createOverrideStore` under one fixed key. The fit is not perfect
 * (this is UI state, not an override over provider truth) but that module is
 * the single persistence mechanism, and one seam to change later beats three.
 *
 * Plain `.ts`: it declares no runes of its own. Reading `store.values` inside
 * the getter below is what makes it reactive, and that works from any module.
 */

export type DockSide = "free" | "left" | "right";

export interface PanelState {
	open: boolean;
	dock: DockSide;
	/** Viewport coordinates of the top-left. Only read when dock is "free". */
	x: number;
	y: number;
	/** Size in px while floating. `-1` means "not set yet, use the default". */
	w: number;
	h: number;
}

/**
 * Closed, centred, default size.
 *
 * `-1` is the "not positioned yet" sentinel: a panel centres itself on first
 * open, once it can measure the viewport. Storing a real coordinate here would
 * bake one machine's window size into the default.
 */
export const DEFAULT_PANEL: PanelState = {
	open: false,
	dock: "free",
	x: -1,
	y: -1,
	w: -1,
	h: -1,
};

const KEY = "panel";

export interface PanelStore {
	/** Current geometry, reactive. Was `usePanel()`. */
	panel: () => PanelState;
	setPanel: (next: PanelState) => void;
	/** Read outside a reactive context, for handlers that need the current value. */
	readPanel: () => PanelState;
}

export function createPanelStore(storageKey: string): PanelStore {
	const store = createOverrideStore<PanelState>(storageKey);

	// Spread over the default so a value persisted before a field existed still
	// parses -- localStorage outlives the shape that wrote it.
	const merge = (stored: PanelState | undefined): PanelState =>
		stored ? { ...DEFAULT_PANEL, ...stored } : DEFAULT_PANEL;

	return {
		panel: () => merge(store.values[KEY]),
		setPanel: (next) => store.set(KEY, next),
		readPanel: () => merge(store.read()[KEY]),
	};
}
