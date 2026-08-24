/**
 * Every user-facing string in THRIVE, in one place.
 *
 * English only. No translation library, no locale switching, no runtime lookup
 * by key. This is not i18n -- it is the thing that makes i18n possible later
 * without a rewrite.
 *
 * ## The shape, and why
 *
 * A nested object of strings and functions, grouped by the surface that renders
 * them. Three properties matter, and they are the three that make a retrofit
 * cheap:
 *
 * 1. **No user-facing string is written inline in a component.** Finding all
 *    the copy is `messages.ts`, not a grep across the tree that will miss the
 *    one in a ternary.
 * 2. **Every string has a stable path.** `messages.home.tasks.title` does not
 *    move when the component is refactored, so a Mandarin file can be a
 *    parallel object with the same shape and swapping them is one import.
 * 3. **Anything with a value in it is a FUNCTION, not a template assembled at
 *    the call site.** This is the part that actually breaks translations. A
 *    component writing `{count} more` bakes English word order into markup;
 *    `showMore(count)` lets a translation put the number wherever that language
 *    puts it, or use a different form for one versus many.
 *
 * Rejected: flat dotted keys (`"home.tasks.title"`), which lose type safety and
 * autocomplete and gain nothing until there is a real i18n runtime; and
 * per-component message files, which spread the copy back out and make a
 * translator open twenty files.
 *
 * ## What does not belong here
 *
 * Anything that is not prose a person reads: `aria-label`s that name a value
 * already on screen still count as copy and DO belong here, but token names,
 * route hrefs, and data values do not. Fixture text (course titles, event
 * names) comes from the data layer and is not copy.
 */

