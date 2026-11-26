# Verification record

Implementation date: 26 November 2026.

- React/Vite production build passed.
- Initial pure-rule suite: 14 passed.
- Initial full suite against a real, isolated PostgreSQL 16 database: 17 passed (all three participant compositions).
- Browser: created a session, joined two independent human tabs, confirmed readiness, observed synchronized phases and automated messages, cast both rounds' human ballots, verified identical final cumulative results, refreshed and recovered the same seat/results.
- Browser testing found a React effect cleanup bug from returning the result of scrollIntoView. Changed the effect to return nothing; rebuilt and verified the resumed session and results.
- User feedback identified overly rapid/predictable agent messages. Replaced fixed rapid contributions with delayed, bounded, peer-dependent responses. Added a regression test for minimum response delay and no repeated monologue.
- Docker was initially unavailable on the development Mac; native verification is recorded below. GitHub Actions successfully built and started the complete Docker stack from a clean Ubuntu runner, checked HTTP/database health, and ran the rule and PostgreSQL/WebSocket integration suite inside the app container. Evidence: https://github.com/bilal-younus/common-ground-experiment/actions/runs/45812784461 (source commit d0a9b85f9405893caf27516dabb7045834782ba7).
- Browser-level IP switching was not performed. Authentication does not use IP, and token reconnect was tested.
- User confirmed the model selector label as GPT 6 Astra (Codex desktop). Total active effort remains unverified; see ai_prompts.md.

Final verification after pacing changes:
- 18 tests passed against PostgreSQL (15 rule tests + 3 complete condition flows), in 26.27 seconds. One dependency deprecation warning from Starlette/AnyIO; no failing checks.
- React production rebuild passed after changing chat autoscroll to scroll only the transcript pane.
- Browser quick-reply test: selected Fairness, verified editable composer text, submitted it, observed identical delivery in the other tab. The agent subsequently referenced that message after a delay, then stayed silent without additional peer input.

Participant-guide revision:
- Moved question and rules below the main workspace; replaced the long opening rules with a three-step guide and expandable details. Checked the waiting-room layout in the browser.
- Added six editable round-two discussion shortcuts and round-one totals available during the second ballot. Candidate choices remain the three participants.
- Added seven regression cases covering AI assignment to each label and agent voting for humans/self across all rounds. All 22 rule tests passed; React production build passed.
- Seat types were already shuffled. Agent votes favour capped current-round message counts; self-votes are possible in main rounds but prohibited in the tie-break. Neither behaviour was silently changed.

Third-round verification and question alignment:
- Added five real PostgreSQL/WebSocket integration scenarios that reach round three through submitted ballots: tie-ballot winner, round-two support fallback, participation fallback, exact draw, and silent tie ballot timeout.
- Each checks shared results, reconnect, persisted results/history, and third-round entry. Non-silent cases deliberately submit prohibited self-votes and verify rejection before casting valid ballots.
- Full local suite: 30 passed in 63.47 seconds; one dependency deprecation warning. React build passed.
- Moved the question into the sidebar beside the participant workspace; detailed rules remain below and aligned with the workspace. Browser layout inspected.

Native macOS Docker verification (26 November 2026):
- Installed Docker Desktop 4.99.0 on Apple Silicon macOS 26.3.1. Engine 29.9.3; Compose v5.7.0.
- Tested a fresh public-repository checkout at commit dd06302, without a host virtual environment, node_modules, or frontend build output.
- The first build encountered a Docker registry authorization/download timeout. Retrying the same command succeeded without project changes.
- Ran the documented `docker compose up --build -d --wait`; both services became healthy. HTTP health and the React page returned successfully on localhost:8000.
- All 30 tests passed inside the macOS-hosted Docker app container against a separate PostgreSQL test database, in 65.26 seconds. One dependency deprecation warning.
- Homebrew's optional system link step required an administrator password; installed the official app directly and completed CLI links instead. The README command was then verified without temporary PATH overrides.
- Windows Docker Desktop has not been directly tested.
