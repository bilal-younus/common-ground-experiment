"""Opt-in real PostgreSQL + HTTP/WebSocket integration, using a disposable DB."""
import concurrent.futures
import importlib
import json
import os
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='Set TEST_DATABASE_URL to a disposable PostgreSQL database')


@pytest.mark.parametrize('kinds', [['human']*3, ['human','human','ai'], ['human','ai','ai']])
def test_complete_flow_postgres(monkeypatch, tmp_path, kinds):
    assert 'chm_test' in URL, 'Use a disposable database with chm_test in its name'
    monkeypatch.setenv('DATABASE_URL', URL)
    from engine import load_config
    config=load_config(Path(__file__).resolve().parents[2]/'config.yml')
    config.update(participants=kinds,discussion_seconds=2,voting_seconds=6,feedback_seconds=1,tie_discussion_seconds=2,tie_voting_seconds=6)
    path=tmp_path/'config.yml';path.write_text(yaml.safe_dump(config))
    monkeypatch.setenv('CONFIG_PATH',str(path))
    import main
    main=importlib.reload(main)
    with TestClient(main.app) as client:
        assert client.get('/api/health').status_code==200
        rid=client.post('/api/rooms').json()['id']
        tokens=[client.post(f'/api/rooms/{rid}/join').json()['token'] for _ in range(kinds.count('human'))]
        def participant(token):
            with client.websocket_connect(f'/api/ws/{rid}') as ws:
                ws.send_json({'token':token})
                initial=ws.receive_json();pid=initial['you']
                ws.send_json({'type':'ready'})
                sent=set()
                for _ in range(100):
                    s=ws.receive_json()
                    assert 'error' not in s,s
                    assert 'token_hash' not in json.dumps(s)
                    assert 'kind' not in s['players'][0]
                    key=(s['phase'],s['round'])
                    if s['phase']=='results':return s
                    if key in sent:continue
                    if s['phase']=='discussion':
                        ws.send_json({'type':'message','round':s['round'],'text':f'I am participant {pid} and I value fair and transparent decisions.'})
                        sent.add(key)
                    if s['phase']=='voting':
                        options=[i for i in s['candidates'] if s['round']!=3 or i!=pid]
                        ws.send_json({'type':'vote','round':s['round'],'candidate':options[0]})
                        sent.add(key)
                raise AssertionError('Session did not terminate')
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(participant,tokens))
        assert all(s['result']==results[0]['result'] for s in results)
        assert results[0]['ballot_counts']['1']==3
        assert results[0]['ballot_counts']['2']==3
        with client.websocket_connect(f'/api/ws/{rid}') as ws:
            ws.send_json({'token':tokens[0]})
            restored=ws.receive_json()
            assert restored['phase']=='results'
            assert restored['you']==results[0]['you']
        with main.engine.connect() as conn:
            saved=conn.execute(main.select(main.records.c.snapshot).where(main.records.c.id==rid)).scalar_one()
            assert saved['result']==results[0]['result']
            assert saved['config']['participants']==kinds
            assert len(saved['history'])>=6


@pytest.mark.parametrize('scenario,expected', [('ballot',0),('history',1),('participation',2),('draw',None),('silent',None)])
def test_third_round_full_flow(monkeypatch,tmp_path,scenario,expected):
    """Force ties through real client ballots, never by patching server room state."""
    assert 'chm_test' in URL
    monkeypatch.setenv('DATABASE_URL',URL)
    from engine import load_config
    config=load_config(Path(__file__).resolve().parents[2]/'config.yml')
    config.update(participants=['human']*3,discussion_seconds=2,voting_seconds=3,feedback_seconds=1,tie_discussion_seconds=2,tie_voting_seconds=3)
    path=tmp_path/'tie.yml';path.write_text(yaml.safe_dump(config))
    monkeypatch.setenv('CONFIG_PATH',str(path))
    import main
    main=importlib.reload(main)
    with TestClient(main.app) as client:
        rid=client.post('/api/rooms').json()['id']
        tokens=[client.post(f'/api/rooms/{rid}/join').json()['token'] for _ in range(3)]
        def participant(token):
            with client.websocket_connect(f'/api/ws/{rid}') as ws:
                ws.send_json({'token':token});pid=ws.receive_json()['you']
                ws.send_json({'type':'ready'})
                seen=set();rejected=False
                for _ in range(150):
                    s=ws.receive_json()
                    if 'error' in s:
                        assert 'Self-votes' in s['error']
                        rejected=True
                        candidate=[1,0,0][pid] if scenario=='ballot' else (pid+1)%3
                        ws.send_json({'type':'vote','round':3,'candidate':candidate})
                        continue
                    key=(s['phase'],s['round'])
                    if s['phase']=='results':
                        assert ('discussion',3) in seen and ('voting',3) in seen
                        assert rejected or scenario=='silent'
                        return s
                    if key in seen:continue
                    seen.add(key)
                    if key==('discussion',1) and scenario=='participation' and pid==2:
                        ws.send_json({'type':'message','round':1,'text':'I would listen to every perspective before making a decision.'})
                    if s['phase']=='voting':
                        r=s['round']
                        if r==3:
                            assert s['candidates']==[0,1,2]
                            if scenario=='silent':continue
                            # Verify server enforcement before submitting a valid ballot.
                            candidate=pid
                        elif scenario=='history':candidate=([0,0,2] if r==1 else [1,1,2])[pid]
                        else:candidate=pid
                        ws.send_json({'type':'vote','round':r,'candidate':candidate})
                raise AssertionError('Tie flow did not finish')
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(participant,tokens))
        assert all(s['result']==results[0]['result'] for s in results)
        final=results[0]
        assert final['round']==3 and final['result']['winner']==expected
        assert final['ballot_counts']=={'1':3,'2':3,'3':0 if scenario=='silent' else 3}
        criterion={'ballot':'Tie-break votes','history':'Round 2 support','participation':'Discussion participation','draw':'Discussion participation','silent':'Discussion participation'}[scenario]
        assert final['result']['trace'][-1]['criterion']==criterion
        with client.websocket_connect(f'/api/ws/{rid}') as ws:
            ws.send_json({'token':tokens[0]})
            assert ws.receive_json()['result']==final['result']
        with main.engine.connect() as conn:
            saved=conn.execute(main.select(main.records.c.snapshot).where(main.records.c.id==rid)).scalar_one()
            assert saved['result']==final['result']
            assert any(h['round']==3 and h['phase']=='voting' for h in saved['history'])
