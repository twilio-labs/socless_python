Socless Core Library
===================

The Socless Core library contains functions used by the Socless automation framework to bootstrap its core components and integrations.



create_events call flow

1. `create_events` calls `EventBatch().create_events`
2. `EventBatch()` init ensures the event keys are the right types
3. `EventBatch().create_events` says for each event in details list:
   1.  format the event to a new structure and then call `EventCreator(new_event).create()`
   2.  `EventBatch().execute_playbook()` - step 7
4.  `EventCreator` init validates event key types
5.  `EventCreator` `.create()` calls `.deduplicate()` which interacts with DEDUP_TABLE and mutates the event
6.  `.create()` then formats the event and puts it into the EVENTS_TABLE
7.  `EventBatch().execute_playbook()` 
    1.  formats the playbook metadata (arn, investigation_id, input dict)
    2.  puts an item in the results table
    3.  starts stepFunctions with a subset of results item