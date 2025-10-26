from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from app.services.realtime_service import realtime_service
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket Streams"])

@router.websocket("/ws/risk")
async def risk_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket risk stream connected")
    
    try:
        while True:
            # Stop sending if the socket is closed
            if websocket.application_state != WebSocketState.CONNECTED:
                logger.warning("WebSocket closed — stopping stream.")
                break

            try:
                metrics = await realtime_service.get_current_metrics()
                
                enhanced_metrics = {
                    **metrics,
                    "_metadata": {
                        "type": "comprehensive_risk_update",
                        "stream": "real_time",
                        "timestamp": metrics.get("timestamp"),
                        "data_points": metrics.get("data_points", 0),
                        "signals_count": len(metrics.get("available_signals", []))
                    }
                }
                
                await websocket.send_json(enhanced_metrics)
                logger.debug(f"Sent COMPREHENSIVE WebSocket update: {enhanced_metrics['timestamp']}")
                
            except Exception as e:
                logger.warning(f"Risk stream inner error: {e}")
                # Send error to client but don't break connection
                try:
                    await websocket.send_json({
                        "error": str(e),
                        "_metadata": {
                            "type": "error",
                            "timestamp": datetime.utcnow().isoformat() + "Z"
                        }
                    })
                except:
                    pass

            await asyncio.sleep(10)  # 10-second intervals with FULL data

    except WebSocketDisconnect:
        logger.info("WebSocket risk stream client disconnected")
    except Exception as e:
        logger.error(f"WebSocket risk stream error: {e}")
    finally:
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close()