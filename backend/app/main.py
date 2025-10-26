from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.db import init_db
from app.core.cache import RedisCache, get_redis_client
from app.routers import analytics, risk, stream
from app.core.websocket_manager import SnapshotWebSocketManager
from app.services.data_pipeline import initialize_fred_client, get_credit_signals
import asyncio
import pickle


app = FastAPI(title="Systemic Risk Engine")
snapshot_ws_manager = SnapshotWebSocketManager()
background_task_started = False

# Routers
app.include_router(risk.router, prefix="/risk", tags=["Risk"])
app.include_router(stream.router, tags=["WebSocket"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === BACKGROUND REFRESH ===
async def background_refresh(interval_hours: int = 24):
    """Runs every <interval_hours> after the last refresh."""
    global background_task_started
    if background_task_started:
        print("⚠️ Background refresh already running — skipping duplicate task.")
        return
    background_task_started = True

    print(f"✅ Background refresh loop started. Next run in {interval_hours}h.")

    # Wait 24 hours before the first refresh
    await asyncio.sleep(interval_hours * 3600)

    while True:
        try:
            print("🔄 Background refresh: updating market/credit data...")
            await get_credit_signals(force_refresh=True)
            print("✅ Credit data successfully refreshed.")
        except Exception as e:
            print(f"❌ Background refresh failed: {e}")

        print(f"🕓 Sleeping {interval_hours}h until next refresh...")
        await asyncio.sleep(interval_hours * 3600)


@app.on_event("startup")
async def startup_event():
    initialize_fred_client()
    await init_db()
    await RedisCache._initialize()

    redis_client = await get_redis_client()
    
    if redis_client:
        print("✅ Startup: Redis & DB initialized.")
        try:
            # Warm up cache if not already there
            print("⚙️ Warming up cache with credit signals...")
            await get_credit_signals(force_refresh=False, _internal_call=True)
            print("✅ Cache warm-up complete.")
        except Exception as e:
            print(f"❌ Cache warm-up failed: {e}")
    else:
        print("⚠️ Redis unavailable. Only DB initialized.")

    await asyncio.sleep(2)
    

    asyncio.create_task(background_refresh(interval_hours=24))


@app.on_event("shutdown")
async def shutdown_event():
    await RedisCache.close()
    print("🛑 Shutdown: Redis connection closed.")


@app.get("/debug/cache/status")
async def cache_status():
    redis_client = await get_redis_client()
    status = {"redis_available": redis_client is not None, "cache_keys": []}

    if redis_client:
        try:
            keys = await redis_client.keys("*")
            status["cache_keys"] = keys
            test_key = "health_check"
            await redis_client.set(test_key, "test", ex=10)
            val = await redis_client.get(test_key)
            status["read_write_test"] = val == b"test"
        except Exception as e:
            status["error"] = str(e)

    return status


@app.get("/debug/cache/credit-signals")
async def debug_credit_signals_cache():
    redis_client = await get_redis_client()
    if not redis_client:
        return {"error": "Redis not available"}

    try:
        cache_key = "credit_signals"
        cached = await redis_client.get(cache_key)
        if not cached:
            return {"cached": False, "message": "No cached data found"}

        data = pickle.loads(cached)
        return {
            "cached": True,
            "data_shape": f"{len(data)} rows × {len(data.columns)} columns",
            "columns": list(data.columns),
            "latest_date": str(data.index[-1]) if not data.empty else "empty",
        }
    except Exception as e:
        return {"error": f"Error reading cache: {e}"}


@app.get("/debug/cache/clear")
async def clear_cache():
    redis_client = await get_redis_client()
    if not redis_client:
        return {"message": "Redis not available"}

    try:
        await redis_client.flushdb()
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/")
async def root():
    return {"message": "Systemic Risk API running."}


__all__ = ["app", "snapshot_ws_manager"]
