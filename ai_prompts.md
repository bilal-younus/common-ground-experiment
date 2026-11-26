# AI-assisted development: structured summary

**Format:** Retrospectively reconstructed prompts, followed by implemented results.

**Assistant:** OpenAI Codex desktop  
**Model selector label:** GPT 6 Astra (confirmed by the candidate)  
**Tools:** shell execution, file editing, web research, browser inspection, and GitHub integration  
**Collaboration:** one assistant; no subagents

## 1. Requirements and scope

**Prompt**

> Build a minimal three-participant Decision Maker experiment using React, FastAPI, PostgreSQL, and Docker Compose. Support all three human/agent compositions through YAML. Separate experiment rules from transport and UI concerns. Review relevant platforms as references and document pragmatic scope choices.

**Result and rationale**

**Objective:** Implement a lightweight, three-participant experiment for electing a Decision Maker.

- Use React, Python/FastAPI, PostgreSQL, and Docker Compose.
- Configure the three conditions through YAML: three humans, two humans and one agent, or one human and two agents.
- Use neutral participant labels and keep participant types out of the client-facing state.
- Prioritize a working experiment, understandable rules, and a reproducible local setup.
- Examine related experiment platforms as references; implement the assessment independently.

**Decision:** Separate experiment rules from the HTTP/WebSocket adapter and React interface. Use simulated agents for a keyless demonstration. No code was copied from the researched repositories.

## 2. Session lifecycle and timing

**Prompt**

> Define a bounded session lifecycle with a waiting room, two timed discussions, and a ballot after each discussion. Explain how round 1 feedback informs round 2. Keep phase transitions authoritative on the server and specify what happens when participants remain silent or miss a ballot.

**Result and rationale**

**Objective:** Make every stage explicit and prevent inactivity from blocking completion indefinitely.

1. Wait for all required human seats to be filled and ready.
2. Run round 1: 60-second discussion, then a ballot lasting up to 30 seconds.
3. Display aggregate round 1 feedback for 8 seconds.
4. Run round 2: 60-second discussion, then a ballot lasting up to 30 seconds.
5. Combine the two rounds' votes and determine whether a tie-break is needed.
6. Display a shared result with the reason for the outcome.

**Decision:** The server owns deadlines and phase transitions. Missing votes count as abstentions; silence does not extend a phase. Waiting expires after 300 seconds. Both main rounds use the same configured discussion and voting durations.

## 3. Election and tie-breaking

**Prompt**

> Count votes from both main rounds. If cumulative leaders tie, add a bounded tie-break restricted to those candidates and prohibit self-votes. Use earlier voting evidence and participation as explicit fallback criteria. Do not select a random winner; explain any unresolved outcome and limitations of the participation metric.

**Result and rationale**

**Objective:** Give both main ballots a role and avoid arbitrary winner selection.

- Add round 1 and round 2 votes with equal weight.
- Allow self-votes in the two main ballots.
- If cumulative leaders tie, hold a 30-second discussion and a ballot lasting up to 30 seconds.
- Restrict tie-ballot candidates to the tied leaders; all three participants may vote, but self-votes are prohibited.
- Resolve a remaining tie using round 2 support, then round 1 support, then capped participation counts.
- If the evidence remains equal, return an inconclusive result rather than selecting randomly.

**Trade-off:** The conditional third discussion extends the brief's two-round flow. Participation is an observable activity proxy, not a validated measure of leadership. These choices are disclosed to participants and documented in the README.

## 4. Participant guidance

**Prompt**

> Make the experiment self-explanatory. Present the shared Decision Maker question, rules, phase, countdown, and next action. Combine free text with editable quick replies so participants can contribute within the short discussion window.

**Result and rationale**

**Objective:** Make the experiment understandable without an external facilitator.

**Shared question:** “What would make someone a good Decision Maker, and who in your group best fits those qualities?”

- Explain the election rules before participants confirm readiness.
- Show the current round, stage, remaining time, and required action.
- Support free-text discussion and editable quick-reply suggestions.
- Explain cumulative totals and the final selection criteria.

## 5. Agent behaviour and revision

**Prompt**

