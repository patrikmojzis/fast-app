import pytest

from fast_app.core.storage import Storage


@pytest.mark.asyncio
async def test_storage_put_and_get(tmp_path):
    Storage.configure({'local': {'driver': 'disk', 'root': str(tmp_path)}}, default_disk='local')
    data = b'hello'
    path = 'test.txt'
    await Storage.put(path, data)
    assert await Storage.exists(path)
    assert await Storage.get(path) == data
