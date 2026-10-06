# Project Charter

## Objective
Build a national research infrastructure for public asset declarations of Polish local public officials, then use it for economic research.

## Role families
1. councillors;
2. mayors / city presidents / commune heads;
3. deputies, secretaries, treasurers;
4. heads of organisational units;
5. selected managers / decision-makers covered by disclosure rules.

## Non-negotiable measurement rules
- missing != 0; blank != "nie dotyczy";
- preserve literal source text separately from normalized values;
- principal != current loan balance;
- joint ownership is not automatically 50%;
- do not infer property address/location;
- new reporting != proven purchase; disappearance != proven sale;
- every field retains provenance and extractor version;
- production data need not be Gold; uncertainty must be measured, not hidden.

## Architecture
Census-like acquisition corpus + probability-based scientific sample + stratified Gold audit.

## Anti-stall rule
No single source/document may block independent jobs. Failed jobs receive error codes and move to retry/dead-letter queues.