> Revise agent pacing: responses are too fast and an agent appears to be speaking alone. Introduce delayed contributions, limit message frequency, and make follow-ups depend on new peer input. Document whether agents are simulated or live LLMs and avoid overstating their realism.

**Result and rationale**

**Objective:** Avoid immediate, repetitive agent messages that dominate the discussion.

**Observed issue:** Candidate feedback identified overly fast contributions and an agent speaking without meaningful interaction.

**Revision:** Schedule contributions with a 12–24 second delay, limit each agent to two contributions per discussion, and require new peer input before a follow-up. Responses use simple keyword matching to reference public discussion. Election winners are never randomized.

**Limitation:** These are rule-based simulations, not live LLMs. Their wording and timing can still reveal their nature. Interface blinding does not establish that humans cannot identify an agent.

## 6. Network identity and security

**Prompt**

> Design participant identity independently of IP addresses so refreshes and network changes do not create a new seat. Explain token authentication, server-side action validation, and which fields participants may receive. Bound message size and frequency, isolate the database, and distinguish local-demo protections from production security.

**Result and rationale**

**Objective:** Preserve participant identity across refreshes and network changes without using an IP address as identity.

**Implemented decisions:**

- Identify each seat with a private, randomly generated 256-bit token; store only its SHA-256 hash in PostgreSQL.
- Keep the token in browser session storage and send it in the first WebSocket frame rather than in the URL.
- Derive the sender's identity on the server; validate the phase, round, vote eligibility, and deadline before accepting actions.
- Build participant snapshots from an explicit allowlist. Exclude participant types, token hashes, private ballots, and raw configuration.
- Limit chat messages to 500 characters and enforce a two-second per-seat message interval. Render messages as text.
- Bind the app's published port to localhost. Keep PostgreSQL on the internal Compose network without a published database port.
- Do not store IP addresses in experiment records. Local server access logs may still contain connecting IPs.

**Boundaries:** A token represents a seat, not a verified person. This implementation does not enforce one person per seat. Browser reconnect was tested; changing networks/IP addresses was not tested directly. Internet deployment would require additional transport security, abuse controls, and operational review.

## 7. Database and recovery

**Prompt**

> Use PostgreSQL for actual experiment persistence. Store configuration, messages, ballots, transitions, and results. Persist accepted mutations before broadcasting. Define recovery after browser disconnects and server restarts, and explain the storage and concurrency trade-offs.

**Result and rationale**

**Objective:** Persist experiment data and keep all participants consistent.

**Implementation:** PostgreSQL 16, accessed through SQLAlchemy and psycopg. The `experiment_sessions` table stores a session ID and JSON snapshot containing configuration, messages, ballots, transition history, and results.

- Commit state changes before broadcasting them to participants.
- Use a Docker volume so records survive container recreation.
- Restore a participant's seat and current state after browser reconnection.
- Mark unfinished sessions as interrupted after a server restart while retaining their records.

**Trade-off:** JSON snapshots keep the assessment compact. A larger study would benefit from normalized event storage and transcript pagination. The server runs as one process because connection routing and timers are in memory.

## 8. Verification and delivery

**Prompt**

> Provide a one-command Docker setup that does not require host Node.js, Python, or PostgreSQL. Verify the frontend build and all three participant compositions against a real database. Test synchronized results and reconnection, document debugging outcomes, and publish the implementation with reproducible setup instructions.

**Result and rationale**

**Objective:** Make the application runnable on a computer without Node.js, Python, or PostgreSQL installed.

**Delivery:** Docker Desktop or Docker Engine with Compose is the prerequisite. Start the full stack with:

```sh
docker compose up --build -d --wait
```

**Evidence:** The clean Docker build, HTTP/database health checks, and all 18 tests passed in [GitHub Actions](https://github.com/bilal-younus/common-ground-experiment/actions/runs/45812784461). Integration tests exercised all three participant compositions against PostgreSQL using HTTP and authenticated WebSockets.

**Debugging example:** Browser testing exposed an invalid React effect cleanup caused by returning `scrollIntoView`'s result. The effect was corrected, the frontend rebuilt, and reconnect/results checked again.

**Effort disclosure:** No complete active-effort stopwatch record exists. This summary does not claim a verified four-hour total.
