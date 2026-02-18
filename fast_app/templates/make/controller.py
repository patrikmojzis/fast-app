from app.http_files.resources.__MODEL_SNAKE___resource import __MODEL_CLASS__Resource
from app.http_files.schemas.__MODEL_SNAKE___schema import __MODEL_CLASS__Schema, __MODEL_CLASS__PartialSchema
from app.models.__MODEL_SNAKE__ import __MODEL_CLASS__

from fast_app import paginate


async def index():
    return await paginate(__MODEL_CLASS__, __MODEL_CLASS__Resource)


async def show(__MODEL_VAR__: __MODEL_CLASS__):
    return __MODEL_CLASS__Resource(__MODEL_VAR__)


async def store(data: __MODEL_CLASS__Schema):
    __MODEL_VAR__ = await __MODEL_CLASS__.create(data.validated)
    return __MODEL_CLASS__Resource(__MODEL_VAR__)


async def update(__MODEL_VAR__: __MODEL_CLASS__, data: __MODEL_CLASS__PartialSchema):
    __MODEL_VAR__ = await __MODEL_VAR__.update(data.validated)
    return __MODEL_CLASS__Resource(__MODEL_VAR__)


async def destroy(__MODEL_VAR__: __MODEL_CLASS__):
    await __MODEL_VAR__.delete()
