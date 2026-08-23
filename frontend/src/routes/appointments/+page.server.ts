import { fail } from "@sveltejs/kit";

import {
	REASON_MAX,
	toAppointmentView,
	toBookingDayViews,
	type AppointmentView,
	type ServiceView,
	type SlotView,
} from "$lib/appointmentsView";
import {
	availabilityByDay,
	openSlotCount,
	orderedDayKeys,
	publishedByDay,
} from "$lib/availability";
import { buildScheduleData } from "$lib/buildSchedule";
import { apiEnabled } from "$lib/data/api/client";
import {
	bookAppointment,
	cancelAppointment,
	getAdvisors,
	getMyAppointments,
	getSlots,
	SlotUnavailableError,
} from "$lib/data";
import { formatTime } from "$lib/format";
import { messages } from "$lib/messages";
import { addDays, dayKeyOf } from "$lib/schedule";
import type { Actions, PageServerLoad } from "./$types";

/**
 * The booking surface's data, and every date decided here.
 *
 * ## One clock read
 *
 * `new Date()` is called ONCE and two things come off it: the day a chip calls
 * "Today" and the one it calls "Tomorrow". The calendar page calls `todayKey()`
 * and gets a second internal read; this page passes the instant it already has
 * to `dayKeyOf` instead, which is the same string from one read rather than two
 * microseconds apart.
 *
 * There is deliberately no `nowISO` here. Nothing on this page is editable in
 * the sense CONVENTIONS' narrowed exception covers -- a booking is created and
 * cancelled through an action, not moved in `localStorage` -- so no component
 * needs an instant to reclassify against.
 *
 * ## Advisors first, then everything else
 *
 * `getSlots` needs an advisor id, so the fan-out cannot join the same
 * `Promise.all` as the call that produces the ids. Two awaits, and the second
 * one is parallel across advisors and the two independent reads.
 */
export const load: PageServerLoad = async () => {
	const advisors = await getAdvisors();

	const [slotsByAdvisor, appointments, data] = await Promise.all([
		Promise.all(advisors.map((advisor) => getSlots(advisor.id))),
		getMyAppointments(),
		buildScheduleData(),
	]);

	const now = new Date();
	const todayKey = dayKeyOf(now);

	/*
	 * Tomorrow, for a chip's relative label, derived from the SAME instant.
	 * `addDays` walks local parts, so this is one calendar day later even across a
	 * DST boundary -- which an elapsed-milliseconds addition would not be.
	 */
	const tomorrowKey = addDays(todayKey, 1);

	const services: ServiceView[] = advisors.map((advisor, index) => {
		const slots: SlotView[] = slotsByAdvisor[index].map((slot) => ({
			id: slot.id,
			advisorId: slot.advisorId,
			// `dayKeyOf`, never `toISOString().slice(0, 10)`: a 4pm slot would land
			// on the following day anywhere behind UTC, and the day list would offer
			// a day the times column had nothing for.
			dayKey: dayKeyOf(slot.start),
			timeLabel: formatTime(slot.start),
			mode: slot.mode,
			available: slot.available,
			startISO: slot.start,
			endISO: slot.end,
		}));

		const openByDay = availabilityByDay(slots);
		/*
		 * Both maps, because a chip has to tell "fully booked" apart from "not a day
		 * this advisor works". Open counts alone cannot: both are zero, and there is
		 * no chip at all for a day nobody works.
		 */
		const published = publishedByDay(slots);
		const dayKeys = orderedDayKeys(published);

		return {
			advisor,
			serviceLabel: messages.appointments.serviceLabel[advisor.service],
			slots,
			openByDay,
			/*
			 * The chips, formatted here. Three of their five fields are
			 * locale-formatted dates and the fourth is relative to today, so building
			 * them on the server leaves the strip with no opinion about the calendar
			 * at all -- and means this page appears nowhere on CONVENTIONS' list of
			 * accepted client-side date formats.
			 */
			days: toBookingDayViews(
				openByDay,
				published,
				dayKeys,
				todayKey,
				tomorrowKey,
			),
			/*
			 * Every open slot, because the published set IS the window now. There is
			 * no separate month-ahead rule for a card to contradict.
			 */
			openCount: openSlotCount(slots),
		};
	});

	const advisorById = new Map(advisors.map((advisor) => [advisor.id, advisor]));

	const appointmentViews: AppointmentView[] = appointments.map((appointment) =>
		toAppointmentView(appointment, advisorById.get(appointment.advisorId)),
	);

	return {
		services,
		appointments: appointmentViews,
		/**
		 * The student's own schedule, for the "Your day" strip. Classes arrive as
		 * weekday RULES, which is what lets it answer for any day in the window
		 * without another round trip.
		 */
		data,
		/** The day the strip marks "Today" and the pane may chip as today. */
		todayKey,
	};
};

