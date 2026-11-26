# Common Ground

A three-participant decision-making experiment built with React, FastAPI WebSockets and PostgreSQL. Participants discuss a shared question, cast two cumulative ballots, and see an explained outcome. Quick replies are editable suggestions alongside free text.

## Start from a clean computer

**You do not need Node.js, npm, Python, pip or PostgreSQL installed.** Docker builds React in a Node container, installs Python dependencies in the app container, and starts PostgreSQL in its own container.

1. Install [Docker Desktop](https://docs.docker.com/get-docker/) for macOS/Windows/Linux and start it. On Linux, Docker Engine plus the [Compose v2 plugin](https://docs.docker.com/compose/install/) also works. Docker is the one prerequisite; this project does not silently install system software or change machine settings.
2. Download this repository using **Code → Download ZIP** and extract it. Git is optional.
3. Open Terminal (macOS/Linux) or PowerShell (Windows) in the extracted folder containing `compose.yml`.
4. Run this one command:

```sh
docker compose up --build -d --wait
```

5. Open **http://localhost:8000** after both services are healthy.

For beginner-friendly prerequisite checks, use `sh start.sh` on macOS/Linux or `powershell -File .\start.ps1` on Windows. These wrappers run the same Docker command. If Windows policy blocks scripts, use the direct Docker command; no policy change is necessary.

The first build downloads images and packages and may take several minutes. Subsequent starts reuse Docker's cache. No paid API account, key, environment file or manual database setup is needed. Local port **8000** must be free.

### Try the experiment

Create a session, copy its invitation link, and open it in independently opened browser tabs/profiles for the human participants. Each human reads the rules and clicks **I understand · I’m ready**. The default is **two humans + one simulated agent**: open the same invitation in two independent tabs and participate in both. To try alone, change YAML to `[human, ai, ai]` before creating a new room.

Avoid duplicating an existing participant tab: browsers can copy its session storage and therefore its identity. Independently opened tabs receive separate seats. Refreshing a tab restores its seat.

The shared question, phase, countdown, quick replies, vote confirmation and tie-break criteria are explained in the interface. A quick reply fills the composer so you can edit it before sending.

### Stop, restart and troubleshoot

- Stop: `docker compose down`. Saved sessions remain in the database volume.
- Start again: `docker compose up -d --wait`.
- After source changes: `docker compose up --build -d --wait`.
- Diagnostics: `docker compose logs --tail=100`.
- If Docker cannot connect: open Docker Desktop and wait until the engine is running.
- If port 8000 is occupied: stop that service, or change the left-hand port in `compose.yml`, e.g. `127.0.0.1:8080:8000`, and visit port 8080.
- Do not use `docker compose down -v` unless you intend to erase this project's saved experiment data.

The app binds to this computer only. Testing with remote participants requires a separate hosting/security plan. No third-party assets are loaded by the app after startup.

## Change the condition

Edit `config.yml`:

```yaml
participants: [human, human, human] # 3 humans
# participants: [human, human, ai]  # 2 humans + 1 agent
# participants: [human, ai, ai]     # 1 human + 2 agents
```

Configuration is validated when a new room is created. Each session stores its own snapshot, so editing YAML does not alter an ongoing experiment. Seat labels are shuffled independently of participant type. Election outcomes never use random selection.

The experiment always has **two main rounds**; there is no separate round-count setting. The following table includes all configurable YAML keys.

| Setting | Default | Meaning |
|---|---:|---|
| participants | `[human, human, ai]` | Session composition; exactly three seats |
| discussion_seconds | 60 | Discussion in round 1 AND round 2 (60 seconds each) |
| voting_seconds | 30 | Ballot in round 1 AND round 2 (up to 30 seconds each) |
| feedback_seconds | 8 | First-round aggregate feedback |
| waiting_seconds | 300 | Maximum time to assemble/ready the group |
| tie_discussion_seconds | 30 | Conditional tie discussion |
| tie_voting_seconds | 30 | Tie ballot |
| agent_min_delay_seconds | 12 | Minimum agent contribution/reply delay |
| agent_max_delay_seconds | 24 | Maximum sampled scheduling delay |
| question | See YAML | Shared discussion question |
| ai_mode | simulated | Only mode implemented in this build |

**Default flow:** Waiting room → round 1 discussion (60s) → round 1 vote (up to 30s) → feedback (8s) → round 2 discussion (60s) → round 2 vote (up to 30s) → results, or conditional tie discussion (30s) and tie vote (up to 30s) → results.

Maximum active duration under defaults: 248 seconds including first-round feedback and the conditional tie-break, excluding the waiting room. Missing participation never extends a deadline.

## Election rules

1. Two discussion rounds, each followed by one irreversible ballot. Self-voting is allowed in these rounds.
2. Sum rounds 1 and 2 equally. Round 1 totals are shown before the second discussion; individual ballots remain private. Changing preference in round 2 does not erase the first vote.
3. A unique cumulative leader wins. If no main ballots exist, the outcome is inconclusive.
4. A cumulative tie triggers a bounded extra discussion and ballot: only tied leaders are eligible; all three participants vote; self-votes are prohibited.
5. If that ballot ties, restrict the remaining candidates successively by **round 2 support**, **round 1 support**, then **participation**. Earlier totals cannot break a cumulative tie by themselves; recency is the explicit additional preference.
6. Participation is the number of distinct normalized contributions of at least 20 characters, capped at three per participant per discussion. Quick replies count; duplicate text in the same discussion and very short messages do not. This is a transparent activity proxy, **not a validated leadership measure**. It can favour verbosity and does not evaluate substantive quality. All criteria are disclosed before participation.
7. If all measures still tie, show an inconclusive outcome. Never fabricate a winner or use random selection.

The conditional third discussion is a deliberate extension to the brief's two-round flow, requested during design. It is used only for ties. If strict two-round compliance is required, this extension must be reconsidered before submission.

Silence is valid observation. Missing votes are abstentions. Partial ballots count without a quorum requirement, and results show how many were received. Humans are not silently replaced with agents.

## Agent behaviour and blinding

Agents are explicitly **rule-based simulations, not live LLMs**. They sample a 12–24 second contribution delay, make at most two contributions per discussion, and do not continue a monologue after their opening. Further contributions require new peer discussion and wait at least the configured minimum reply delay. Simple keyword responses reference a peer's published message. Short tie discussions may therefore contain fewer agent messages.

Agents vote using capped current-round public contribution counts, with a deterministic identity/round-based ordering for equal scores. They do not inspect private ballots or other participants' types. This policy is a reproducible demonstration, not evidence of human-like reasoning. Timing/wording may still let people guess identity. The agent policy itself can affect experimental results, especially when participation is an election fallback; it must be reported as part of the condition.

WebSocket snapshots use an explicit allowlist: no type flags, raw configuration, private ballots or tokens. Connection badges describe only the viewer's connection. The app does not reveal AI identities in the UI. The source/YAML are researcher-visible, so this is interface blinding rather than protection against a participant who inspects the public repository or controls the server.

## Architecture and failure behaviour

```text
React participant views
        | HTTP join + authenticated WebSocket frames
FastAPI: one process, server deadlines, serialized mutations
        | persist before broadcast
PostgreSQL: one JSON snapshot row per session
```

- `backend/engine.py`: configuration validation, election rules, agent policy, public-view construction. No network or database dependencies in rule execution.
- `backend/main.py`: HTTP/WebSocket adapter, token authentication, persistence and scheduler.
- `frontend/src/main.jsx`: participant flow and reconnecting client.
- `backend/tests/`: rule tests and opt-in real-PostgreSQL integration tests.

A private 256-bit token identifies a seat; only its SHA-256 hash is stored in the database. It is sent in the first WebSocket frame, not a URL. Browser session storage restores the seat after refresh/network changes. **IP addresses are not participant identifiers and are not stored in the experiment records.** Uvicorn's local operational access logs may contain connecting IPs. This is not a one-person-one-seat enforcement system.

The server derives sender identity from the token. Votes, candidate eligibility, phase and round are checked server-side. Old-round messages/votes and actions after a deadline are rejected. Text is limited to 500 characters with a two-second per-seat message interval. React renders messages as text.

State changes are copied, committed atomically to PostgreSQL, then broadcast. Snapshots contain the full configuration, timestamped messages, ballots, transition history and result explanation. This intentionally simple schema is suitable for a small assessment; larger studies would normalize events and paginate transcripts. No researcher export endpoint is exposed to participants.

One process is required because connection routing, timers and locks are in memory. Browser reconnects restore state; **server restarts mark unfinished sessions interrupted**, retaining their records instead of pretending timers and participation were uninterrupted. Completed sessions can still be revisited using their existing tokens. Database outages reject uncommitted actions; a scheduler failure is logged and retried. This is a local demonstration, not a hardened public multi-tenant service.

## Tests

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
cd frontend
npm ci
npm run build
```

Integration tests require a separate disposable PostgreSQL database with `chm_test` in its name:

```sh
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/chm_test \
  PYTHONPATH=backend .venv/bin/pytest backend/tests -q
```

They exercise all three compositions through HTTP joins and authenticated WebSockets, timers, messages, ballots, shared results, reconnection and actual database persistence. They create synthetic test sessions; do not point them at a study database.

For development, set `DATABASE_URL`, run `.venv/bin/uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1`, then run `npm run dev` inside `frontend`. Vite proxies HTTP and WebSocket requests. A built frontend is also served directly by FastAPI.

## AI process and verification

See `ai_prompts.md` for the edited development summary and confirmed model label (GPT 6 Astra, using Codex desktop). It is not a verbatim prompt log; the assessment’s full-history requirement remains outstanding with this edited version. See `VERIFICATION.md` for actual test evidence and remaining checks. Earlier planning happened across multiple days; no complete active-effort stopwatch record exists, so this project does **not claim a verified four-hour total**. Confirm actual effort before submission.

No repository was copied. Design references: [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/), [Docker Compose readiness](https://docs.docker.com/compose/how-tos/startup-order/), [GRAIL](https://github.com/microsoft/group_ai_lab) and [CHM Simple Chat](https://github.com/center-for-humans-and-machines/simple-chat). References informed discussion; this source was authored for the assessment.

Only publish this `experiment-platform` directory, not its parent folder containing the CV and application documents. Private recruitment correspondence is redacted from the public prompt log. Repository publication does not send the submission email; that is a separate action.
