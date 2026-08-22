import { createPanelStore, type PanelState } from "$lib/floatingPanel";

/**
 * Where the Ask THRIVE panel is, and whether it is open.
 *
 * Persisted so the panel is where the student left it across a navigation and
 * a reload -- a panel that resets to centre every time you change page is a
 * panel you stop moving.
 *
 * The shape and the storage live in `floatingPanel.ts`, shared with the quick
 * list. This module is just the instance.
 */

const store = createPanelStore("thrive:assistant");

export type AssistantState = PanelState;

/** Was `useAssistantState()`. */
export const assistantState = store.panel;
export const setAssistantState = store.setPanel;
export const readAssistantState = store.readPanel;
