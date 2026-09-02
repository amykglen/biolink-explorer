// (Intentionally empty.)
//
// This previously cleared a dropdown's search box after each selection, to work around a
// dcc.Dropdown virtualization quirk where reopening a dropdown you'd typed-and-selected in
// could open at a too-short height. That was removed because clearing the filter is
// undesirable for multi-select: people often want to pick several options that match the
// same typed filter, and the text should stay put. The short-height-on-reopen quirk is a
// Dash internal issue we accept in exchange.
