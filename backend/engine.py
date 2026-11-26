"""Pure experiment rules. All transitions/actions are called under the server lock."""
import hashlib
import re
import random
import secrets
import time
import uuid
from collections import Counter
from pathlib import Path

import yaml

LABELS = ['Player A', 'Player B', 'Player C']
TERMINAL = {'results', 'expired', 'interrupted'}
QUICK_REPLIES = [
    'A good Decision Maker listens to everyone before choosing.',
    'A good Decision Maker explains the reasons behind their choice.',
    'A good Decision Maker weighs different views fairly.',
    'What would you do if the group disagrees with your decision?',
]


def load_config(path):
    c = yaml.safe_load(Path(path).read_text())
    if not isinstance(c, dict):
        raise ValueError('Configuration must be a mapping')
    kinds = c.get('participants', [])
    if len(kinds) != 3 or any(x not in ('human', 'ai') for x in kinds) or kinds.count('human') not in (1, 2, 3):
        raise ValueError('Use exactly three participants, including at least one human')
    for key in ('discussion_seconds', 'voting_seconds', 'feedback_seconds', 'waiting_seconds', 'tie_discussion_seconds', 'tie_voting_seconds', 'agent_min_delay_seconds', 'agent_max_delay_seconds'):
        if type(c.get(key)) is not int or not 1 <= c[key] <= 3600:
            raise ValueError(f'{key} must be an integer from 1 to 3600')
    if c['agent_min_delay_seconds'] > c['agent_max_delay_seconds']:
        raise ValueError('Agent minimum delay must not exceed maximum delay')
    if c.get('ai_mode') != 'simulated':
        raise ValueError('This minimal build supports ai_mode: simulated only')
    if not isinstance(c.get('question'), str) or not 1 <= len(c['question']) <= 1000:
        raise ValueError('Provide a question of 1–1000 characters')
    return c


def new_room(config, now=None):
    now = time.time() if now is None else now
    kinds = list(config['participants'])
    secrets.SystemRandom().shuffle(kinds)  # Assignment only; elections never use randomness.
    return dict(id=uuid.uuid4().hex[:12], config=config.copy(), phase='waiting', round=0,
                deadline=now + config['waiting_seconds'], version=0, created=now,
                players=[dict(id=i, label=label, kind=kinds[i], token_hash=None, ready=kinds[i] == 'ai') for i, label in enumerate(LABELS)],
                messages=[], votes={'1': {}, '2': {}, '3': {}}, history=[], candidates=[0, 1, 2],
                result=None, bot_sent={}, bot_due={}, bot_peer_seen={}, last_message={})


