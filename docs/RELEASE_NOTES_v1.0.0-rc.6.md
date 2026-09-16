# Harbor 1.0.0-rc.6

This release candidate lets a customer choose one verified newsletter source
for the ordinary scheduled and manual report. The existing default remains a
combined report from all connected sources.

## Changed

- Added a source selector to the customer schedule, so an account with Kit and
  Beehiiv can report on Kit alone without disconnecting Beehiiv.
- Made manual runs follow the same selected source as the schedule.
- Passed the selected source into legacy scheduled jobs and limited the Sprite
  run specification to that source. An unrelated Kit connection therefore does
  not receive an unnecessary run-scoped broker grant.
- Rejected unverified or cross-workspace source choices and kept invalid-source
  execution failures durable in run history.

The Kit OAuth consent and first real-data Kit report are still live acceptance
gates. This release candidate is not public-launch approval.
