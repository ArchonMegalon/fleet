# Fleet design-progress semantics feedback

Date: 2026-03-11
Audience: `fleet` maintainers
Status: injected feedback

The missing piece is now progress semantics.

Fleet can already answer:

* what is running
* what is blocked
* what is healing

It still does not answer:

* how far a group or project is from the intended design target

## Required distinction

Fleet must surface two different kinds of progress:

* `delivery_progress` - progress through currently dispatchable work
* `design_progress` - progress toward the intended end-state in milestones and uncovered scope

Queue exhaustion must never be mistaken for design completion.

## Suggested model

Add a computed `design_progress` object on every group and project with:

* `percent_complete`
* `percent_inflight`
* `percent_blocked`
* `percent_unmaterialized`
* `eta_human`
* `eta_confidence`
* `basis`
* `summary`

## Milestone registry improvements

Extend milestone and scope items with:

* `weight`
* `status`
* `owner_project`
* `design_area`
* `exit_tests_total`
* `exit_tests_passed`

## Dashboard direction

Main cockpit group cards should show one design-completeness bar.

Expanded group detail should add per-project:

* design-complete percent
* design ETA
* short summary
* top blocker
* uncovered scope count

The expanded view should show both:

* `Delivery`
* `Design`

so the operator can tell the difference between queue progress and true product progress.
