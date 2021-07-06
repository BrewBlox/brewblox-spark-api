"""
Client-side API for Spark blocks

Requires setup() to have been called for the following
brewblox_service modules:
- scheduler
- http
- mqtt
"""

import asyncio
from contextlib import suppress
from copy import deepcopy
from typing import Awaitable, Callable, List, Optional, Set

from aiohttp import web
from brewblox_service import brewblox_logger, features, http, mqtt

STATE_TOPIC = 'brewcast/state'

LOGGER = brewblox_logger(__name__)


class BlocksApi(features.ServiceFeature):

    def __init__(self, app: web.Application, service_id: str):
        super().__init__(app)

        self._service_id: str = service_id
        self._url: str = f'http://{service_id}:5000/{service_id}'
        self._state: dict = None
        self._ready_evt: asyncio.Event = None
        self._listeners: Set[Callable[[List[dict]], Awaitable[None]]] = set()

    async def startup(self, app: web.Application):
        self._ready_evt = asyncio.Event()
        await mqtt.listen(app, f'{STATE_TOPIC}/{self._service_id}', self._on_state)
        await mqtt.listen(app, f'{STATE_TOPIC}/{self._service_id}/patch', self._on_patch)
        await mqtt.subscribe(app, f'{STATE_TOPIC}/{self._service_id}/#')

    async def shutdown(self, app: web.Application):
        if self._ready_evt:
            self._ready_evt.clear()
        await mqtt.unsubscribe(app, f'{STATE_TOPIC}/{self._service_id}/#')
        await mqtt.unlisten(app, f'{STATE_TOPIC}/{self._service_id}/patch', self._on_patch)
        await mqtt.unlisten(app, f'{STATE_TOPIC}/{self._service_id}', self._on_state)

    async def _notify(self):
        blocks = self.blocks
        for cb in self._listeners:
            await cb(blocks)

    async def _on_state(self, topic, payload):
        self._state = payload['data']

        synchronized = False
        with suppress(KeyError, TypeError):
            synchronized = self._state['status']['is_synchronized'] is True

        if synchronized != self._ready_evt.is_set():
            if synchronized:
                LOGGER.info(f'Spark service {self._service_id} is now ready')
                self._ready_evt.set()
            else:
                LOGGER.info(f'Spark service {self._service_id} disconnected')
                self._ready_evt.clear()

        await self._notify()

    async def _on_patch(self, topic, payload):
        if not self._state:
            return

        data = payload['data']
        affected = data['deleted'] + [
            block['id'] for block in data['changed']
        ]
        self._state['blocks'] = data['changed'] + [
            block for block in self._state['blocks']
            if not block['id'] in affected
        ]

        await self._notify()

    @property
    def is_ready(self) -> asyncio.Event:
        """
        Returns an awaitable event that is set as long as the service is ready.
        """
        return self._ready_evt

    @property
    def blocks(self) -> List[dict]:
        try:
            return deepcopy(self._state['blocks'])
        except (KeyError, TypeError):
            return []

    def on_blocks_change(self, cb) -> None:
        self._listeners.add(cb)

    def cached_block(self, id: str) -> Optional[dict]:
        return next((block for block in self.blocks if block['id'] == id), None)

    async def wait_ready(self, timeout=None):
        await asyncio.wait_for(self._ready_evt.wait(), timeout=timeout)

    async def create(self, block: dict) -> dict:
        resp = await http.session(self.app).post(
            f'{self._url}/blocks/create',
            json=block,
        )
        return await resp.json()

    async def read(self, id: str) -> dict:
        resp = await http.session(self.app).post(
            f'{self._url}/blocks/read',
            json={'id': id},
        )
        return await resp.json()

    async def write(self, block: dict) -> dict:
        resp = await http.session(self.app).post(
            f'{self._url}/blocks/write',
            json=block,
        )
        return await resp.json()

    async def patch(self, id: str, partial: dict) -> dict:
        resp = await http.session(self.app).post(
            f'{self._url}/blocks/patch',
            json={'id': id, 'data': partial},
        )
        return await resp.json()

    async def delete(self, id: str) -> None:
        await http.session(self.app).post(
            f'{self._url}/blocks/delete',
            json={'id': id},
        )
