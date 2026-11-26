# How we used AI to build Common Ground

**Tool:** OpenAI Codex desktop  
**Model:** GPT 6 Astra  
**Format:** Prompts below are edited reconstructions of the conversation, paired with the decisions and work that followed.

## 1. Understand the problem before writing code

**Prompt**

> First, explain the complete problem to me. What are they expecting us to build, what are the required technologies, and which decisions have they left to us? Let's break it down before starting the implementation.

**What followed**

We identified the required three-person experiment, waiting room, two discussion rounds, voting, hidden participant types, and three YAML-configured conditions. React, FastAPI, a real database, and a one-command Docker setup were requirements. Tie-breaking, intermediate feedback, and agent behaviour needed our own decisions.

The early discussion focused on understanding those choices. It was not just a request to generate an application from the brief.

## 2. Research related projects and try existing demos

**Prompt**

> Let's go through the internet and find relevant projects, GitHub repositories, or existing platforms for this kind of human–AI experiment. Are any of them deployed so we can try the flow ourselves? Explain which examples are closest to our task and what we can learn from them.

**What followed**

The research brought related platforms and examples into the discussion:

- [oTree readymade demos](https://demo.on.otree.org/), including AI chat and group coordination examples.
- [GRAIL / Group AI Lab](https://github.com/microsoft/group_ai_lab).
- [CHM Simple Chat](https://github.com/center-for-humans-and-machines/simple-chat).

The candidate explored the oTree demo list and asked which example to select. The follow-up observation was that the visible interaction seemed simple: a chat box and choices for reaching a group decision. That prompted a closer look at what our assessment actually needed beyond a chat interface.

These were design references. The implementation was written for this assessment; no code was copied from those repositories. This record does not claim that every referenced project had a working deployed demo or that every demo was tested.

## 3. Spend time on the rules and awkward cases

**Prompt**

> Before we build, let's think through the rules properly. Who decides whether a session has two humans and one AI? What happens if people join but nobody chats or votes? Why do we have a first round if its votes do not affect the result? What happens if everyone votes for themselves? We also need to think about changing IP addresses and responses that make an AI too easy to recognise.

**What followed**

This discussion shaped the experiment:

- The researcher chooses the participant composition in YAML; participants do not choose or see their condition in the interface.
- Waiting, discussion, and voting have deadlines. Silence or missing votes cannot keep a session running indefinitely.
- Both main rounds contribute to the final vote total.
- Participant identity is tied to a private session token, not an IP address.
- Agent timing and repeated messages need attention as well as the text of each response.

We returned to the assessment brief during this stage to distinguish required behaviour from optional design choices.

## 4. Work through the tie-break instead of choosing randomly

**Prompt**

> I think both rounds should count. If there is a tie, let the tied candidates go into an extra discussion and vote, with self-voting banned. If it ties again, look at the earlier votes and then participation. But what happens if all that evidence is still equal? Let's make the rule clear before implementing it.

**What followed**

We settled on adding the two main ballots equally. A unique cumulative leader wins. A tie triggers one bounded extra discussion and a ballot between the tied leaders. All participants may vote, but nobody may vote for themselves in that ballot.

A remaining tie is narrowed using round 2 support, then round 1 support, then capped participation counts. If the evidence still does not distinguish a winner, the result is inconclusive. There is no random winner selection.

Two limitations matter: the extra discussion extends the brief's two-round flow, and speaking more is not proof of better leadership. Participation is only a disclosed activity proxy. The README explains the exact criteria.

## 5. Make the experience understandable and useful

**Prompt**

> How can we make this more thoughtful than a basic chat and vote page? The experiment should explain itself. Let's start with: “What would make someone a good Decision Maker, and who in your group best fits those qualities?” Time is short, so allow normal messages and quick choices that people can edit before sending.

**What followed**

The interface explains the rules before readiness, shows the current round and countdown, and provides editable quick replies alongside free text. Round 1 aggregate feedback gives participants something to consider before round 2. The result explains how the Decision Maker was selected.

The emphasis became a clear experiment flow and explainable decisions, rather than adding unrelated features.

## 6. Agree on the design, then build the core flow

**Prompt**

> Now let's implement what we discussed. Keep the required stack and make sure all three participant configurations work. Choose an agent approach that is suitable and quick to run. Keep the rules, question, tie-break, and reconnect behaviour consistent with the design.

**What followed**

The assistant implemented React for the participant interface, FastAPI for HTTP and WebSockets, and PostgreSQL 16 for persistence. Experiment rules live separately from the transport layer. The server controls deadlines and validates actions.

We chose rule-based simulated agents so the application runs without an API key. This was a pragmatic implementation choice, not a claim that simulated agents provide the same behaviour as live LLMs.

PostgreSQL stores a session ID and JSON snapshot containing configuration, messages, ballots, transition history, and results. Changes are committed before they are broadcast. A Docker volume retains the records. One server process keeps in-memory connection routing and timers simple.

## 7. Handle reconnects and keep private state private

**Prompt**

> Make sure a refresh or network change does not give someone a different identity. Participants should not be able to see who is an AI or submit actions as another player. Explain how identity and private information are handled, and keep the local setup simple.

**What followed**

The implementation uses a private 256-bit seat token stored in browser session storage. PostgreSQL stores its SHA-256 hash. The token is sent in the first WebSocket frame rather than the URL, and the server derives the sender's identity from it.

The server checks the round, phase, deadline, and eligible vote targets. Participant snapshots exclude type flags, token hashes, raw configuration, and private ballots. Messages have a 500-character limit and a two-second per-seat interval, and React renders them as text.

The app is bound to localhost, and PostgreSQL has no published host port. IP addresses are not stored in experiment records, although local server access logs may contain them.

These are local-demo protections. A token identifies a seat, not a verified person. Browser reconnect was tested; changing networks was not directly tested. Public internet deployment would need further security work. A server restart marks unfinished sessions interrupted while preserving their records.

## 8. Test the interaction and respond to feedback

**Prompt**

> One player is writing too quickly and seems to be talking alone. That makes it feel obviously like an AI. Slow the responses down and make them react to the conversation rather than keep posting by themselves.

**What followed**

Candidate feedback led to delayed agent contributions, with a sampled 12–24 second interval and at most two messages per discussion. Follow-ups require new peer input and wait at least the minimum response delay. Simple keyword matching lets a response refer to the discussion.

The agents remain simulations; pacing changes do not guarantee that participants cannot identify them.

Browser testing also exposed an invalid React effect cleanup caused by returning the result of `scrollIntoView`. The effect was corrected, the frontend rebuilt, and the resumed session and results checked again. Editable quick replies and delivery between participant tabs were also checked.

## 9. Make it easy to run and verify the full stack

**Prompt**

> Make sure we fulfil the technology requirements and that someone can start the project from scratch without installing Node packages themselves. Explain the setup clearly, test it, and push it to GitHub.

**What followed**

Docker builds the frontend, installs Python dependencies, and starts PostgreSQL. The host needs Docker with Compose, but does not need Node.js, Python, or PostgreSQL installed separately:

```sh
docker compose up --build -d --wait
```

The [GitHub Actions run](https://github.com/bilal-younus/common-ground-experiment/actions/runs/45812784461) successfully built and started the stack from a clean runner, checked app/database health, and passed all 18 tests. Integration tests exercised all three participant compositions through HTTP and authenticated WebSockets against real PostgreSQL, including shared results, reconnection, and persistence.

The source, YAML configuration, Docker setup, startup helpers, and verification notes were published to the public repository.

## Process notes

The conversation moved through research, rule design, implementation, user feedback, and verification. Some technical details were proposed by the assistant during implementation; the reconstructed prompts above combine those discussions for readability rather than attributing every detail to an original candidate prompt.

No subagents were used. No complete active-effort stopwatch record exists, so this record does not claim a verified four-hour total. The original conversation is needed to satisfy the assessment's request for all actual prompts.
