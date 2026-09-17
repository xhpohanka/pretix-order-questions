# pretix-order-questions

Adds configurable questions that are asked once per order in the pretix contact-information step,
instead of once for every ticket.

Supported question types:

- one-line and multiline text,
- yes/no,
- single choice,
- multiple choice.

Answers are stored in dedicated `OrderAnswer` records linked directly to the pretix `Order`. They
are shown in both the control panel and the customer-facing order detail and stay available when a
question is disabled. Questions and their options are copied when an event is cloned.
Each question can additionally opt in to showing its answer in POS order detail;
leave that off for customer data staff do not need at the terminal.

## Installation

Install the package in the same environment as pretix, run the standard Django migrations and
enable **Order questions** for the event. Questions can then be configured under
**Settings → Order questions**.
