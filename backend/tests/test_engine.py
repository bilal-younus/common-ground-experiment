import copy
import json
from pathlib import Path
import pytest
from engine import *

BASE = load_config(Path(__file__).resolve().parents[2] / 'config.yml')


def room(kinds=None):
    c = copy.deepcopy(BASE)
    c['participants'] = kinds or ['human'] * 3
    return new_room(c, 100)


def start(r):
    for p in r['players']:
        if p['kind'] == 'human':
            token = join(r)
            apply(r, identify(r, token), {'type': 'ready'}, 101)


def vote_all(r, choices, now):
    for pid, choice in enumerate(choices):
        apply(r, pid, {'type':'vote', 'candidate':choice, 'round':r['round']}, now)


@pytest.mark.parametrize('kinds', [['human']*3, ['human','human','ai'], ['human','ai','ai']])
def test_all_conditions_wait_and_start(kinds):
    r=room(kinds)
    count=kinds.count('human')
    tokens=[join(r) for _ in range(count)]
    for token in tokens[:-1]:
        apply(r, identify(r,token), {'type':'ready'},101)
        assert r['phase']=='waiting'
    apply(r,identify(r,tokens[-1]),{'type':'ready'},101)
    assert r['phase']=='discussion' and r['round']==1
    with pytest.raises(ValueError):join(r)


def test_cumulative_result_and_feedback():
    r=room();start(r)
    advance(r,161);vote_all(r,[0,0,1],162)
    assert r['phase']=='feedback'
    advance(r,170);advance(r,230);vote_all(r,[1,1,2],231)
    assert r['result']['winner']==1
    assert r['result']['totals']=={'0':2,'1':3,'2':1}


def test_tie_bans_self_and_uses_round_two_history():
    r=room();start(r)
    advance(r,161);vote_all(r,[0,0,2],162)
    advance(r,170);advance(r,230);vote_all(r,[1,1,2],231)
    assert r['round']==3 and r['candidates']==[0,1,2]
    advance(r,261)
    with pytest.raises(ValueError,match='Self-votes'):apply(r,0,{'type':'vote','candidate':0,'round':3},262)
    vote_all(r,[1,2,0],262)
    assert r['result']['winner']==1
    assert 'round 2 support' in r['result']['reason']


def test_tie_participation_and_exact_draw():
    for vocal in (True,False):
        r=room();start(r)
        if vocal:
            apply(r,2,{'type':'message','text':'Let us listen to each other before deciding.','round':1},102)
        advance(r,161);vote_all(r,[0,1,2],162)
        advance(r,170);advance(r,230);vote_all(r,[0,1,2],231)
        advance(r,261);vote_all(r,[1,2,0],262)
        assert r['result']['winner']==(2 if vocal else None)


def test_no_votes_ends_and_silent_chat_advances():
    r=room();start(r)
    for t in (161,191,199,259,289):advance(r,t)
    assert r['phase']=='results' and r['result']['winner'] is None


def test_private_information_never_in_view():
    r=room(['human','ai','ai']);token=join(r);p=identify(r,token)
    snapshot=view(r,p,101)
    raw=json.dumps(snapshot)
    for hidden in ('token_hash','ai_mode','participants','"kind"',token):assert hidden not in raw
    assert 'votes' not in snapshot and 'ready' not in snapshot['players'][0]


def test_duplicate_invalid_late_and_wrong_round_actions():
    r=room();start(r)
    with pytest.raises(ValueError):apply(r,0,{'type':'vote','candidate':1,'round':1},102)
    with pytest.raises(ValueError):apply(r,0,{'type':'message','text':'late','round':1},161)
    advance(r,161)
    with pytest.raises(ValueError):apply(r,0,{'type':'vote','candidate':9,'round':1},162)
    apply(r,0,{'type':'vote','candidate':1,'round':1},162)
    with pytest.raises(ValueError,match='already recorded'):apply(r,0,{'type':'vote','candidate':2,'round':1},163)
    with pytest.raises(ValueError):apply(r,1,{'type':'vote','candidate':0,'round':2},163)


def test_participation_capped_repetition_and_short_text():
    r=room();start(r)
    for i,text in enumerate(['Hi','A long and considered contribution to the discussion.']*4):
        apply(r,0,{'type':'message','text':text,'round':1},102+3*i)
    assert participation(r)['0']==1
    for i in range(5):
        apply(r,1,{'type':'message','text':f'Distinct detailed contribution number {i} about leadership.','round':1},102+3*i)
    assert participation(r)['1']==3


def test_token_seat_restores_without_ip():
    r=room();token=join(r)
    assert identify(r,token) is not None
    assert identify(r,'forged') is None
    assert identify(copy.deepcopy(r),token)==identify(r,token)


def test_tied_candidates_only_but_everyone_votes():
    r=room();start(r)
    r['round']=3;r['candidates']=[0,1];transition(r,'voting',30,200)
    with pytest.raises(ValueError):apply(r,0,{'type':'vote','candidate':2,'round':3},201)
    vote_all(r,[1,0,1],201)
    assert r['result']['winner']==1


def test_simulated_agents_chat_vote_and_do_not_leak_types():
    r=room(['human','ai','ai']);start(r)
    assert agent_step(r,126)
    assert len(r['messages'])==1  # A peer message prevents an immediate bot pile-on.
    agent_step(r,140)
    assert len(r['messages'])==2
    advance(r,161);agent_step(r,170)
    assert len(r['votes']['1'])==2
    assert not agent_step(r,171) # Already voted; does not submit twice.


def test_bad_config(tmp_path):
    c=BASE.copy();c['participants']=['ai']*3
    f=tmp_path/'config.yml';f.write_text(yaml.safe_dump(c))
    with pytest.raises(ValueError):load_config(f)


def test_agents_wait_and_do_not_monologue():
    r=room(['human','human','ai']);start(r)
    agent_step(r,102)
    assert not r['messages']
    agent_step(r,126)
    assert len(r['messages'])==1
    agent_step(r,130)
    assert len(r['messages'])==1
    human=next(p['id'] for p in r['players'] if p['kind']=='human')
    apply(r,human,{'type':'message','round':1,'text':'How would you handle disagreement fairly?'},131)
    agent_step(r,132)
    assert len(r['messages'])==2
    agent_step(r,156)
    assert len(r['messages'])==3
    assert 'ask each person for a reason' in r['messages'][-1]['text']
