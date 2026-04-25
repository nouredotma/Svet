from taskiq import InMemoryBroker

broker = InMemoryBroker()


def _register_middlewares() -> None:
    from app.workers.middlewares import LoggingMiddleware, RetryMiddleware

    broker.add_middlewares(LoggingMiddleware(), RetryMiddleware())


_register_middlewares()


import importlib

importlib.import_module("app.workers.agent_task")


async def startup_broker() -> None:
    await broker.startup()


async def shutdown_broker() -> None:
    await broker.shutdown()
