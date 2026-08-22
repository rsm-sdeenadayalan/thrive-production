/**
 * Feature flags.
 *
 * Hidden for now to simplify the UI. Flip to true to bring back.
 *
 * The two floating widgets mount from the app shell, so they are present on
 * every route at once -- which makes them the two things most able to get in
 * the way while the rest of the app is still being built. MIGRATION.md section 9
 * already records them overlapping page content at 375px (defect 6). Their
 * mount points exist in the shell, gated on these flags, so turning them back
 * on is a one-word change rather than a re-integration.
 */
export interface Features {
	/** The floating quick list. `quicklist/QuickListWidget` in the Next app. */
	floatingTodo: boolean;
	/** Ask THRIVE. `assistant/AssistantWidget` in the Next app. */
	floatingAssistant: boolean;
}

export const FEATURES: Features = {
	floatingTodo: false,
	floatingAssistant: false
};
