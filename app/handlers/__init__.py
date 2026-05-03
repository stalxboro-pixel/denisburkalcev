from aiogram import Dispatcher

from app.handlers import admin, info, menu, payments, products, profile, start, support


def register_routers(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(profile.router)
    dp.include_router(info.router)
    dp.include_router(support.router)
    dp.include_router(products.router)
    dp.include_router(payments.router)
    dp.include_router(admin.router)