def identify(room, token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    return next((p['id'] for p in room['players'] if p['token_hash'] and secrets.compare_digest(p['token_hash'], digest)), None)


def join(room):
    if room['phase'] != 'waiting':
        raise ValueError('This session has already started or closed.')
    p = next((p for p in room['players'] if p['kind'] == 'human' and p['token_hash'] is None), None)
    if p is None:
        raise ValueError('All seats are reserved. Open your existing participant tab to reconnect.')
    token = secrets.token_urlsafe(32)
    p['token_hash'] = hashlib.sha256(token.encode()).hexdigest()
    return token


def transition(room, phase, seconds, now):
    room['phase'] = phase
    room['deadline'] = now + seconds if seconds else None
    room['history'].append(dict(phase=phase, round=room['round'], at=now))


def totals(room, rounds=(1, 2)):
    counts = Counter(int(v) for r in rounds for v in room['votes'][str(r)].values())
    return {str(i): counts[i] for i in range(3)}


def participation(room):
    # Transparent proxy, not semantic leadership scoring. Repetition/spam earns no extra points.
    seen = {}
    for m in room['messages']:
        normalized = re.sub(r'\W+', ' ', m['text'].lower()).strip()
        if len(normalized) >= 20:
            seen.setdefault((m['player'], m['round']), set()).add(normalized)
    return {str(i): sum(min(3, len(seen.get((i, r), set()))) for r in (1, 2, 3)) for i in range(3)}


def leaders(scores, eligible):
    top = max(scores[str(i)] for i in eligible)
    return [i for i in eligible if scores[str(i)] == top]


def finish(room, winner, reason, now, trace=None):
    room['result'] = dict(winner=winner, reason=reason, trace=trace or [],
                          totals=totals(room), participation=participation(room))
    transition(room, 'results', 0, now)


def resolve_main(room, now):
    t = totals(room)
    if sum(t.values()) == 0:
        finish(room, None, 'No main-round votes were received. No election can be inferred.', now)
        return
    tied = leaders(t, [0, 1, 2])
    if len(tied) == 1:
        finish(room, tied[0], 'Highest combined vote total across rounds 1 and 2.', now)
    else:
        room['candidates'] = tied
        room['round'] = 3
        transition(room, 'discussion', room['config']['tie_discussion_seconds'], now)


def resolve_tie(room, now):
    eligible = room['candidates'][:]
    trace = []
    criteria = [('Tie-break votes', totals(room, (3,))),
                ('Round 2 support', totals(room, (2,))),
                ('Round 1 support', totals(room, (1,))),
                ('Discussion participation', participation(room))]
    for name, scores in criteria:
        eligible = leaders(scores, eligible)
        trace.append(dict(criterion=name, scores=scores, remaining=eligible[:]))
        if len(eligible) == 1:
            finish(room, eligible[0], f'Selected by {name.lower()} after a cumulative tie.', now, trace)
            return
    finish(room, None, 'Still tied after the tie-break ballot, previous support and participation. No random selection was made.', now, trace)


def advance(room, now):
    phase, r, c = room['phase'], room['round'], room['config']
    if phase == 'waiting':
        transition(room, 'expired', 0, now)
    elif phase == 'discussion':
        transition(room, 'voting', c['tie_voting_seconds'] if r == 3 else c['voting_seconds'], now)
    elif phase == 'feedback':
        room['round'] = 2
        transition(room, 'discussion', c['discussion_seconds'], now)
    elif phase == 'voting':
        if r == 1:
            transition(room, 'feedback', c['feedback_seconds'], now)
        elif r == 2:
            resolve_main(room, now)
        else:
            resolve_tie(room, now)


def apply(room, player, action, now=None):
    now = time.time() if now is None else now
    if room['deadline'] is not None and now >= room['deadline']:
        raise ValueError('This phase has ended. Wait for the latest session state.')
    kind = action.get('type')
    if kind == 'ready' and room['phase'] == 'waiting':
        room['players'][player]['ready'] = True
        if all(p['ready'] for p in room['players']):
            room['round'] = 1
            transition(room, 'discussion', room['config']['discussion_seconds'], now)
        return
    if action.get('round') != room['round']:
        raise ValueError('That action belongs to an earlier round.')
    if kind == 'message' and room['phase'] == 'discussion':
        raw = action.get('text')
        if not isinstance(raw, str):
            raise ValueError('Message must be text.')
        text = raw.strip()
        if not 1 <= len(text) <= 500:
            raise ValueError('Use 1–500 characters.')
        if now - room['last_message'].get(str(player), -100) < 2:
            raise ValueError('Please wait two seconds between messages.')
        room['messages'].append(dict(id=len(room['messages']) + 1, player=player, round=room['round'], text=text, at=now))
        room['last_message'][str(player)] = now
        return
    if kind == 'vote' and room['phase'] == 'voting':
        candidate = action.get('candidate')
        if type(candidate) is not int or candidate not in room['candidates']:
            raise ValueError('Choose an eligible candidate.')
        if room['round'] == 3 and candidate == player:
            raise ValueError('Self-votes are not allowed in the tie-break.')
        ballots = room['votes'][str(room['round'])]
        if str(player) in ballots:
            raise ValueError('Your vote is already recorded and cannot be changed.')
        ballots[str(player)] = candidate
        if len(ballots) == 3:
            advance(room, now)
        return
    raise ValueError('That action is not available in the current phase.')


def agent_step(room, now):
    """Bounded rule-based agents: neutral identities, human-paced replies, no private ballots."""
    if room['phase'] not in ('discussion', 'voting'):
        return False
    changed = False
    phase, r = room['phase'], room['round']
    c = room['config']
    duration = (c['tie_discussion_seconds'] if r == 3 else c['discussion_seconds']) if phase == 'discussion' else (c['tie_voting_seconds'] if r == 3 else c['voting_seconds'])
    started = room['deadline'] - duration
    for p in room['players']:
        if p['kind'] != 'ai' or room['phase'] != phase or room['round'] != r:
            continue
        pid = p['id']
        key = f'{r}:{phase}:{pid}'
        if key not in room['bot_due']:
            # Pacing randomness is unrelated to election decisions: no random winner selection.
            delay = random.uniform(c['agent_min_delay_seconds'], c['agent_max_delay_seconds']) if phase == 'discussion' else random.uniform(1, min(8, max(1, duration * .6)))
            room['bot_due'][key] = started + delay
            changed = True
        if now < room['bot_due'][key] or now >= room['deadline']:
            continue
        if phase == 'discussion':
            n = room['bot_sent'].get(key, 0)
            if n >= 2:
                continue
            peers = [m for m in room['messages'] if m['player'] != pid and m['round'] == r]
            other = peers[-1] if peers else None
            # At most one unsolicited opening. Further replies require a new peer contribution.
            if n and (not other or other['id'] <= room['bot_peer_seen'].get(key, 0)):
                continue
            if other and now < other['at'] + c['agent_min_delay_seconds']:
                continue
            if other:
                content = other['text'].lower()
                label = LABELS[other['player']]
                if 'disagree' in content or 'objection' in content:
                    text = f"{label}, I would ask each person for a reason, then explain what changed my mind."
                elif 'listen' in content:
                    text = f"I agree with {label} about listening. We should also leave time to actually choose."
                elif 'fair' in content:
                    text = f"{label}, fairness matters to me too. How would you balance two different preferences?"
                elif 'reason' in content or 'explain' in content:
                    text = f"{label}, a clear reason would help me trust the choice, even if I preferred another option."
                else:
                    text = f"{label}, what would you do if someone felt their view had been overlooked?"
            else:
                text = ['I would want someone who listens before deciding.',
                        'For me, explaining the choice matters more than sounding confident.',
                        'I think fairness matters. What quality would you put first?'][pid]
            try:
                apply(room, pid, dict(type='message', text=text, round=r), now)
                room['bot_sent'][key] = n + 1
                room['bot_peer_seen'][key] = other['id'] if other else 0
                room['bot_due'][key] = now + random.uniform(c['agent_min_delay_seconds'], c['agent_max_delay_seconds'])
                changed = True
            except ValueError:
                pass
        elif str(pid) not in room['votes'][str(r)]:
            options = [i for i in room['candidates'] if r != 3 or i != pid]
            counts = Counter(m['player'] for m in room['messages'] if m['round'] == r)
            candidate = max(options, key=lambda i: (min(3, counts[i]), -((i - pid - r) % 3)))
            apply(room, pid, dict(type='vote', candidate=candidate, round=r), now)
            changed = True
    return changed


def view(room, player, now=None):
    r = room['round']
    # Explicit allowlist: never serialize configuration, token hashes, kinds or private ballots.
    return dict(id=room['id'], phase=room['phase'], round=r, deadline=room['deadline'],
                server_time=time.time() if now is None else now, version=room['version'],
                you=player, players=[dict(id=p['id'], label=p['label']) for p in room['players']],
                ready=room['players'][player]['ready'], question=room['config']['question'],
                durations={k:room['config'][k] for k in ('discussion_seconds','voting_seconds','tie_discussion_seconds','tie_voting_seconds')},
                messages=room['messages'], candidates=room['candidates'],
                voted=str(player) in room['votes'].get(str(r), {}),
                round_one=totals(room, (1,)) if room['phase'] == 'feedback' or r >= 2 else None,
                result=room['result'],
                ballot_counts={key:len(value) for key,value in room['votes'].items()} if room['phase'] == 'results' else None,
                quick_replies=QUICK_REPLIES)
