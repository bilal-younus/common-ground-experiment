# Verification record

Implementation date: 26 November 2026.

- React/Vite production build passed.
- Initial pure-rule suite: 14 passed.
- Initial full suite against a real, isolated PostgreSQL 16 database: 17 passed (all three participant compositions).
- Browser: created a session, joined two independent human tabs, confirmed readiness, observed synchronized phases and automated messages, cast both rounds' human ballots, verified identical final cumulative results, refreshed and recovered the same seat/results.
- Browser testing found a React effect cleanup bug from returning the result of scrollIntoView. Changed the effect to return nothing; rebuilt and verified the resumed session and results.
- User feedback identified overly rapid/predictable agent messages. Replaced fixed rapid contributions with delayed, bounded, peer-dependent responses. Added a regression test for minimum response delay and no repeated monologue.
- Docker is unavailable on the development Mac. GitHub Actions successfully built and started the complete Docker stack from a clean Ubuntu runner, checked HTTP/database health, and ran the rule and PostgreSQL/WebSocket integration suite inside the app container. Evidence: https://github.com/bilal-younus/common-ground-experiment/actions/runs/45812784461 (source commit d0a9b85f9405893caf27516dabb7045834782ba7).
- Browser-level IP switching was not performed. Authentication does not use IP, and token reconnect was tested.
- User confirmed the model selector label as GPT 6 Astra (Codex desktop). Total active effort remains unverified; see ai_prompts.md.

Final verification after pacing changes:
- 18 tests passed against PostgreSQL (15 rule tests + 3 complete condition flows), in 26.27 seconds. One dependency deprecation warning from Starlette/AnyIO; no failing checks.
- React production rebuild passed after changing chat autoscroll to scroll only the transcript pane.
- Browser quick-reply test: selected Fairness, verified editable composer text, submitted it, observed identical delivery in the other tab. The agent subsequently referenced that message after a delay, then stayed silent without additional peer input.
