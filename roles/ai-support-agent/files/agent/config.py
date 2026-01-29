"""
Configuration management for the AI Support Agent (Claude Code CLI version).
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Config:
    """Agent configuration loaded from environment variables."""
    
    # Discord settings
    discord_token: str
    guild_id: Optional[int] = None
    command_prefix: str = "!"
    environment: str = "dev"
    
    # Channel IDs (loaded from env)
    channels: Dict[str, int] = field(default_factory=dict)
    
    # Channel provisioning
    auto_provision_channels: bool = True
    agent_category_name: str = "AI Agent"
    agent_channel_name: str = "claude-agent"
    
    # Claude Code CLI Configuration
    codebase_path: str = "/app/codebase"
    
    # Behavior settings
    auto_respond: bool = True
    auto_remediate: bool = False  # Disabled by default for safety
    
    @property
    def allow_edit_tools(self) -> bool:
        """Allow Write/Edit tools only in development environment."""
        return self.environment.lower() == "dev"
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables."""
        
        # Required
        discord_token = os.environ.get('DISCORD_TOKEN')
        if not discord_token:
            raise ValueError("DISCORD_TOKEN environment variable is required")
        
        # Optional guild ID
        guild_id = os.environ.get('DISCORD_GUILD_ID')
        guild_id = int(guild_id) if guild_id else None
        
        # Channel configuration
        channels = {}
        channel_mappings = {
            'alerts': 'CHANNEL_ALERTS',
            'critical': 'CHANNEL_CRITICAL',
            'status': 'CHANNEL_STATUS',
            'infrastructure': 'CHANNEL_INFRASTRUCTURE',
            'docker': 'CHANNEL_DOCKER',
            'ai_agent': 'CHANNEL_AI_AGENT',
        }
        
        for key, env_var in channel_mappings.items():
            value = os.environ.get(env_var)
            if value:
                channels[key] = int(value)
        
        return cls(
            discord_token=discord_token,
            guild_id=guild_id,
            command_prefix=os.environ.get('COMMAND_PREFIX', '!'),
            environment=os.environ.get('ENVIRONMENT', 'dev'),
            channels=channels,
            auto_provision_channels=os.environ.get('AUTO_PROVISION_CHANNELS', 'true').lower() == 'true',
            agent_category_name=os.environ.get('AGENT_CATEGORY_NAME', 'AI Agent'),
            agent_channel_name=os.environ.get('AGENT_CHANNEL_NAME', 'claude-agent'),
            codebase_path=os.environ.get('CODEBASE_PATH', '/app/codebase'),
            auto_respond=os.environ.get('AUTO_RESPOND', 'true').lower() == 'true',
            auto_remediate=os.environ.get('AUTO_REMEDIATE', 'false').lower() == 'true',
        )
    
    def get_channel(self, name: str) -> Optional[int]:
        """Get a channel ID by name."""
        return self.channels.get(name)
