import asyncio

from sqlalchemy import update

from app.db.config import async_session, engine
from app.db.models import ModelProfile


async def disable_all_model_profiles():
    """一次性将所有 model_profiles.is_enabled 设置为 False 的脚本"""
    print("正在连接数据库并准备更新 ModelProfile...")

    async with async_session() as session:
        async with session.begin():
            try:
                stmt = (
                    update(ModelProfile)
                    .values(is_enabled=False)
                    .execution_options(
                        synchronize_session=False
                    )  # 绕过内存 Session 缓存，直接在数据库层更新
                )

                result = await session.execute(stmt)

                # 获取受影响的行数
                affected_rows = result.rowcount
                print(f"成功将 {affected_rows} 个模型配置的 is_enabled 设置为 False。")
            except Exception as exc:
                print(f"更新过程中发生错误，事务已回滚: {exc}")
                raise exc


async def main():
    try:
        await disable_all_model_profiles()
    finally:
        await engine.dispose()
        print("数据库连接已安全关闭。")


if __name__ == "__main__":
    asyncio.run(main())
