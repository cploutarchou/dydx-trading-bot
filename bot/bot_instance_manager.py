"""
Bot Instance Manager - Handles multiple bot instances with API control
"""
import asyncio
import json
import os
import psutil
import signal
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import logging

from bot_api_models import (
    BotInstanceConfig,
    BotInstanceState,
    BotInstanceStatus,
    BotStatus,
    BotOperationResult,
    TradingParameters,
    NetworkEnvironment
)

logger = logging.getLogger(__name__)


class BotInstanceManager:
    """Manages multiple bot instances with isolated state and configuration"""
    
    def __init__(self, state_dir: str = "./bot_states", max_instances: int = 10):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.max_instances = max_instances
        
        # In-memory instance tracking
        self.instances: Dict[str, BotInstanceState] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        
        # Load existing instances from disk
        self._load_existing_instances()
    
    def _load_existing_instances(self):
        """Load bot instances from state directory"""
        state_file = self.state_dir / "instances.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    for instance_data in data.get('instances', []):
                        # Reconstruct instance state (without active processes)
                        instance_id = instance_data['instance_id']
                        self.instances[instance_id] = BotInstanceState(
                            instance_id=instance_id,
                            config=BotInstanceConfig.parse_obj(instance_data['config']),
                            status=BotStatus.STOPPED,
                            process_info={},
                            trading_stats=instance_data.get('trading_stats', {}),
                            created_at=datetime.fromisoformat(instance_data['created_at']),
                            last_update=datetime.now()
                        )
                logger.info(f"Loaded {len(self.instances)} existing bot instances")
            except Exception as e:
                logger.error(f"Error loading instances: {e}")
    
    def _save_instances_state(self):
        """Persist instance state to disk"""
        state_file = self.state_dir / "instances.json"
        try:
            data = {
                'instances': [
                    {
                        'instance_id': state.instance_id,
                        'config': state.config.dict(),
                        'trading_stats': state.trading_stats,
                        'created_at': state.created_at.isoformat(),
                        'last_update': state.last_update.isoformat()
                    }
                    for state in self.instances.values()
                ],
                'last_saved': datetime.now().isoformat()
            }
            with open(state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving instances state: {e}")
    
    def _get_instance_state_files(self, instance_id: str) -> Dict[str, Path]:
        """Get paths to instance-specific state files"""
        return {
            'bot_agents': self.state_dir / f"bot_agents_{instance_id}.json",
            'cointegrated_pairs': self.state_dir / f"cointegrated_pairs_{instance_id}.json",
            'config': self.state_dir / f"config_{instance_id}.yaml",
            'log': self.state_dir / f"bot_{instance_id}.log"
        }
    
    def _create_instance_config_file(self, instance_id: str, config: BotInstanceConfig) -> Path:
        """Create instance-specific configuration file"""
        files = self._get_instance_state_files(instance_id)
        
        # Create dynamic config YAML for this instance
        config_data = {
            'is_testnet': config.trading_params.is_testnet,
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'telegram': {
                'token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
                'chat_id': os.getenv('TELEGRAM_CHAT_ID', '')
            },
            'botSettings': {
                'abortAllPositions': config.trading_params.abort_all_positions,
                'findCointegratedPairs': config.trading_params.find_cointegrated_pairs,
                'manageExits': config.trading_params.manage_exits,
                'placeTrades': config.trading_params.place_trades,
                'resolutionTimeframe': config.trading_params.resolution_timeframe,
                'strategy': config.trading_params.strategy.value,
                'statsWindow': config.trading_params.stats_window,
                'maxHalfLife': config.trading_params.max_half_life,
                'ZScoreThreshold': config.trading_params.zscore_threshold,
                'usdPerTrade': config.trading_params.usd_per_trade,
                'usdMinCollateral': config.trading_params.usd_min_collateral,
                'closeAtZscoreCross': config.trading_params.close_at_zscore_cross
            },
            'dydx_testnet': {
                'dydx_chain_address': config.credentials.address if config.trading_params.is_testnet else '',
                'dydx_chain_secret': config.credentials.mnemonic if config.trading_params.is_testnet else ''
            },
            'dydx_mainnet': {
                'dydx_chain_address': config.credentials.address if not config.trading_params.is_testnet else '',
                'dydx_chain_secret': config.credentials.mnemonic if not config.trading_params.is_testnet else ''
            },
            'logging': {
                'level': os.getenv('LOG_LEVEL', 'INFO'),
                'loki': {
                    'enabled': os.getenv('LOKI_ENABLED', 'false').lower() == 'true',
                    'url': os.getenv('LOKI_URL', ''),
                    'username': os.getenv('LOKI_USERNAME', ''),
                    'password': os.getenv('LOKI_PASSWORD', ''),
                    'labels': {'instance': instance_id}
                }
            }
        }
        
        # Write YAML config
        import yaml
        with open(files['config'], 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)
        
        return files['config']
    
    async def create_instance(self, config: BotInstanceConfig) -> BotOperationResult:
        """Create new bot instance"""
        try:
            # Validate instance limit
            if len(self.instances) >= self.max_instances:
                return BotOperationResult(
                    success=False,
                    message=f"Maximum instances limit reached ({self.max_instances})",
                    instance_id=config.instance_id,
                    status=BotStatus.ERROR
                )
            
            # Check if instance already exists
            if config.instance_id in self.instances:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {config.instance_id} already exists",
                    instance_id=config.instance_id,
                    status=BotStatus.ERROR
                )
            
            # Create instance state
            instance_state = BotInstanceState(
                instance_id=config.instance_id,
                config=config,
                status=BotStatus.STOPPED,
                process_info={},
                trading_stats={},
                created_at=datetime.now(),
                last_update=datetime.now()
            )
            
            # Create instance-specific configuration file
            config_file = self._create_instance_config_file(config.instance_id, config)
            
            # Initialize empty state files
            files = self._get_instance_state_files(config.instance_id)
            
            # Create empty bot agents file
            with open(files['bot_agents'], 'w') as f:
                json.dump([], f)
            
            # Store instance
            self.instances[config.instance_id] = instance_state
            self._save_instances_state()
            
            logger.info(f"Created bot instance: {config.instance_id}")
            
            return BotOperationResult(
                success=True,
                message=f"Bot instance {config.instance_id} created successfully",
                instance_id=config.instance_id,
                status=BotStatus.STOPPED
            )
            
        except Exception as e:
            logger.error(f"Error creating instance {config.instance_id}: {e}")
            return BotOperationResult(
                success=False,
                message=f"Error creating instance: {str(e)}",
                instance_id=config.instance_id,
                status=BotStatus.ERROR
            )
    
    async def start_instance(self, instance_id: str) -> BotOperationResult:
        """Start bot instance"""
        try:
            if instance_id not in self.instances:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {instance_id} not found",
                    instance_id=instance_id,
                    status=BotStatus.ERROR
                )
            
            instance = self.instances[instance_id]
            
            if instance.status == BotStatus.RUNNING:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {instance_id} is already running",
                    instance_id=instance_id,
                    status=BotStatus.RUNNING
                )
            
            # Update status
            instance.status = BotStatus.STARTING
            instance.last_update = datetime.now()
            
            # Get instance files
            files = self._get_instance_state_files(instance_id)
            
            # Prepare environment for bot process
            bot_env = os.environ.copy()
            bot_env.update({
                'BOT_INSTANCE_ID': instance_id,
                'BOT_CONFIG_FILE': str(files['config']),
                'BOT_AGENTS_FILE': str(files['bot_agents']),
                'BOT_PAIRS_FILE': str(files['cointegrated_pairs'])
            })
            
            # Start bot process
            cmd = [
                'python', 'main.py',
                '--instance-id', instance_id,
                '--config', str(files['config'])
            ]
            
            process = subprocess.Popen(
                cmd,
                env=bot_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=Path(__file__).parent,
                text=True
            )
            
            # Store process reference
            self.processes[instance_id] = process
            
            # Update instance state
            instance.status = BotStatus.RUNNING
            instance.process_info = {
                'pid': process.pid,
                'started_at': datetime.now(),
                'cmd': ' '.join(cmd)
            }
            instance.last_update = datetime.now()
            
            self._save_instances_state()
            
            logger.info(f"Started bot instance {instance_id} with PID {process.pid}")
            
            return BotOperationResult(
                success=True,
                message=f"Bot instance {instance_id} started successfully",
                instance_id=instance_id,
                status=BotStatus.RUNNING
            )
            
        except Exception as e:
            logger.error(f"Error starting instance {instance_id}: {e}")
            if instance_id in self.instances:
                self.instances[instance_id].status = BotStatus.ERROR
            return BotOperationResult(
                success=False,
                message=f"Error starting instance: {str(e)}",
                instance_id=instance_id,
                status=BotStatus.ERROR
            )
    
    async def stop_instance(self, instance_id: str, force: bool = False) -> BotOperationResult:
        """Stop bot instance"""
        try:
            if instance_id not in self.instances:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {instance_id} not found",
                    instance_id=instance_id,
                    status=BotStatus.ERROR
                )
            
            instance = self.instances[instance_id]
            
            if instance.status == BotStatus.STOPPED:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {instance_id} is already stopped",
                    instance_id=instance_id,
                    status=BotStatus.STOPPED
                )
            
            # Update status
            instance.status = BotStatus.STOPPING
            instance.last_update = datetime.now()
            
            # Stop process if running
            if instance_id in self.processes:
                process = self.processes[instance_id]
                
                if process.poll() is None:  # Process is still running
                    if force:
                        process.kill()
                        logger.info(f"Force killed bot instance {instance_id}")
                    else:
                        process.terminate()
                        logger.info(f"Gracefully terminating bot instance {instance_id}")
                        
                        # Wait for graceful shutdown
                        try:
                            process.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            logger.warning(f"Force killed bot instance {instance_id} after timeout")
                
                # Remove process reference
                del self.processes[instance_id]
            
            # Update instance state
            instance.status = BotStatus.STOPPED
            instance.process_info['stopped_at'] = datetime.now()
            instance.process_info.pop('pid', None)
            instance.last_update = datetime.now()
            
            self._save_instances_state()
            
            logger.info(f"Stopped bot instance: {instance_id}")
            
            return BotOperationResult(
                success=True,
                message=f"Bot instance {instance_id} stopped successfully",
                instance_id=instance_id,
                status=BotStatus.STOPPED
            )
            
        except Exception as e:
            logger.error(f"Error stopping instance {instance_id}: {e}")
            return BotOperationResult(
                success=False,
                message=f"Error stopping instance: {str(e)}",
                instance_id=instance_id,
                status=BotStatus.ERROR
            )
    
    async def delete_instance(self, instance_id: str) -> BotOperationResult:
        """Delete bot instance and cleanup files"""
        try:
            # Stop instance first if running
            if instance_id in self.instances and self.instances[instance_id].status == BotStatus.RUNNING:
                stop_result = await self.stop_instance(instance_id, force=True)
                if not stop_result.success:
                    return stop_result
            
            # Remove from memory
            if instance_id in self.instances:
                del self.instances[instance_id]
            
            # Cleanup state files
            files = self._get_instance_state_files(instance_id)
            for file_path in files.values():
                if file_path.exists():
                    file_path.unlink()
            
            self._save_instances_state()
            
            logger.info(f"Deleted bot instance: {instance_id}")
            
            return BotOperationResult(
                success=True,
                message=f"Bot instance {instance_id} deleted successfully",
                instance_id=instance_id,
                status=BotStatus.STOPPED
            )
            
        except Exception as e:
            logger.error(f"Error deleting instance {instance_id}: {e}")
            return BotOperationResult(
                success=False,
                message=f"Error deleting instance: {str(e)}",
                instance_id=instance_id,
                status=BotStatus.ERROR
            )
    
    async def get_instance_status(self, instance_id: str) -> Optional[BotInstanceStatus]:
        """Get current status of bot instance"""
        if instance_id not in self.instances:
            return None
        
        instance = self.instances[instance_id]
        
        # Update process info if running
        if instance_id in self.processes:
            process = self.processes[instance_id]
            if process.poll() is not None:  # Process died
                instance.status = BotStatus.ERROR
                instance.process_info['stopped_at'] = datetime.now()
                del self.processes[instance_id]
            else:
                # Update resource usage
                try:
                    proc = psutil.Process(process.pid)
                    instance.process_info.update({
                        'cpu_usage': proc.cpu_percent(),
                        'memory_usage_mb': proc.memory_info().rss / (1024 * 1024)
                    })
                except psutil.NoSuchProcess:
                    instance.status = BotStatus.ERROR
        
        # Update trading stats from state files
        self._update_instance_trading_stats(instance_id)
        
        instance.last_update = datetime.now()
        return instance.to_api_status()
    
    def _update_instance_trading_stats(self, instance_id: str):
        """Update trading statistics from bot state files"""
        try:
            files = self._get_instance_state_files(instance_id)
            
            # Read bot agents file for active positions
            if files['bot_agents'].exists():
                with open(files['bot_agents'], 'r') as f:
                    agents = json.load(f)
                    active_positions = len([a for a in agents if a.get('pair_status') == 'LIVE'])
                    self.instances[instance_id].trading_stats['active_positions'] = active_positions
            
            # Additional stats can be added here (total trades, P&L, etc.)
            
        except Exception as e:
            logger.error(f"Error updating trading stats for {instance_id}: {e}")
    
    async def list_instances(self) -> List[BotInstanceStatus]:
        """Get list of all bot instances"""
        statuses = []
        for instance_id in list(self.instances.keys()):
            status = await self.get_instance_status(instance_id)
            if status:
                statuses.append(status)
        
        return statuses
    
    async def cleanup_dead_processes(self):
        """Cleanup dead processes and update instance statuses"""
        for instance_id in list(self.processes.keys()):
            process = self.processes[instance_id]
            if process.poll() is not None:  # Process is dead
                logger.warning(f"Found dead process for instance {instance_id}")
                if instance_id in self.instances:
                    self.instances[instance_id].status = BotStatus.ERROR
                    self.instances[instance_id].process_info['stopped_at'] = datetime.now()
                del self.processes[instance_id]
        
        self._save_instances_state()


# Global bot manager instance
bot_manager = BotInstanceManager()