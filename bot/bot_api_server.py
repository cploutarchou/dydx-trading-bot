"""
Bot API Server - FastAPI server for controlling multiple bot instances
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import bot models and manager
from bot_api_models import (
    BotInstanceConfig,
    BotInstanceStatus,
    BotInstanceList,
    BotOperationResult,
    BotActionRequest,
    BotTradingStats,
    TradingParameters,
    BotCredentials,
    BotStatus
)
from bot_instance_manager import bot_manager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="dYdX Trading Bot API",
    description="API for managing multiple dYdX trading bot instances",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API RESPONSE WRAPPER
# ============================================================================

def api_response(success: bool, data=None, message: str = "", status_code: int = 200):
    """Standardized API response format"""
    response_data = {
        "success": success,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    return JSONResponse(content=response_data, status_code=status_code)


# ============================================================================
# BOT INSTANCE MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/v1/bots", response_model=BotOperationResult)
async def create_bot_instance(config: BotInstanceConfig):
    """Create a new bot instance"""
    try:
        result = await bot_manager.create_instance(config)
        
        if result.success:
            return api_response(
                success=True,
                data=result.dict(),
                message=f"Bot instance '{config.instance_id}' created successfully"
            )
        else:
            return api_response(
                success=False,
                message=result.message,
                status_code=400
            )
    
    except Exception as e:
        logger.error(f"Error creating bot instance: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500
        )


@app.get("/api/v1/bots", response_model=BotInstanceList)
async def list_bot_instances():
    """Get list of all bot instances"""
    try:
        instances = await bot_manager.list_instances()
        
        # Calculate summary statistics
        total_instances = len(instances)
        running_instances = len([i for i in instances if i.status == BotStatus.RUNNING])
        stopped_instances = len([i for i in instances if i.status == BotStatus.STOPPED])
        error_instances = len([i for i in instances if i.status == BotStatus.ERROR])
        
        result = BotInstanceList(
            instances=instances,
            total_instances=total_instances,
            running_instances=running_instances,
            stopped_instances=stopped_instances,
            error_instances=error_instances
        )
        
        return api_response(
            success=True,
            data=result.dict(),
            message=f"Retrieved {total_instances} bot instances"
        )
    
    except Exception as e:
        logger.error(f"Error listing bot instances: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500
        )


@app.get("/api/v1/bots/{instance_id}", response_model=BotInstanceStatus)
async def get_bot_instance(instance_id: str):
    """Get specific bot instance status"""
    try:
        instance = await bot_manager.get_instance_status(instance_id)
        
        if instance is None:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404
            )
        
        return api_response(
            success=True,
            data=instance.dict(),
            message=f"Retrieved status for bot instance '{instance_id}'"
        )
    
    except Exception as e:
        logger.error(f"Error getting bot instance {instance_id}: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500
        )


@app.delete("/api/v1/bots/{instance_id}")
async def delete_bot_instance(instance_id: str, force: bool = False):
    """Delete bot instance"""
    try:
        result = await bot_manager.delete_instance(instance_id)
        
        if result.success:
            return api_response(
                success=True,
                data=result.dict(),
                message=f"Bot instance '{instance_id}' deleted successfully"
            )
        else:
            return api_response(
                success=False,
                message=result.message,
                status_code=400
            )
    
    except Exception as e:
        logger.error(f"Error deleting bot instance {instance_id}: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500
        )


# ============================================================================
# BOT CONTROL ENDPOINTS
# ============================================================================

@app.post("/api/v1/bots/{instance_id}/start")
async def start_bot_instance(instance_id: str):
    """Start bot instance"""
    try:
        result = await bot_manager.start_instance(instance_id)
        
        if result.success:
            return api_response(
                success=True,
                data=result.dict(),
                message=f"Bot instance '{instance_id}' started successfully"
            )
        else:
            return api_response(
                success=False,
                message=result.message,
                status_code=400
            )
    
    except Exception as e:
        logger.error(f"Error starting bot instance {instance_id}: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500
        )


@app.post("/api/v1/bots/{instance_id}/stop")
async def stop_bot_instance(instance_id: str, force: bool = False):
    """Stop bot instance"""
    try:
        result = await bot_manager.stop_instance(instance_id, force=force)
        
        if result.success:
            return api_response(
                success=True,
                data=result.dict(),
                message=f"Bot instance '{instance_id}' stopped successfully"
            )
        else:
            return api_response(
                success=False,
                message=result.message,
                status_code=400
            )
    
    except Exception as e:
        logger.error(f"Error stopping bot instance {instance_id}: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500
        )


@app.post("/api/v1/bots/{instance_id}/restart")
async def restart_bot_instance(instance_id: str):
    """Restart bot instance"""
    try:
        # Stop first
        stop_result = await bot_manager.stop_instance(instance_id, force=False)
        if not stop_result.success:
            return api_response(
                success=False,
                message=f"Failed to stop instance: {stop_result.message}",
                status_code=400
            )
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Start again
        start_result = await bot_manager.start_instance(instance_id)
        
        if start_result.success:
            return api_response(
                success=True,
                data=start_result.dict(),
                message=f"Bot instance '{instance_id}' restarted successfully"
            )
        else:
            return api_response(
                success=False,
                message=f"Failed to start instance: {start_result.message}",
                status_code=400
            )
    
    except Exception as e:
        logger.error(f"Error restarting bot instance {instance_id}: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500
        )


# ============================================================================
# QUICK DEPLOYMENT ENDPOINTS
# ============================================================================

@app.post("/api/v1/bots/quick-deploy")
async def quick_deploy_bot(
    instance_name: str,
    credentials: BotCredentials,
    trading_params: TradingParameters,
    auto_start: bool = True
):
    """Quick deploy and optionally start a new bot instance"""
    try:
        # Generate instance ID from name
        import re
        instance_id = re.sub(r'[^a-zA-Z0-9_-]', '-', instance_name.lower())
        instance_id = f"{instance_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Create configuration
        config = BotInstanceConfig(
            instance_id=instance_id,
            instance_name=instance_name,
            credentials=credentials,
            trading_params=trading_params
        )
        
        # Create instance
        create_result = await bot_manager.create_instance(config)
        if not create_result.success:
            return api_response(
                success=False,
                message=create_result.message,
                status_code=400
            )
        
        # Auto-start if requested
        if auto_start:
            await asyncio.sleep(1)  # Brief pause
            start_result = await bot_manager.start_instance(instance_id)
            
            if start_result.success:
                return api_response(
                    success=True,
                    data={
                        "instance_id": instance_id,
                        "created": create_result.success,
                        "started": start_result.success,
                        "status": "running"
                    },
                    message=f"Bot '{instance_name}' deployed and started successfully"
                )
            else:
                return api_response(
                    success=True,
                    data={
                        "instance_id": instance_id,
                        "created": create_result.success,
                        "started": False,
                        "status": "stopped",
                        "start_error": start_result.message
                    },
                    message=f"Bot '{instance_name}' deployed but failed to start: {start_result.message}"
                )
        else:
            return api_response(
                success=True,
                data={
                    "instance_id": instance_id,
                    "created": create_result.success,
                    "started": False,
                    "status": "stopped"
                },
                message=f"Bot '{instance_name}' deployed successfully (not started)"
            )
    
    except Exception as e:
        logger.error(f"Error in quick deploy: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500
        )


# ============================================================================
# HEALTH AND STATUS ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """API health check"""
    return api_response(
        success=True,
        data={
            "status": "healthy",
            "api_version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        },
        message="API is healthy"
    )


@app.get("/api/v1/system/status")
async def system_status():
    """Get system status and statistics"""
    try:
        instances = await bot_manager.list_instances()
        
        # Cleanup any dead processes
        await bot_manager.cleanup_dead_processes()
        
        # Calculate system stats
        total_instances = len(instances)
        running_instances = len([i for i in instances if i.status == BotStatus.RUNNING])
        
        # System resource usage
        import psutil
        cpu_usage = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        return api_response(
            success=True,
            data={
                "bot_instances": {
                    "total": total_instances,
                    "running": running_instances,
                    "max_allowed": bot_manager.max_instances
                },
                "system_resources": {
                    "cpu_usage_percent": cpu_usage,
                    "memory_usage_percent": memory.percent,
                    "memory_available_gb": round(memory.available / (1024**3), 2)
                },
                "api_info": {
                    "version": "1.0.0",
                    "uptime_hours": "N/A"  # Could implement uptime tracking
                }
            },
            message="System status retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500
        )


# ============================================================================
# BACKGROUND TASKS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize bot manager on startup"""
    logger.info("Starting Bot API Server...")
    await bot_manager.cleanup_dead_processes()
    logger.info("Bot API Server ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Bot API Server...")
    # Optionally stop all running instances on shutdown
    # This could be configurable behavior


# ============================================================================
# MAIN SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    # Configuration from environment
    host = os.getenv("BOT_API_HOST", "0.0.0.0")
    port = int(os.getenv("BOT_API_PORT", 8889))
    workers = int(os.getenv("BOT_API_WORKERS", 1))
    
    # Run server
    uvicorn.run(
        "bot_api_server:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,  # Set to True for development
        log_level="info"
    )