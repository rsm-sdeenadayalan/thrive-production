export class SlotUnavailableError extends Error {
  constructor(message = "That time was just taken. Pick another.") {
    super(message);
    this.name = "SlotUnavailableError";
  }
}
