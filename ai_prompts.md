# AI-assisted development: structured summary

This is an edited summary of the development requests and resulting decisions, not a verbatim transcript or a claim that these exact prompts were used. Informal exchanges are omitted. It does not replace the full prompt history requested in the assessment.

**Assistant:** OpenAI Codex desktop  
**Model selector label:** GPT 6 Astra (confirmed by the candidate)  
**Tools:** shell execution, file editing, web research, browser inspection, and GitHub integration  
**Collaboration:** one assistant; no subagents

## 1. Requirements and scope

**Objective:** Implement a lightweight, three-participant experiment for electing a Decision Maker.

- Use React, Python/FastAPI, PostgreSQL, and Docker Compose.
- Configure the three conditions through YAML: three humans, two humans and one agent, or one human and two agents.
- Use neutral participant labels and keep participant types out of the client-facing state.
- Prioritize a working experiment, understandable rules, and a reproducible local setup.
- Examine related experiment platforms as references; implement the assessment independently.

**Decision:** Separate experiment rules from the HTTP/WebSocket adapter and React interface. Use simulated agents for a keyless demonstration. No code was copied from the researched repositories.

## 2. Session lifecycle and timing

**Objective:** Make every stage explicit and prevent inactivity from blocking completion indefinitely.

1. Wait for all required human seats to be filled and ready.
2. Run round 1: 60-second discussion, then a ballot lasting up to 30 seconds.
3. Display aggregate round 1 feedback for 8 seconds.
4. Run round 2: 60-second discussion, then a ballot lasting up to 30 seconds.
5. Combine the two rounds' votes and determine whether a tie-break is needed.
6. Display a shared result with the reason for the outcome.

**Decision:** The server owns deadlines and phase transitions. Missing votes count as abstentions; silence does not extend a phase. Waiting expires after 300 seconds. Both main rounds use the same configured discussion and voting durations.

## 3. Election and tie-breaking

**Objective:** Give both main ballots a role and avoid arbitrary winner selection.

- Add round 1 and round 2 votes with equal weight.
- Allow self-votes in the two main ballots.
- If cumulative leaders tie, hold a 30-second discussion and a ballot lasting up to 30 seconds.
- Restrict tie-ballot candidates to the tied leaders; all three participants may vote, but self-votes are prohibited.
- Resolve a remaining tie using round 2 support, then round 1 support, then capped participation counts.
- If the evidence remains equal, return an inconclusive result rather than selecting randomly.

**Trade-off:** The conditional third discussion extends the brief's two-round flow. Participation is an observable activity proxy, not a validated measure of leadership. These choices are disclosed to participants and documented in the README.

## 4. Participant guidance

**Objective:** Make the experiment understandable without an external facilitator.

**Shared question:** “What would make someone a good Decision Maker, and who in your group best fits those qualities?”

- Explain the election rules before participants confirm readiness.
- Show the current round, stage, remaining time, and required action.
- Support free-text discussion and editable quick-reply suggestions.
- Explain cumulative totals and the final selection criteria.

## 5. Agent behaviour and revision

**Objective:** Avoid immediate, repetitive agent messages that dominate the discussion.

**Observed issue:** Candidate feedback identified overly fast contributions and an agent speaking without meaningful interaction.

**Revision:** Schedule contributions with a 12–24 second delay, limit each agent to two contributions per discussion, and require new peer input before a follow-up. Responses use simple keyword matching to reference public discussion. Election winners are never randomized.

**Limitation:** These are rule-based simulations, not live LLMs. Their wording and timing can still reveal their nature. Interface blinding does not establish that humans cannot identify an agent.

## 6. Network identity and security

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

**Objective:** Persist experiment data and keep all participants consistent.

**Implementation:** PostgreSQL 16, accessed through SQLAlchemy and psycopg. The `experiment_sessions` table stores a session ID and JSON snapshot containing configuration, messages, ballots, transition history, and results.

- Commit state changes before broadcasting them to participants.
- Use a Docker volume so records survive container recreation.
- Restore a participant's seat and current state after browser reconnection.
- Mark unfinished sessions as interrupted after a server restart while retaining their records.

**Trade-off:** JSON snapshots keep the assessment compact. A larger study would benefit from normalized event storage and transcript pagination. The server runs as one process because connection routing and timers are in memory.

## 8. Verification and delivery

**Objective:** Make the application runnable on a computer without Node.js, Python, or PostgreSQL installed.

**Delivery:** Docker Desktop or Docker Engine with Compose is the prerequisite. Start the full stack with:

```sh
docker compose up --build -d --wait
```

**Evidence:** The clean Docker build, HTTP/database health checks, and all 18 tests passed in [GitHub Actions](https://github.com/bilal-younus/common-ground-experiment/actions/runs/45812784461). Integration tests exercised all three participant compositions against PostgreSQL using HTTP and authenticated WebSockets.

**Debugging example:** Browser testing exposed an invalid React effect cleanup caused by returning `scrollIntoView`'s result. The effect was corrected, the frontend rebuilt, and reconnect/results checked again.

**Effort disclosure:** No complete active-effort stopwatch record exists. This summary does not claim a verified four-hour total.
