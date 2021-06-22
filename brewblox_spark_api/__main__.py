"""
Quick and dirty test code.
"""

import asyncio

from brewblox_service import (brewblox_logger, features, http, mqtt, repeater,
                              scheduler, service)

from brewblox_spark_api import blocks_api

LOGGER = brewblox_logger(__name__)


class TestClient(repeater.RepeaterFeature):

    async def prepare(self):
        self.api = blocks_api.BlocksApi(self.app, 'sparkey')
        await self.api.startup(self.app)
        self.api.on_blocks_change(self.on_blocks)

    async def before_shutdown(self, app):
        await self.api.shutdown(app)

    async def run(self):
        await asyncio.sleep(5)
        # block = await asyncio.wait_for(
        #     self.api.read('Ferment Beer Setting'),
        #     timeout=2
        # )
        # LOGGER.info(f'{block}')

    async def on_blocks(self, blocks):
        LOGGER.info(f'{len(blocks)}')


def main():
    app = service.create_app('test_app')

    scheduler.setup(app)
    mqtt.setup(app)
    http.setup(app)

    features.add(app, TestClient(app))

    service.furnish(app)
    service.run(app)


if __name__ == '__main__':
    main()
