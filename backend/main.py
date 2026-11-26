import asyncio
import copy
import logging
import os
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from sqlalchemy import JSON, Column, MetaData, String, Table, create_engine, select, update

from engine import TERMINAL, advance, agent_step, apply, identify, join, load_config, new_room, transition, view

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
CONFIG = Path(os.getenv('CONFIG_PATH', str(ROOT / 'config.yml')))
engine = create_engine(os.getenv('DATABASE_URL', 'postgresql+psycopg://experiment:experiment@localhost:5432/experiment'), pool_pre_ping=True)
meta = MetaData()
records = Table('experiment_sessions', meta, Column('id', String, primary_key=True), Column('snapshot', JSON, nullable=False))
rooms, sockets = {}, {}
lock = asyncio.Lock()


def persist(room, insert=False):
    with engine.begin() as connection:
        if insert:
            connection.execute(records.insert().values(id=room['id'], snapshot=room))
        else:
            connection.execute(update(records).where(records.c.id == room['id']).values(snapshot=room))


async def commit(room):
    room['version'] += 1
    await asyncio.to_thread(persist, room)
    rooms[room['id']] = room
    async def send(ws, pid):
        try:
            await asyncio.wait_for(ws.send_json(view(room, pid)), timeout=1)
        except Exception:
            sockets.get(room['id'], {}).pop(ws, None)
    await asyncio.gather(*(send(ws, pid) for ws, pid in list(sockets.get(room['id'], {}).items())))


async def ticker():
    while True:
        await asyncio.sleep(0.25)
        async with lock:
            for original in list(rooms.values()):
                if original['phase'] in TERMINAL:
                    continue
                room = copy.deepcopy(original)
                now = time.time()
                changed = False
                if room['deadline'] is not None and now >= room['deadline']:
                    advance(room, now)
                    changed = True
                changed = agent_step(room, now) or changed
                if changed:
                    try:
                        await commit(room)
                    except Exception:
                        logger.exception('Could not persist session transition')


@asynccontextmanager
async def lifespan(app):
    load_config(CONFIG)
    await asyncio.to_thread(meta.create_all, engine)
    def restore():
        with engine.connect() as connection:
            return list(connection.execute(select(records.c.snapshot)).scalars())
    for room in await asyncio.to_thread(restore):
        if room['phase'] not in TERMINAL:
            transition(room, 'interrupted', 0, time.time())
            await asyncio.to_thread(persist, room)
        rooms[room['id']] = room
    task = asyncio.create_task(ticker())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    engine.dispose()


app = FastAPI(title='Common Ground experiment', lifespan=lifespan)


@app.get('/api/health')
async def health():
    def check():
        with engine.connect() as connection:
            connection.execute(select(1))
    await asyncio.to_thread(check)
    return {'status': 'ok'}


@app.post('/api/rooms')
async def create_room():
    async with lock:
        if sum(r['phase'] not in TERMINAL for r in rooms.values()) >= 50:
            raise HTTPException(429, 'Too many active sessions. Wait for a session to close.')
        room = new_room(load_config(CONFIG))
        await asyncio.to_thread(persist, room, True)
        rooms[room['id']] = room
        return {'id': room['id']}


@app.post('/api/rooms/{rid}/join')
async def join_room(rid: str):
    async with lock:
        if rid not in rooms:
            raise HTTPException(404, 'Session not found. Check the invitation link.')
        room = copy.deepcopy(rooms[rid])
        if room['deadline'] is not None and time.time() >= room['deadline']:
            raise HTTPException(409, 'The waiting room has expired.')
        try:
            token = join(room)
        except ValueError as e:
            raise HTTPException(409, str(e))
        await commit(room)
        return {'token': token}


@app.websocket('/api/ws/{rid}')
async def websocket(ws: WebSocket, rid: str):
    await ws.accept()
    try:
        # Token is in the first frame, never in URLs/access logs.
        auth = await asyncio.wait_for(ws.receive_json(), timeout=5)
        token = auth.get('token') if isinstance(auth, dict) else None
        if not isinstance(token, str) or len(token) > 100:
            await ws.close(code=1008)
            return
        async with lock:
            room = rooms.get(rid)
            pid = identify(room, token) if room else None
            if pid is None:
                await ws.close(code=1008)
                return
            sockets.setdefault(rid, {})[ws] = pid
            await ws.send_json(view(room, pid))
        while True:
            raw = await ws.receive_text()
            if len(raw) > 4096:
                await ws.close(code=1009)
                return
            import json
            try:
                action = json.loads(raw)
                if not isinstance(action, dict):
                    raise ValueError('Expected an action object.')
                async with lock:
                    room = copy.deepcopy(rooms[rid])
                    apply(room, pid, action)
                    await commit(room)
            except (ValueError, TypeError) as e:
                await ws.send_json({'error': str(e)})
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        sockets.get(rid, {}).pop(ws, None)


if (ROOT / 'frontend/dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'frontend/dist', html=True), name='frontend')
