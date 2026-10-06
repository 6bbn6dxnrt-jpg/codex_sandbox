# Local Wealth Poland

Production pipeline for a reproducible research dataset of Polish local-government asset declarations.

## Design
RAW -> BRONZE -> SILVER -> GOLD -> PANEL -> ANALYTIC

**Unit of analysis:** person × role × filing obligation × economic date. A PDF is evidence, not an observation.

## Primary window
2020–2025. Earlier years may be ingested as robustness/history.

## Success metric
Representative, correctly structured, auditable person-years per unit time, subject to quality gates.

## Privacy
This public repository contains code/configuration only. Source declarations, extracted personal data and derived row-level datasets must not be committed here.

## First benchmark
Run an end-to-end heterogeneous pilot before national scaling. Measure discovery coverage, download success, document class, extraction quality, expensive-model routing, cost and person-years/hour.