/**
 * Booking and cancelling, as form actions.
 *
 * ## Why forms rather than a fetch from a click handler
 *
 * The Next version called server actions imperatively out of `useTransition`.
 * The SvelteKit shape is form-first, and taking it buys three things: `load`
 * re-runs automatically after a successful action, which is what makes a fresh
 * booking appear in "Your day" and in the list below with no manual refresh and
 * no client-side cache to keep honest; the cancel button on each row works with
 * no JavaScript at all; and the pending state is one boolean around one await
 * rather than React's concurrent primitive, which has no Svelte equivalent
 * (MIGRATION.md section 8.4).
 *
 * ## Errors are values, not throws
 *
 * `SlotUnavailableError` is caught here and returned through `fail`. Two people
 * CAN want the same slot -- the page a student is looking at was rendered before
 * somebody else took it -- so a taken slot is an ordinary outcome the panel has
 * to render, not a crash. Anything else re-throws, because a provider failing
 * for a reason we have not thought about should not be reported to a student as
 * a booking problem.
 *
 * ## Auth check, gated on the API being live
 *
 * Both actions now guard first: no `locals.student` while `apiEnabled()` is
 * true fails the action with 401 rather than letting a direct POST reach the
 * provider with no session -- MIGRATION.md section 9 defect 2, closed for the
 * Django path. On the mock path there is still no session to check against,
 * so the guard is a no-op there, same as before.
 */
export const actions: Actions = {
	book: async ({ request, locals }) => {
		if (apiEnabled() && !locals.student) {
			return fail(401, { error: messages.appointments.errors.signedOut });
		}

		const form = await request.formData();
		const slotId = String(form.get("slotId") ?? "");
		/*
		 * Truncated here, not just in the textarea. `maxlength` is a courtesy to
		 * the person typing; this is the limit. See `REASON_MAX`.
		 */
		const reason = String(form.get("reason") ?? "").slice(0, REASON_MAX);

		if (!slotId) {
			return fail(400, { error: messages.appointments.errors.noSlot });
		}

		try {
			const appointment = await bookAppointment(slotId, reason);
			const advisors = await getAdvisors();
			const advisor = advisors.find(
				(candidate) => candidate.id === appointment.advisorId,
			);

			/*
			 * The whole view model comes back, not just an id. The confirmation
			 * panel renders the same object the list below it will render on the
			 * next load, through the same mapper -- so the two cannot disagree
			 * about when the meeting is or where it happens.
			 */
			return { booked: toAppointmentView(appointment, advisor) };
		} catch (error) {
			if (error instanceof SlotUnavailableError) {
				/*
				 * 409, and the data layer's own sentence.
				 *
				 * It throws two different messages -- "no longer listed" for a slot
				 * id that does not resolve, "just taken" for one that has been
				 * claimed -- and only the data layer knows which happened. Replacing
				 * both with one string from `messages` would flatten a real
				 * distinction, and recovering it here would mean matching on the
				 * message text, which is worse than passing it through.
				 */
				return fail(409, { error: error.message });
			}

			throw error;
		}
	},

	cancel: async ({ request, locals }) => {
		if (apiEnabled() && !locals.student) {
			return fail(401, { error: messages.appointments.errors.signedOut });
		}

		const form = await request.formData();
		const appointmentId = String(form.get("appointmentId") ?? "");

		const cancelled = await cancelAppointment(appointmentId);

		if (!cancelled) {
			// Not a throw: an id that is no longer on file is what a stale page
			// looks like, and a student can act on being told so.
			return fail(404, { error: messages.appointments.errors.gone });
		}

		return { cancelled: cancelled.id };
	},
};
