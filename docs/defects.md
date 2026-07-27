# Defects - Stars Ultranova Web

`[ ]` open, `[x]` fixed. Dated notes under each track how it evolved. Sources: functional browser harness (tests/functional/), LLM playtest forensics, wave verifiers.

## API

- [ ] `DEF-1` **waypoint task name asymmetry** - commands accept task 'LayMines' but player-state returns task_type 'LayMinesTaskObj' (Python class name leaks into the API); UI compensates in taskDisplayName but API consumers must handle both spellings; fix: normalize task_type serialization to the command vocabulary; `backend player-state serialization`
  - 2026-07-27 reported: reported by functional harness (test_fleet_waypoints)

## Client UI

- [ ] `DEF-2` **race wizard re-render loses in-flight input** - MEDIUM; every field change triggers full wizard re-render (updateField -> render), so typing Race Name then Plural Name loses the plural - first field's blur re-render resets the second input before its change commits; debounced /races/validate also briefly disables Save Race and can swallow the click; fix: re-render only derived sections or preserve focus/values; `frontend/js/views/race-wizard.js`
  - 2026-07-27 reported: reported by functional harness (test_race_designer, reproducible)
- [ ] `DEF-3` **empty turn report dialog every turn** - turn report dialog opens even with zero messages ('No messages this turn') forcing a dismiss each turn; cause: app.js checks only GameState.game where the comment says show-if-messages; fix: gate on message count; `frontend/js/app.js`
  - 2026-07-27 reported: reported by functional harness (test_turn_and_messages)

## Gameplay

- [ ] `DEF-4` **first-turn message drought** - LOW; first turns on seeds 1111/4242/5555/6666 produce no player messages at all so the message panel stays hidden after turn 1; first star-linked message appears only when production completes; assess whether canonical Stars! emits early-game messages (research, growth) and add if so; `backend/server/turn_generator.py`
  - 2026-07-27 reported: reported by functional harness (multiple seeds)
