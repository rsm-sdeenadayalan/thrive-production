/**
 * The fit-on-one-screen numbers, as design-system values.
 *
 * Two halves, in two places, for a reason:
 *
 *  - The **height cap** is a CSS length and lives in `app.css` as
 *    `--thrive-card-body-cap`, consumed by `.thrive-card-body`. It is a size,
 *    and sizes belong in the design system file with every other size.
 *  - The **collapsed row counts** are integers that JavaScript has to slice
 *    with, so they cannot be CSS. They live here.
 *
 * What matters is that neither is a number typed into a component. A card asks
 * for `COLLAPSED_TASK_ROWS`; it does not decide that four is the right number,
 * and changing the answer is one edit in one file.
 *
 * ## How these were chosen
 *
 * By driving the built page in a real browser and reading
 * `getBoundingClientRect`, not by arithmetic. Solved for a 1512x1052 viewport
 * (MacBook Pro 14 at default scaling), where the sticky top bar leaves a 996px
 * budget and the cap of 19rem produces a 968px grid.
 *
 * The counts are then whatever makes each card's collapsed content land just
 * under the 304px cap -- which is a different number per card, because a course
 * card is 141px and a task row is 54px. Measured collapsed heights at these
 * counts: Tasks 299px, My Classes 294px, today's classes 55px.
 */

/**
 * Task rows shown before "show N more".
 *
 * Four, and four fits only because the collapsed view is FLAT -- no group
 * headings, and the progress bar moved into the card's header band. With those
 * in the body the card carried ~190px of furniture before its first row, and at
 * any cap that let the grid fit a laptop it showed one task.
 *
 * The headings come back on expand, where they are worth their height. See the
 * note in `TasksCard`.
 *
 * ## The collapsed card scrolls now, and that is the trade
 *
 * 6a measured 299px of content for four rows plus the Done heading, against the
 * 300px cap -- collapsed, it fit exactly, with nothing to scroll. **That is no
 * longer true and the number above is 6a's, kept only as history.**
 *
 * Re-measured at 1512x1052 once the rows became editable: a desktop row is 61-81px
 * rather than 54px, and the collapsed body holds 424px of content. The cause is
 * arithmetic, not styling: a row carries five 44px controls (WCAG 2.5.8, and
 * shrinking them would trade a layout problem for an accessibility one), so it
 * cannot be shorter than 44px plus its padding whatever else changes. Four of
 * those plus the Done heading plus the 44px "Add a task" button does not fit 300px,
 * and no arrangement of them will.
 *
 * So the collapsed card scrolls about 124px inside its own body. **The guarantee
 * that actually matters is untouched:** `.thrive-card-body` is a FIXED height, so
 * the overflow can only ever scroll and the 2x2 grid is still immovable --
 * asserted by `check:interaction` ("editing did not move the grid") and by
 * `check:layout` on every route and viewport.
 *
 * The alternative is three rows, which would fit. It is not taken here because it
 * is a visible change to Home's densest card and belongs to whoever owns that
 * decision, not to this constant. Flagged in HANDOFF.
 */
export const COLLAPSED_TASK_ROWS = 4;

/**
 * Course cards shown before "show N more".
 *
 * Two, not four. A measured course card is 141px against a 54px task row, so the
 * shared cap holds far fewer of them -- 2 cards plus their gap is 294px, 3 would
 * be 447px and overflow. The count differs per card because the rows differ, and
 * pretending one number fits all of them is how a card ends up either scrolling
 * at rest or leaving half its cap empty.
 */
export const COLLAPSED_COURSE_CARDS = 2;

/**
 * Event rows shown before "show N more".
 *
 * This one is NOT a collapse limit in the same sense -- it is the Next app's
 * `VISIBLE = 4`, kept because it is load-bearing behaviour rather than layout:
 * ignored events are filtered FIRST and this slice happens second, so the next
 * event moves up instead of leaving a gap. Named here so the layout numbers sit
 * together, but see `UpcomingEvents` for why the order matters.
 */
export const VISIBLE_EVENTS = 4;

/**
 * Class rows shown before "show N more".
 *
 * Today's classes is the one card that is usually short -- four meetings on a
 * heavy day, often one or none. It gets a limit anyway so a Monday with four
 * classes cannot be the thing that breaks the grid.
 */
export const COLLAPSED_CLASS_ROWS = 4;
