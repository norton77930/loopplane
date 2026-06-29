# Contract: Schedules And Model Defaults

## Purpose

Define the additive contract for schedule management and host-provided model default selection.

## Scope

This contract covers:

- schedule list/get/write/delete;
- schedule enable/disable;
- schedule run-now;
- model default list/get/set;
- host catalog validation.

It does not cover distributed scheduling, plan mode, budget policy, provider setup, or browser-side provider credential entry.

## Schedule Summary

A schedule summary includes:

- `id`
- `name`
- `description`
- `trigger`
- `enabled`
- `status`
- `next_run_at`
- `last_run_at`
- `problem`

Status values:

- `enabled`
- `disabled`
- `running`
- `invalid`
- `failed`
- `deleted`

## Schedule Operations

### List Schedules

Request: authenticated list.

Response: schedules visible to the current principal.

### Get Schedule

Request: authenticated get by schedule id.

Response: schedule detail when owned or readable.

### Write Schedule

Request: create or update a schedule.

Required input:

- `name`
- `trigger`
- `enabled`
- target action metadata accepted by the host.

Response: public-safe operation result plus refreshed schedule summary.

### Delete Schedule

Request: delete by schedule id with explicit confirmation.

Response: public-safe operation result.

### Run Schedule Now

Request: run one owned schedule immediately.

Response: operation result with `running`, `enabled`, `disabled`, `invalid`, or `failed` state.

## Model Defaults

### List Available Models

Response: host-provided model catalog entries that can be selected as defaults.

### Get Default Model

Response:

- selected model id when available;
- fallback or unavailable state when no selection is valid.

### Set Default Model

Request: select one model id from the host catalog.

Response: updated model default state.

## Rules

- Browser UI must not render fields for provider credential entry.
- A model id not present in the host catalog is rejected.
- Removed models become unavailable or fallback without blocking other capability settings.
- Schedule failures use public-safe messages.

## Compatibility Requirements

- Existing 074 per-session model selection remains available.
- A model default may prefill future draft sessions but does not mutate existing sessions.
- Schedule management is additive and can be disabled without removing existing chat/session behavior.
