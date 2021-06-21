"""
Tests brewblox_spark_api.blocks_api
"""
import pytest
from brewblox_service import http

from brewblox_spark_api import blocks_api

TESTED = blocks_api.__name__


@pytest.fixture
def app(app, mocker):
    http.setup(app)
    return app


async def test_api_state(app, client):
    pass