export const messages = {
	/** Reused across surfaces. Kept here rather than duplicated per card. */
	common: {
		viewAll: 'View all',
		/** Names which section a "View all" leads to, for screen readers. */
		viewAllIn: (section: string) => ` in ${section}`,
		undo: 'Undo',
		ignore: 'Ignore',
		/** Appended to a one-word button so the accessible name has a subject. */
		ignoreSubject: (title: string) => ` ${title}`,
		showMore: (count: number) => `Show ${count} more`,
		showLess: 'Show less',
		done: 'Done',
		/** A group heading's count, e.g. "Done · 3". */
		countSuffix: (count: number) => ` · ${count}`,

		/**
		 * Copy shared by every surface that lists an opt-in event.
		 *
		 * Home and the calendar render the same act with the same words, and they
		 * write the same store under the same key. Two copies of these strings was
		 * survivable while Home's controls were inert; it stopped being survivable
		 * the moment both were live, because a translation would then have to find
		 * both and keep them in step.
		 *
		 * Here rather than in `home` or `calendar` for the reason this group exists:
		 * these are reused across surfaces, not owned by one.
		 */
		events: {
			countMeIn: 'Count me in',
			/** Appended so a screen reader hears which event, not four identical buttons. */
			subject: (title: string) => ` for ${title}`,
			/**
			 * State and exit, deliberately two things.
			 *
			 * Joining used to be one toggle: the button read "You're in" and pressing
			 * it again removed you, which nobody could discover. A control whose
			 * off-switch is invisible is a control students are afraid to press.
			 */
			joined: 'You’re in',
			leave: 'Remove from my list',
			/** Said once per joined row, because the button implies otherwise. */
			joinedNote: 'Saved in THRIVE only. Nobody was notified.',
			addToCalendar: 'Add to calendar',
			relevanceBadge: 'For you'
		}
	},

	home: {
		/** The eyebrow above the greeting, and the page title. */
		documentTitle: 'Home',

		greeting: {
			/** `greetingFor()` supplies "Good morning"; this joins it to a name. */
			line: (greeting: string, firstName: string) => `${greeting}, ${firstName}`,
			headingId: 'greeting-heading',
			goalChip: (goal: string) => `Becoming: ${goal}`,
			trackChip: (track: string) => `${track} track`,
			unitsChip: (completed: number, required: number) =>
				`${completed} of ${required} units`,
			unitsBarLabel: 'Units completed toward the degree'
		},

		stats: {
			overdue: 'overdue',
			dueToday: 'due today',
			eventsThisWeek: 'events this week',
			/*
			 * The popover's list name, e.g. "3 overdue".
			 *
			 * A function rather than `${count} ${label}` at the call site, and this
			 * is the case that shows why the rule is not pedantry: the pill's own
			 * label is already a separate string, so a language that puts the count
			 * after the noun, or inflects the noun on the count, has one place to say
			 * so. Assembling it in markup would bake English order into three
			 * components.
			 */
			listLabel: (count: number, label: string) => `${count} ${label}`,
			/** The accessible name of a popover row. The arrow alone is not a name. */
			jumpTo: (title: string) => `Jump to ${title}`
		},

		timeline: {
			/** Shown when no phase is current, e.g. between terms. */
			fallbackTerm: 'Your program',
			youAreHere: ' · you are here',
			/*
			 * Split in two on purpose, and the one place in this file where a
			 * sentence is not a single string.
			 *
			 * The percentage is a value, so the two-face rule puts it in mono, which
			 * means it has to be its own element inside the sentence. Exposing the
			 * split as two message entries is the honest way to do that: a
			 * translation can rewrite `progressRest` completely, including the
			 * punctuation and where the finish term falls.
			 *
			 * The limitation, stated rather than discovered: the VALUE always comes
			 * first. A language that wants "through 42% of your program" cannot
			 * express that here. If one turns up, this becomes a function returning
			 * parts rather than two strings -- which is a change to one entry and one
			 * component, not to the architecture.
			 */
			progressPercent: (percent: number) => `${percent}%`,
			progressRest: (finishTerm: string) =>
				` through your program · finish ${finishTerm}`,
			/** Spoken form of one pip, which is otherwise colour-only. */
			phaseStatus: (label: string, term: string, status: string, optional: boolean) =>
				`${label}, ${term}, ${status}${optional ? ', optional' : ''}`,
			statusComplete: 'completed',
			statusCurrent: 'in progress',
			statusUpcoming: 'not started'
		},

		tasks: {
			title: 'Tasks',
			description: 'What to do next, pulled from every source',
			progressLabel: 'Tasks done this week',
			progressValue: (done: number, total: number) => `${done} of ${total} done`,
			/** The live-region sentence. Read on load and after any change. */
			liveCount: (done: number, total: number) =>
				`${done} of ${total} tasks done this week.`,
			emptyAll: 'Nothing on your list yet. Add the first thing below.',
			emptyOpen: 'Everything on your list is done. Enjoy it.'
		},

		todaysClasses: {
			title: 'Today’s classes',
			empty: 'No classes today. A good day to get ahead.'
		},

		myClasses: {
			title: 'My Classes',
			description: (count: number) => `${count} courses this term`,
			progressLabel: (code: string) => `${code} course progress`,
			/*
			 * A prefix, not a whole sentence, for the same reason the timeline
			 * percentage is split: the assignment title is styled differently from
			 * the word introducing it, so it has to be its own element. Same
			 * value-comes-last limitation, same one-entry fix if a language needs
			 * otherwise.
			 */
			nextPrefix: 'Next: '
		},

		events: {
			title: 'Upcoming Events',
			description: 'Matched to your goal and track',
			empty: 'Nothing scheduled. New events appear here as they’re announced.',
			/** The only way back on Home, and only once nothing is left. */
			allIgnored: 'You have ignored every upcoming event.',
			bringBack: 'Bring them back',
			broughtBack: 'Ignored events restored',
			ignored: (title: string) => `Ignored “${title}”`
			/* "Count me in", "You're in", "Add to calendar" and the "For you" badge
			   moved to `common.events` in 7c, when Home's controls were wired and the
			   calendar started rendering the identical words for the identical act. */
		}
	},

	/** Group headings for the task list. Also the spoken name of each group. */
	taskGroups: {
		/*
		 * A task whose due date will not parse. Its own group, at the TOP of the
		 * list -- decided 2026-08-21 after it spent a phase reachable in the data
		 * and rendered nowhere.
		 *
		 * "Needs a date" rather than "No date": the row is not describing itself,
		 * it is asking for something. A student who sees it can fix it; a student
		 * who never sees it has a deadline that silently does not exist.
		 */
		unknown: 'Needs a date',
		overdue: 'Overdue',
		today: 'Today',
		upcoming: 'This week',
		done: 'Done'
	},

	/** The two-label cap per task row. See taskView.ts. */
	taskLabels: {
		urgent: 'Urgent',
		dueSoon: 'Due soon',
		/** Only ever spoken. `rowPriorityLabel` uses it; no chip renders it. */
		later: 'Later',
		done: 'Done',
		class: 'Class',
		career: 'Career',
		admin: 'Admin',
		event: 'Event'
	},

	/**
	 * Editing a task in place. Shared by Home and, later, /assignments.
	 *
	 * Nearly every entry here is a function, and the reason is the same one every
	 * time: these strings name a specific task, so a screen reader hears "Edit
	 * Draft the case memo" rather than a row of buttons all called "Edit". A
	 * template assembled at the call site would bake English word order into five
	 * components.
	 */
	taskEditing: {
		/* --- The row's controls --------------------------------------------- */
		/** The checkbox's accessible name IS the task, so it needs no verb. */
		toggle: (title: string) => title,
		copyToList: (title: string) => `Copy ${title} to your to-do list`,
		copied: (title: string) => `“${title}” copied to your to-do list`,
		edit: (title: string) => `Edit ${title}`,
		addNote: (title: string) => `Add a note to ${title}`,
		editNote: (title: string) => `Edit your note on ${title}`,

		/* --- Reordering ----------------------------------------------------- */
		/** Names where the row is now, so a move has a stated starting point. */
		position: (index: number, count: number, group: string) =>
			`position ${index} of ${count} in ${group}`,
		moveUp: (title: string, position: string) => `Move ${title} up. Currently ${position}.`,
		moveDown: (title: string, position: string) => `Move ${title} down. Currently ${position}.`,
		/** Announced after a keyboard or pointer move lands. */
		moved: (title: string, index: number, count: number, group: string) =>
			`${title} moved to position ${index} of ${count} in ${group}.`,
		movedToGroup: (title: string, group: string) => `${title} moved to ${group}. Due date updated.`,

		/* --- The inline editor ---------------------------------------------- */
		titleField: 'Title',
		titleHint: 'Enter to save, Escape to cancel. Clear the field to restore the original.',
		priorityField: 'Priority',
		save: 'Save',
		saveSubject: (title: string) => ` changes to ${title}`,
		cancel: 'Cancel',
		cancelSubject: (title: string) => ` editing ${title}`,

		/* --- Priority ------------------------------------------------------- */
		priorityLegend: (title: string) => `Priority for ${title}`,
		priorityHigh: 'High',
		priorityMedium: 'Med',
		priorityLow: 'Low',
		/** The full word, spoken after the abbreviation the button shows. */
		priorityHighFull: 'High priority',
		priorityMediumFull: 'Medium priority',
		priorityLowFull: 'Low priority',

		/* --- Notes ---------------------------------------------------------- */
		noteLabel: (title: string) => `Your note on ${title}`,
		notePlaceholder: 'A note to yourself…',

		/* --- The due date editor -------------------------------------------- */
		changeDue: (title: string) => ` — change the due date for ${title}`,
		dueDialogLabel: (title: string) => `Due date for ${title}`,
		dueToday: 'Today',
		dueTomorrow: 'Tomorrow',
		dueNextWeek: 'Next week',
		duePick: 'Pick a date',
		dueUpdated: (title: string) => `${title} due date updated.`,
		/*
		 * The row has just left the list, and saying so is the point.
		 *
		 * Home shows this week only, so a date set further out removes the row --
		 * correctly, and invisibly. A student who sets a date and watches the row
		 * vanish with no explanation has been given the app's worst failure mode: a
		 * correct action that looks like a broken one. The date is a value, so it is
		 * passed in already formatted.
		 */
		dueMovedOutOfWeek: (title: string, when: string) =>
			`${title} moved to ${when}, which is past this week. It is no longer in this list.`,

		/* --- Undo ----------------------------------------------------------- */
		markedDone: 'Marked done',
		markedNotDone: 'Marked not done',
		undoSubject: (action: string, title: string) => ` ${action.toLowerCase()}: ${title}`,
		/*
		 * The whole live sentence while an undo offer stands.
		 *
		 * ONE function rather than three strings joined at the call site, and this is
		 * the entry that shows why the rule is not pedantry: the card would otherwise
		 * write `${a} ${b}${c}` in markup, baking in the order of a clause, a count
		 * and an offer. A translation gets to put them wherever that language puts
		 * them, or to drop the count from the middle entirely.
		 */
		liveWithUndo: (action: string, title: string, done: number, total: number) =>
			`${action}: ${title}. ${done} of ${total} tasks done this week. Undo is available.`,
		/*
		 * Undone, but not shown -- because Home is this week only.
		 *
		 * Unticking a task due three weeks out puts it back on the list and then the
		 * week filter removes it again, so the row the student was looking at is
		 * simply gone. Saying so is the point: a correct action that looks like a
		 * broken one is this app's worst failure mode.
		 */
		restoredOutOfWeek: (title: string) =>
			`${title} is back on your list, but it is due past this week so it is not shown here.`,

		/* --- Adding --------------------------------------------------------- */
		addOpen: 'Add a task',
		addTitleField: 'Task',
		addTitlePlaceholder: 'What needs doing?',
		addDueField: 'Due',
		addPriorityField: 'Priority',
		addLabelField: 'Label',
		/** Rendered in normal case beside a small-caps label. */
		addLabelOptional: '(optional)',
		addLabelPlaceholder: 'MGT 253',
		addSubmit: 'Add task',
		addClose: 'Done adding',
		added: (title: string) => `${title} added.`
	},

	/**
	 * The calendar, complete as of Phase 7c: the page and the month grid (7a), the
	 * other two views and the filter bar (7b), and the detail dialog, the add form
	 * and the events section (7c).
	 *
	 * Two things here are worth naming because they are easy to get wrong on a
	 * retrofit:
	 *
	 * 1. **The counts line is one function, not a loop over a template.** A day
	 *    reads "4 classes · 3 tasks · 2 clubs", and assembling that at the call
	 *    site would bake both the pluralisation and the separator into markup. It
	 *    takes already-labelled pairs and returns the whole line.
	 * 2. **`dayFigureLabel` exists because the big number has no words beside it.**
	 *    A `3xl` "12" reads as a heading to a screen reader and as nothing at all
	 *    to a student who cannot see the breakdown next to it.
	 */
	calendar: {
		documentTitle: 'Calendar',
		/**
		 * ONE piece of furniture above the grid, not three.
		 *
		 * This block used to be an eyebrow ("calendar · fall 2026"), a 30px
		 * two-line title ("Everything, one page") and a subtitle listing the six
		 * streams — three things saying one thing, and together they pushed the
		 * month grid's top edge to 202px on a 1052px laptop.
		 *
		 * What survives is the page's NAME. The term is already on the month header
		 * a few pixels below, the streams are named in the Key, and every row in the
		 * day panel carries its own labelled tag — so the subtitle was describing
		 * what the page shows to someone who could already see it.
		 */
		title: 'Calendar',
		/**
		 * The Key's disclosure. Says what it opens, and carries the count of active
		 * filters so a hidden stream is never invisible while the panel is closed.
		 */
		keyToggle: 'Key and filters',
		keyToggleCount: (count: number) => `${count} hidden`,
		/*
		 * There is no `intro` any more. It was cut to one line and then cut
		 * entirely: a page whose Key names every stream and whose day rows each
		 * carry a labelled tag does not also need a sentence saying it holds
		 * classes and deadlines.
		 */

		/* --- The month grid ------------------------------------------------- */
		grid: {
			label: 'Calendar',
			today: 'Today',
			previousMonth: 'Previous month',
			nextMonth: 'Next month',
			/** Weekday column initials, Sunday first. Paired with the names below. */
			weekdayInitials: ['S', 'M', 'T', 'W', 'T', 'F', 'S'],
			weekdayNames: [
				'Sunday',
				'Monday',
				'Tuesday',
				'Wednesday',
				'Thursday',
				'Friday',
				'Saturday'
			],
			/**
			 * A day cell's whole accessible name. The date arrives already
			 * formatted; this decides what else is said and in what order.
			 */
			dayLabel: (date: string, items: string, today: boolean) =>
				today ? `${date}, ${items}, today` : `${date}, ${items}`,
			noItems: 'no items',
			itemCount: (count: number) => (count === 1 ? '1 item' : `${count} items`),
			/** The "+n" when a day has more categories than there are dots for. */
			overflow: (count: number) => `+${count}`
		},

		/* --- The selected day's header -------------------------------------- */
		header: {
			headingId: 'calendar-day-heading',
			todayChip: 'today',
			/** Names the bare figure, which otherwise reads as a heading. */
			dayFigureLabel: (count: number) =>
				count === 1 ? '1 item on this day' : `${count} items on this day`,
			nothing: 'nothing scheduled',
			/** "4 classes · 3 tasks". Pairs come in already pluralised. */
			countsLine: (parts: string[]) => parts.join(' · '),
			/** One "4 classes" pair. The irregular plural is the category's own. */
			countPart: (count: number, singular: string, plural: string) =>
				count === 1 ? `1 ${singular}` : `${count} ${plural}`,
			doneOfTickable: (done: number, tickable: number) => `${done} of ${tickable} done`,
			nextUpLabel: 'next up:',
			/** The square strip, named as a whole. */
			squaresLabel: 'What is left on this day',
			/** One square. State is a word, so colour is never the only channel. */
			squareLabel: (title: string, state: string) => `${title}: ${state}`,
			squareDone: 'done',
			squareNext: 'next up',
			squareNotDone: 'not done',
			/**
			 * The one live region on the page, read on every day change.
			 *
			 * Says what changed and how much is in it, because a student moving
			 * through the grid with arrow keys never sees the panel below repaint.
			 */
			announcement: (heading: string, schedule: number, personal: number, events: number) =>
				`${heading}. ${schedule} on your schedule, ${personal} on your list, ${events} to register for.`
		},

		/* --- The day's sections --------------------------------------------- */
		day: {
			headingId: 'day-items',
			eyebrow: 'your day',
			empty: 'Nothing scheduled this day. A good day to get ahead.',
			/** Arrange-by control. Words, so this is not a numeric treatment. */
			groupByLabel: 'Arrange the day by',
			groupByPrefix: 'by',
			groupByType: 'type',
			groupByTime: 'time',
			/** The single group the "time" arrangement produces. */
			chronological: 'Everything, in order'
		},

		/* --- One row -------------------------------------------------------- */
		row: {
			allDay: 'all day',
			urgent: 'urgent',
			/** Spoken form, for the week column's glyph where the pill will not fit. */
			urgentLabel: 'Urgent',
			/** The checkbox says what pressing it will do, not what is true now. */
			toggle: (title: string, done: boolean) =>
				done ? `Mark ${title} not done` : `Mark ${title} done`
		},

		/* --- The view switcher ---------------------------------------------- */
		views: {
			label: 'Calendar view',
			month: 'month',
			week: 'week',
			agenda: 'agenda',
			/** The agenda-only grouping control. Words, so DM Sans. */
			groupByLabel: 'group by',
			groupByDay: 'day',
			groupByCategory: 'type',
			groupByCourse: 'course'
		},

		/* --- The week columns ----------------------------------------------- */
		week: {
			/** A day with nothing in it. An em dash, not the word "empty". */
			emptyDay: '—',
			/** Names the column, since the heading is an abbreviation and a number. */
			selectDay: (date: string) => `Show ${date}`,
			/**
			 * Shown in the agenda's place when week view cannot fit.
			 *
			 * Not an error. The student asked for a view that needs seven readable
			 * columns and this screen has room for about two, so they get the list
			 * instead and are told why rather than left wondering what happened to
			 * their choice.
			 */
			fallbackNote: 'Week view needs a wider screen. Showing the agenda instead.'
		},

		/* --- The agenda ----------------------------------------------------- */
		agenda: {
			empty: 'Nothing in this range. Try showing more streams, or a different view.',
			/** The undated section. These rows exist nowhere else in the app. */
			undatedTitle: 'No date',
			undatedHint: 'to-dos you never dated',
			/** How far ahead the list looks, stated so the range is not a guess. */
			rangeNote: (days: number) => `the next ${days} days`
		},

		/* --- The key, which is also the filter ------------------------------ */
		key: {
			headingId: 'calendar-key',
			title: 'Key',
			/** Sits inline before the title, lowercase. */
			prefix: 'show',
			/** The count beside the title. A value, so it renders numeric. */
			hiddenCount: (count: number) => `${count} hidden`,
			showAll: 'show all',
			hideAll: 'hide all',
			/** The two dimensions, named. They are never one list. */
			streams: 'streams',
			labels: 'labels',
			/** Says what a stream chip will do, since the chip itself is one word. */
			streamToggle: (stream: string, on: boolean) =>
				on ? `Hide ${stream}` : `Show ${stream}`,
			labelToggle: (label: string, on: boolean) =>
				on ? `Hide items labelled ${label}` : `Show items labelled ${label}`,
			doneItems: 'done items',
			urgentOnly: 'urgent only',
			ignoredEvents: 'ignored events',
			/** Shown only when there are some, so flipping it has a visible effect. */
			ignoredCount: (count: number) => `(${count})`,
			allHidden: 'Everything is hidden — nothing will show below.'
		},

		/* --- The detail dialog ---------------------------------------------- */
		detail: {
			headingId: 'item-detail-title',
			close: 'Close',
			/** Says what the dialog is about, since the heading is just a title. */
			dialogLabel: (title: string) => `Details for ${title}`,
			/** The control on a row that opens it. One word would name every row alike. */
			open: (title: string) => `Details for ${title}`,
			allDay: 'all day',
			urgent: 'urgent',
			/** Field labels in the read half. Each names a value beside it. */
			course: 'course',
			priority: 'priority',
			editEyebrow: 'edit',
			labelField: 'label',
			labelPlaceholder: 'none',
			markUrgent: 'Mark urgent',
			/** Why the urgent control is disabled. Stated, not just greyed out. */
			urgentDisabled: 'Done items are never urgent.',
			addToCalendar: 'Add to calendar',
			/** The download is unavailable on a row with no instant — a class rule. */
			noInstant: 'This one repeats weekly, so there is no single date to export.',
			delete: 'Delete',
			/*
			 * The second step. Destructive and irreversible -- there is no undo slot
			 * for a deleted event -- so it asks, and the question names the thing
			 * rather than saying "are you sure".
			 */
			deleteConfirm: (title: string) => `Delete “${title}”? This cannot be undone.`,
			deleteGoAhead: 'Delete for good',
			deleteKeep: 'Keep it',
			deleted: (title: string) => `“${title}” deleted`,
			/*
			 * The standing promise, on the one surface where a student is typing
			 * things into a browser and could reasonably assume otherwise.
			 */
			localOnlyLabel: 'Local only.',
			localOnly:
				'Labels, urgent flags and anything you add here are stored in this browser. Nothing is sent anywhere and nobody is notified.'
		},

		/* --- Adding to a day ------------------------------------------------ */
		add: {
			/** Collapsed to one button until wanted, the same shape as Home's. */
			open: 'Add to this day',
			eyebrow: 'add',
			cancel: 'Cancel',
			kindLegend: 'What kind',
			/** The three kinds. The hint says what each one MEANS, not what it does. */
			kindTask: 'task',
			kindTaskHint: 'work with a deadline',
			kindTodo: 'to-do',
			kindTodoHint: 'a scratch item',
			kindEvent: 'event',
			kindEventHint: 'something happening',
			titleField: 'Title',
			titlePlaceholder: 'What is it?',
			timeField: 'at',
			labelField: 'label',
			labelPlaceholder: 'optional',
			markUrgent: 'Mark urgent',
			/** Names the kind, because the button IS the routing decision. */
			submit: (kind: string) => `Add ${kind}`,
			/** Where it went. Confirming the STORE is the point: three kinds, three lists. */
			addedTask: (title: string) => `“${title}” added to your tasks`,
			addedTodo: (title: string) => `“${title}” added to your to-do list`,
			addedEvent: (title: string) => `“${title}” added to this day`
		},

		/* --- The events section --------------------------------------------- */
		events: {
			headingId: 'calendar-happening',
			title: 'Happening',
			/**
			 * A locator, not an instruction.
			 *
			 * "register" read as a verb attached to the title — "register Happening".
			 * The prefix says which slot this is; the buttons say what to do.
			 */
			prefix: 'optional',
			joinedCount: (joined: number, total: number) => `${joined}/${total} joined`,
			empty: 'Nothing to sign up for this day.',
			/* The register vocabulary itself is `common.events` — Home renders the
			   identical words for the identical act, against the same store. Only
			   un-ignore is calendar-only: Home is a recommendation feed, so a
			   dismissal there is permanent by design. */
			unIgnore: 'Un-ignore'
		}
	},

	/* --- Appointments ------------------------------------------------------ */
	appointments: {
		documentTitle: 'Appointments',
		eyebrow: 'appointments',
		title: 'Book time with someone',
		/**
		 * Names the window, because the calendar's grey days otherwise look like a
		 * bug rather than a rule.
		 */
		/**
		 * Names the window, because a five-day strip otherwise looks like an
		 * accident rather than a rule.
		 */
		intro:
			'Book time with academic advising or career coaching. Times shown are the next five business days.',

		/** The two services. Keyed by `Advisor.service`. */
		serviceLabel: {
			advising: 'Academic Advising',
			career: 'Career Coaching'
		},

		card: {
			/**
			 * The words AFTER the figure, so the figure itself can take the numeric
			 * face. Splitting it here keeps the plural in this file rather than
			 * leaving a component to slice the number back out of a finished phrase.
			 */
			openTimesSuffix: (count: number) =>
				count === 1 ? 'open time this week' : 'open times this week',
			noOpenTimes: 'No open times this week',
			book: 'Book',
			/** The pressed state's label. Says what is happening, not what to do. */
			booking: 'Booking',
			/** Screen-reader tail, so three identical buttons are distinguishable. */
			bookWith: (name: string) => ` with ${name}`
		},

		/** The day chips. Each says its own state; there is no legend. */
		days: {
			legend: 'Pick a day',
			/** Relative words win where they apply; past that, the weekday is clearer. */
			today: 'Today',
			tomorrow: 'Tomorrow',
			/**
			 * The count under a chip's date.
			 *
			 * Kept from the month-grid work, which is the one thing worth keeping from
			 * it: a chip that says "4 free" tells a student where to look before they
			 * press anything, where the original strip made them select a day to find
			 * out it was empty.
			 */
			openCount: (count: number) => (count === 1 ? '1 free' : `${count} free`),
			/** The word after the figure, so the figure can take the numeric face. */
			openCountSuffix: (_count: number) => 'free',
			/** A published day whose slots are all taken. Said, not implied. */
			fullyBooked: 'Full',
			/** Spoken name for a chip, so the count is not read as a bare number. */
			dayLabel: (weekday: string, date: string, state: string) =>
				`${weekday} ${date}, ${state}`,
			/** Every published day is full. Not an error — just a full week. */
			empty: 'Nothing open in the next five business days.'
		},

		/** The clickable month under "Your day". */
		monthBrowser: {
			headingId: 'appointments-month',
			title: 'Your month',
			/**
			 * Says what a click DOES.
			 *
			 * This replaced "A reference while you book. Nothing here is clickable." --
			 * a caption explaining why an affordance does not work, which is a losing
			 * argument against a grid full of dots.
			 *
			 * Kept rather than dropped now that "Your day" sits directly beneath this
			 * grid instead of above it. The line no longer has to make up for a result
			 * that lands off-screen -- but this page has two day-shaped things on it,
			 * and naming the one that moves is still worth a line.
			 */
			note: 'Pick a day to see what is on it, below.',
			seeCalendar: 'Open the full calendar'
		},

		panel: {
			headingId: 'booking-heading',
			/** Names the service, since two cards can open this panel. */
			heading: (service: string) => `Book ${service.toLowerCase()}`,
			subheading: (name: string) => `with ${name} · 30 minutes`,
			close: 'Close booking panel',

			modeLegend: 'Meeting type',
			modeAny: 'Any',
			modeInPerson: 'In person',
			modeZoom: 'Zoom',

			timesLegend: 'Available times',
			/**
			 * Names the day the times belong to.
			 *
			 * The chips sit directly above, so this is confirmation rather than
			 * orientation — but a column of bare clock times with no date above it is
			 * a column that could be any day, and the chip's own selected state is a
			 * fill rather than a sentence.
			 */
			timesFor: (day: string) => `on ${day}`,
			/** Two dead ends, and they are not the same dead end. */
			noTimesForFilter: 'Nothing open that day with this meeting type. Try Any, or another day.',
			noDaySelected: 'Pick a day on the calendar to see what is open.',
			/** Spoken tail on a slot chip, so "taken" is not carried by a strikethrough. */
			slotMode: (mode: string) => ` ${mode}`,
			slotTaken: ', already taken',
			takenTitle: 'Already taken',

			reasonLabel: 'What do you want to talk about?',
			reasonPlaceholder: 'A sentence is plenty. It helps them prepare.',
			reasonCount: (used: number, max: number) => `${used}/${max}`,

			confirm: 'Confirm booking',
			confirming: 'Booking…',
			/** The live line beside the button: what is about to happen. */
			pickTime: 'Pick a time to continue.',
			selected: (day: string, time: string, mode: string) => `${day} at ${time}, ${mode}`
		},

		confirmed: {
			headingId: 'booking-confirmed',
			heading: 'You’re booked',
			line: (day: string, time: string, name: string) => `${day} at ${time} with ${name}.`,
			/** The reason, quoted back, so a student can see what was recorded. */
			reasonQuote: (reason: string) => `“${reason}”`,
			/**
			 * The standing promise. THRIVE never writes to a real calendar, and this
			 * is the surface where a student would most reasonably assume it had.
			 */
			note: 'It is on your THRIVE calendar and listed under your appointments. Nothing was written to a real calendar and nobody was notified.',
			done: 'Done',
			addToCalendar: 'Add to calendar',
			/** The .ics event's title. Names the role, not just the person. */
			icsTitle: (role: string, name: string) => `${role} with ${name}`
		},

		myDay: {
			headingId: 'my-day',
			title: 'Your day',
			todayChip: 'today',
			/**
			 * Neutral, because this pane now answers two questions.
			 *
			 * It used to read "Nothing booked this day. Any time works." -- true and
			 * useful while the only way to change the day was to pick a booking chip.
			 * Now the month grid can point it at any day at all, including days nobody
			 * is trying to book, and "any time works" about next Thursday is an offer
			 * the page cannot make. This says the state and stops.
			 */
			empty: 'Nothing scheduled this day.',
			/**
			 * The exclusion, stated rather than left to be noticed.
			 *
			 * This pane shows classes and appointments only. An assignment due at
			 * 11:59pm does not block a 2pm meeting, so listing deadlines here would
			 * make a free afternoon look busy -- but a student who knows they have
			 * work due needs to be told why it is absent.
			 */
			scope: 'Classes and booked time only. Deadlines are not shown here — they do not occupy an hour.'
		},

		list: {
			headingId: 'my-appointments',
			title: 'Your appointments',
			upcoming: (count: number) => `${count} upcoming`,
			empty: 'Nothing booked yet. Pick a service above to find a time.',
			cancel: 'Cancel',
			cancelling: 'Cancelling',
			cancelSubject: (when: string) => ` appointment on ${when}`,
			/** "Tue, Aug 12 at 9:30 AM". Built on the server. */
			whenLabel: (date: string, time: string) => `${date} at ${time}`,
			advisorLine: (name: string, role: string) => `${name} · ${role}`,
			/**
			 * Stands in when an appointment's advisor cannot be resolved. Not
			 * reachable with the mock fixtures; the row is kept rather than dropped
			 * if it ever is, so a booking never silently disappears.
			 */
			unknownAdvisor: 'Advisor'
		},

		/** Failures a student can actually hit. All three are states, not crashes. */
		errors: {
			noSlot: 'Pick a time first.',
			gone: 'That appointment is no longer on file.',
			/**
			 * The catch-all, and it exists because of a real silent no-op.
			 *
			 * The first form submission in this app came back 403 -- SvelteKit's CSRF
			 * check, because `adapter-node` had no `ORIGIN` to compare against. The
			 * `enhance` handler treated anything that was neither a success nor a
			 * `fail()` as "nothing to say", so the button visibly did NOTHING: no
			 * confirmation, no error, no console message a student would ever see.
			 *
			 * A press that produces no response is this repo's worst failure mode.
			 * Every branch of the callback now ends in something on screen.
			 */
			unexpected: 'Something went wrong on our end. Nothing was booked — try again.',
			/** Session lapsed server-side between page render and form submit. */
			signedOut: 'Your session has ended. Refresh to sign in again.'
		},

		disclaimer:
			'This is a prototype. Bookings are held in THRIVE only. Nothing is written to your calendar, and no one is notified.'
	},

	/* --- Career -------------------------------------------------------------- */
	jobs: {
		documentTitle: 'Career',
		eyebrow: 'career',
		title: 'Your career feed',
		intro:
			"Postings from top company job boards, ranked against your resume. Upload your resume once and every job gets a personal match score -- like the ones you want, dismiss the rest, and apply on the company's site.",

		search: {
			label: 'Job title, company, or skill',
			placeholder: 'e.g. Data Analyst',
			button: 'Search'
		},

		/** Which of the two dead ends a student is looking at. Never both. */
		empty: {
			noQuery: 'Search above to see postings.',
			/** Says the query back, so a typo is obvious rather than a mystery. */
			noResults: (query: string) => `No postings match “${query}”. Try different words.`
		},

		/**
		 * The feed's three tabs and their counts, and the three dead ends a tab
		 * can land on.
		 *
		 * Counts are functions rather than a template at the call site, same
		 * reasoning as `benchmark.sampleSize` below: a translation may want the
		 * number placed differently around the word.
		 */
		feed: {
			tabsLabel: 'Job feed tabs',
			tabs: {
				recommended: (n: number) => `Recommended (${n})`,
				liked: (n: number) => `Liked (${n})`,
				all: (n: number) => `All (${n})`
			},

			empty: {
				noJobsAtAll: 'No postings in this feed yet. Check back after the next ingest run.',
				/** Says the query back, same reasoning as `empty.noResults` above. */
				noMatchesForQuery: (query: string) =>
					`No postings match “${query}”. Try different words.`,
				likedTabEmpty:
					'No liked postings yet. Like one from Recommended or All and it will show up here.'
			},

			card: {
				/** The ring's accessible name -- the visual is decorative without it. */
				ringLabel: (score: number) => `Match score, ${score} out of 100`,
				/** Shown under the ring when the score is the search estimate rather
				 *  than a generated report. */
				estimatedMatch: 'Estimated match',
				skillsHave: 'Skills you have',
				skillsBuild: 'Skills to build',
				posted: (date: string) => `Posted ${date}`,
				like: 'Like',
				liked: 'Liked',
				dismiss: 'Dismiss',
				restore: 'Restore',
				apply: 'Apply on company site',
				/** Spoken tail, since the link text alone does not say where it opens. */
				applyTail: ', opens in a new tab',
				getReport: 'Get AI match report'
			}
		},

		/**
		 * The resume panel, in its two shapes.
		 *
		 * Both post to the SAME `?/upload` action -- the backend keeps only the
		 * latest upload and deletes the rest, so there is no separate "replace"
		 * endpoint to call, only different copy over the same form depending on
		 * whether a resume is already on file.
		 */
		profileBanner: {
			/** No resume yet -- the prominent banner. */
			message: 'Upload your resume to rank results against your skills.',
			fileLabel: 'Resume file',
			upload: 'Upload resume',
			uploading: 'Uploading…',
			/** The guard before the file ever reaches the server. */
			empty: 'Choose a file first.',
			/** The provider failing for a reason nobody has thought about. */
			error: 'Something went wrong uploading your resume. Try again.',

			/** A resume is already on file -- the compact row that keeps upload reachable. */
			hasResume: {
				message: 'Your feed is personalized to your uploaded resume.',
				fileLabel: 'Replace resume (PDF)',
				upload: 'Replace resume',
				uploading: 'Replacing…',
				/** Says plainly what the backend does, so a re-upload is never a surprise. */
				note: 'Uploading a new resume replaces the previous one and refreshes every match score.'
			}
		},

		benchmark: {
			headingId: 'jobs-benchmark-heading',
			heading: 'What this role typically asks for',
			/*
			 * A function rather than a template at the call site, same reasoning as
			 * every other count in this file: the sample size is a fact a translation
			 * may want to place differently around the count.
			 */
			sampleSize: (n: number) =>
				n === 1 ? 'Based on 1 posting like this one.' : `Based on ${n} postings like this one.`,
			empty: 'Not enough postings yet to show what this role typically asks for.'
		},

		card: {
			matchScore: 'Match score',
			skillsHave: 'Skills you have',
			skillsBuild: 'Skills to build',
			/** The card's whole accessible name, since the title alone repeats. */
			posted: (date: string) => `Posted ${date}`
		},

		/** An id with no posting behind it. A stale link, not a crash. */
		notFound: 'That job posting is not on file.',

		detail: {
			skillsHeading: 'Skills this posting asks for',
			/** Matches `feed.card.apply` -- one phrase for the one external link. */
			viewPosting: 'Apply on company site',
			/** Spoken tail, since the link text alone does not say where it opens. */
			viewPostingTail: ', opens in a new tab'
		},

		report: {
			headingId: 'jobs-report-heading',
			heading: 'How you match up',
			generate: 'Generate match report',
			generating: 'Generating…',
			/** 409: nothing to score against yet. */
			noResume: 'Upload a resume first to generate a match report.',
			/** 503: the report service, not the posting, is the problem. */
			unavailable: 'The match report service is unavailable right now. Try again shortly.',
			matchedHeading: 'Skills you have',
			gapsHeading: 'Skills to build',
			/** Neither a `fail()` nor a success -- must still say something. */
			unexpected: 'Something went wrong generating your report. Try again.',
			/** Keyed by `JobCompetency`, so a fifth value is a compile error here. */
			competencyLabels: {
				strong: 'Strong match',
				good: 'Good match',
				stretch: 'Stretch',
				reach: 'Reach'
			}
		},

		errors: {
			/** Session lapsed server-side between page render and form submit. */
			signedOut: 'Your session has ended. Refresh to sign in again.'
		}
	},

	/* --- Ask THRIVE -------------------------------------------------------- */
	ask: {
		documentTitle: 'Ask THRIVE',
		eyebrow: 'ask thrive',
		title: 'Ask a question',
		/**
		 * Names the split, and says the honest thing about it in the same breath.
		 *
		 * The two destinations exist because they will be wired to different
		 * material, and a student choosing between them deserves to know that none of
		 * them can answer yet rather than finding out one question in.
		 */
		intro:
			'Two places to ask, depending on what you need. None of them are connected to real material yet — the saved conversations below are examples of what this will hold.',

		/**
		 * The live counterpart of `intro`, shown once the backend is actually
		 * answering.
		 *
		 * Same split as everywhere else `live` gates copy: the mock sentence is a
		 * disclaimer that nothing is connected, and leaving it up once something IS
		 * connected would be a lie the student has no way to catch.
		 */
		introLive:
			"Two places to ask, depending on what you need. Answers come from the program's own material — conversations are saved to your account.",

		/**
		 * Keyed by `AskDestination`, so a destination missing its copy is a compile
		 * error here rather than a blank panel on screen. `AskDestination` still
		 * includes `"career"` for the backend career bot (see `$lib/ask`'s note on
		 * `ASK_DESTINATIONS`), so its entry stays even though the sub-tab that once
		 * showed it is gone -- `ChatWindow` can only ever be handed the two
		 * destinations the UI still routes to.
		 *
		 * Each carries a `blurb` for the rail and a full empty state, because an
		 * empty chat box tells a student nothing about what this particular
		 * destination knows. The examples are the useful part: they are the shape of
		 * question that belongs here, which is faster to read than a description of
		 * the shape of question that belongs here.
		 */
		destinations: {
			resources: {
				label: 'Resources',
				blurb: 'Program material and policy',
				emptyHeading: 'Ask about how the program works',
				emptyBody:
					'Handbooks, policies, deadlines, and who owns which decision. This one answers from the program’s own material rather than from the open web.',
				examples: [
					'What happens if I drop a course after week 2?',
					'Who has to approve a petition?',
					'Where do I request a laptop for the quarter?'
				]
			},
			courses: {
				label: 'Course Recommender',
				blurb: 'Classes and electives',
				emptyHeading: 'Ask which classes fit where you are going',
				emptyBody:
					'Electives, sequencing, and what a quarter will actually cost you in hours. Say what you are aiming at and it can be specific.',
				examples: [
					'Which electives suit product analytics?',
					'Can I take experimentation and data engineering together?',
					'Does auditing a course count toward the degree?'
				]
			},
			career: {
				label: 'Career',
				blurb: 'Job search and interviews',
				emptyHeading: 'Ask about the job search',
				emptyBody:
					'Applications, interviews, offers, and the awkward conversations in between. Bring the specific situation rather than the general question.',
				examples: [
					'How do I answer the salary question in a first screen?',
					'Is two pages too long for my resume?',
					'How do I follow up after a rejection?'
				]
			}
		},

		rail: {
			label: 'Ask THRIVE sections',
			destinationsHeading: 'Ask about',
			historyHeading: 'Saved conversations',
			/** Scoped to the destination, because that is what the list shows. */
			historyEmpty: 'Nothing saved here yet.',
			historyLabel: 'Saved conversations',
			/** Names the count beside a title so the figure is not bare. */
			messageCount: (count: number) => (count === 1 ? '1 message' : `${count} messages`),
			newConversation: 'New conversation',
			/** The rail's own accessible name for a history entry. */
			openConversation: (title: string, when: string) => `${title}, ${when}`
		},

		history: {
			today: 'Today',
			yesterday: 'Yesterday'
		},

		chat: {
			/** Names the log region. A bare "log" tells a screen reader nothing. */
			logLabel: (destination: string) => `${destination} conversation`,
			composerLabel: 'Ask a question',
			placeholder: 'Type your question…',
			send: 'Send',
			/**
			 * Spoken prefixes, so who said what does not rest on which side of the
			 * column a bubble sits on.
			 */
			youSaid: 'You said: ',
			thriveSaid: 'THRIVE said: ',

			/**
			 * The reply, and it says plainly that it cannot answer.
			 *
			 * A placeholder that mimics a real answer teaches a student to trust
			 * something that is not there. Same decision the floating assistant made,
			 * and the same wording problem: this has to sound like a limitation
			 * rather than a failure, because it is one.
			 */
			placeholderReply:
				'I can’t answer this yet. I’m not connected to the program’s material, your courses, or the career team — this page is the container, and the answers arrive when the retrieval service does.',

			/**
			 * Said BEFORE anything is typed, not after.
			 *
			 * The composer works and the exchange is real on screen, but it lives in
			 * this tab and nothing else. A student who found that out by navigating
			 * away would reasonably read it as having lost something.
			 */
			notSaved: 'Nothing you type here is saved yet. Leaving this page clears it.',
			/** The heading over an exchange that only exists in this tab. */
			draftHeading: 'This session',

			/**
			 * Shown as a THRIVE-side bubble while a live send is in flight.
			 *
			 * A bubble rather than a spinner: the log's `role="log"` /
			 * `aria-live="polite"` pair already announces new bubbles, so this rides
			 * the same channel a real reply will use instead of needing a second one.
			 */
			pendingReply: 'Thinking…',

			/**
			 * A live send that failed. The student's own bubble stays on screen above
			 * this one -- the draft is never lost, because it is not a draft any more,
			 * it is a message already rendered.
			 */
			errorReply:
				'Something went wrong sending that. Your message is shown above — try again in a moment.'
		},

		/** A destination or a conversation that does not exist. */
		notFound: {
			destination: 'There is no such section of Ask THRIVE.',
			conversation: 'That conversation is not on file.'
		}
	},

	/** Event origin tags. One per EventType. */
	eventTypes: {
		career: 'Career',
		rady: 'Rady',
		club: 'Club',
		ucsd: 'UCSD',
		sandiego: 'San Diego'
	},

	/** Standing, as a word. Mirrors `standingLabel` in format.ts. */
	standing: {
		onTrack: 'On track',
		watch: 'Watch',
		needsHelp: 'Needs help'
	},

	/**
	 * The navigation rail and bottom bar.
	 *
	 * The disclosure's labels say what pressing will DO, not which way the chevron
	 * points -- the same rule the task checkbox follows. A student who cannot see
	 * the rotation gets the verb.
	 */
	nav: {
		expandGroup: (label: string) => `Show ${label} sections`,
		collapseGroup: (label: string) => `Hide ${label} sections`
	},

	/** Names the scroll region a capped card becomes on desktop. */
	cards: {
		scrollRegion: (section: string) => `${section}, scrollable`
	}
} as const;
