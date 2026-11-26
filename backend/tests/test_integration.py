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
