import { messages } from '$lib/messages';
import type { TagTone } from '$lib/tones';
import type { DueDescriptor } from '$lib/format';
import type { Priority, Task, TaskSource } from '$lib/data';

/**
 * How a task row is presented.
 *
 * THRIVE has two inputs that both want to drive a row's emphasis -- the due
 * date's urgency and the task's own stated priority -- so they are merged here
 * rather than in the component, and the merge rule lives in one place.
 *
 * Client-safe: takes an already-classified `DueDescriptor`, never a raw date.
 * That is what lets a row be re-derived after the student edits a due date
 * without anything here reading a clock.
 */

export type RowPriority = 'urgent' | 'soon' | 'later' | 'none';

/**
 * The row's priority as a WORD, for screen readers.
 *
 * `.thrive-row` carries priority as a left edge and a wash, and neither of those
 * exists with colour turned off. Two rows visibly different and identically
 * spoken is the failure this closes. `none` is empty because a row with no
 * priority has nothing to say, and an empty string renders no element at all at
 * the call site.
 *
 * Shares `taskLabels`' strings on purpose: a row whose state chip already reads
 * "Urgent" must not also announce a different word for the same fact.
 */
export const rowPriorityLabel: Record<RowPriority, string> = {
	urgent: messages.taskLabels.urgent,
	soon: messages.taskLabels.dueSoon,
	later: messages.taskLabels.later,
	none: ''
};

/**
 * Deadline outranks stated priority.
 *
 * A low-priority task that is already overdue is the most urgent thing on the
 * screen, and tinting it by its stated priority would bury it. A done task earns
 * no tint at all -- it has stopped competing for attention.
 */
export function rowPriorityOf(
	due: DueDescriptor,
	priority: Priority,
	done: boolean
): RowPriority {
	if (done) return 'none';
	if (due.urgency === 'overdue') return 'urgent';
	if (due.urgency === 'today' || priority === 'high') return 'soon';
	if (priority === 'medium') return 'later';
	return 'none';
}

export interface TaskLabel {
	text: string;
	tone: TagTone;
}

const sourceLabel: Record<TaskSource, string> = {
	class: messages.taskLabels.class,
	career: messages.taskLabels.career,
	admin: messages.taskLabels.admin,
	event: messages.taskLabels.event
};

/**
 * At most two labels per task: one for state, one for where it came from.
 *
 * Two is a deliberate cap rather than an accident of the data. The direction is
 * that a row stays quiet, and a row wearing four tags is a row shouting. State
 * comes first because it is the thing worth acting on.
 *
 * "Done" REPLACES the state label rather than joining it -- a finished task has
 * no urgency left to report.
 *
 * A task whose due date will not parse gets no state label at all. `describeDue`
 * returns `urgency: "unknown"` for that case, and inventing an urgency for a
 * date that does not exist is how a broken deadline ends up looking fine.
 */
export function taskLabels(
	task: Pick<Task, 'source' | 'courseCode' | 'priority'>,
	due: DueDescriptor,
	done: boolean
): TaskLabel[] {
	const labels: TaskLabel[] = [];

	if (done) {
		labels.push({ text: messages.taskLabels.done, tone: 'neutral' });
	} else if (due.urgency === 'overdue') {
		labels.push({ text: messages.taskLabels.urgent, tone: 'urgent' });
	} else if (due.urgency === 'today' || task.priority === 'high') {
		labels.push({ text: messages.taskLabels.dueSoon, tone: 'watch' });
	}

	// Course code beats the generic source word: "MGT 253" places the work,
	// "Class" does not.
	const origin: TaskLabel =
		task.source === 'class' && task.courseCode
			? { text: task.courseCode, tone: 'primary' }
			: { text: sourceLabel[task.source], tone: 'neutral' };

	labels.push(origin);

	return labels.slice(0, 2);
}
