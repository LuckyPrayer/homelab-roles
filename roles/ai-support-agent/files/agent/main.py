"""
Oracle - Homelab AI Support Agent
An autonomous AI agent using Claude Code CLI for monitoring, troubleshooting, 
and resolving homelab issues. Responds to Discord alerts and reports actions taken.

Oracle is the all-seeing support agent for your homelab infrastructure.
"""

import os
import asyncio
import logging
import json
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass, field

import discord
from discord import app_commands
from discord.ext import commands

from config import Config

# Infrastructure context for accurate responses
INFRASTRUCTURE_CONTEXT = """
## Homelab Infrastructure Map

### Development Environment (VLAN 20: 192.168.20.0/24)
| Host | IP | Services | Ports |
|------|----|---------|-|
| **hermes-dev** | 192.168.68.10 | Jump host, Traefik (external proxy) | SSH:22, HTTP:80, HTTPS:443, Traefik metrics:8082 |
| **orion-dev** | 192.168.20.100 | Traefik (local), Minecraft, Vaultwarden, N8N, Mealie | Traefik:8080, Minecraft:25565, Vaultwarden:8200, N8N:5678, Mealie:9000 |
| **hephaestus-dev** | 192.168.20.200 | Harbor (registry), Documentation server, Discord Bot | Harbor:8082, Docs:8081, Bot webhook:8085 |
| **argus-dev** | 192.168.20.50 | Grafana, Prometheus, Loki, Alertmanager, Oracle AI Agent | Grafana:3000, Prometheus:9090, Loki:3100, Alertmanager:9093 |

### Key Services Quick Reference
- **Documentation**: hephaestus-dev:8081 (container: homelab-docs)
- **Harbor Registry**: hephaestus-dev:8082 or registry.dev.thebozic.com
- **Grafana**: argus-dev:3000 or grafana.dev.thebozic.com
- **Prometheus**: argus-dev:9090
- **Discord Bot**: hephaestus-dev:8085 (container: homelab-discord-bot)
- **Oracle AI Agent**: argus-dev (container: homelab-oracle) - THIS IS YOU, running locally

### SSH Access - YOU ARE THE ORACLE USER
You run as the 'oracle' user with SSH keys configured. Use simple hostnames:
```bash
# SSH by hostname (recommended) - uses oracle user automatically
ssh hephaestus-dev "docker ps"
ssh orion-dev "docker logs homelab-minecraft --tail 20"
ssh hermes-dev "docker ps"

# The SSH config automatically handles:
# - ProxyJump through hermes-dev for VLAN 20 hosts
# - Using your oracle SSH key
# - Disabling host key checking
```

### Local Commands (on argus-dev where you run)
Since you're running on argus-dev, you can run local docker commands directly:
```bash
# Local containers (Grafana, Prometheus, Loki, etc.)
docker ps
docker logs homelab-grafana --tail 20
```

### Remote Diagnostics Examples
```bash
# Check docs container on hephaestus-dev
ssh hephaestus-dev "docker ps -a --filter name=homelab-docs"
ssh hephaestus-dev "docker logs homelab-docs --tail 30"
ssh hephaestus-dev "curl -s localhost:8081 -o /dev/null -w '%{http_code}'"

# Check services on orion-dev
ssh orion-dev "docker ps"
ssh orion-dev "curl -s localhost:8200/alive"  # Vaultwarden health

# Network diagnostics
ping -c 2 192.168.20.200
curl -s http://192.168.20.200:8081 -o /dev/null -w '%{http_code}'
```

### Container Naming Convention
- All containers prefixed with `homelab-`
- Example: homelab-docs, homelab-discord-bot, homelab-grafana, homelab-oracle
"""

# Configure logging
def setup_logging():
    """Set up logging with fallback if file logging fails."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    handlers = [logging.StreamHandler()]
    
    log_file = '/app/logs/agent.log'
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    except (PermissionError, OSError) as e:
        print(f"Warning: Could not set up file logging: {e}")
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=handlers
    )
    return logging.getLogger('oracle')

logger = setup_logging()


# === Session Management ===

@dataclass
class ChannelSession:
    """Tracks a Claude session for a Discord channel."""
    session_id: str
    channel_id: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_count: int = 0
    total_cost: float = 0.0


class SessionManager:
    """Manages Claude sessions per Discord channel."""
    
    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[int, ChannelSession] = {}
        self.session_timeout = session_timeout_minutes
    
    def get_or_create_session(self, channel_id: int) -> tuple[str, bool]:
        """
        Get existing session or create new one for a channel.
        Returns (session_id, is_resume) tuple.
        """
        now = datetime.now(timezone.utc)
        
        if channel_id in self.sessions:
            session = self.sessions[channel_id]
            # Check if session is still valid (not expired)
            age_minutes = (now - session.last_used).total_seconds() / 60
            if age_minutes < self.session_timeout:
                session.last_used = now
                session.message_count += 1
                return session.session_id, True  # Resume existing session
        
        # Create new session
        new_session_id = str(uuid.uuid4())
        self.sessions[channel_id] = ChannelSession(
            session_id=new_session_id,
            channel_id=channel_id,
            message_count=1
        )
        return new_session_id, False  # New session
    
    def reset_session(self, channel_id: int) -> str:
        """Force create a new session for a channel."""
        new_session_id = str(uuid.uuid4())
        self.sessions[channel_id] = ChannelSession(
            session_id=new_session_id,
            channel_id=channel_id,
            message_count=1
        )
        return new_session_id
    
    def get_session_info(self, channel_id: int) -> Optional[ChannelSession]:
        """Get session info for a channel."""
        return self.sessions.get(channel_id)
    
    def update_cost(self, channel_id: int, cost: float):
        """Update the total cost for a session."""
        if channel_id in self.sessions:
            self.sessions[channel_id].total_cost += cost


# === Discord Approval UI Components ===

class ApprovalView(discord.ui.View):
    """Discord UI for approving/denying Oracle actions."""
    
    def __init__(self, action_description: str, command_to_run: str, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.action_description = action_description
        self.command_to_run = command_to_run
        self.approved = None
        self.responder = None
        
    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.approved = True
        self.responder = interaction.user
        await interaction.response.send_message(
            f"✅ **Approved** by {interaction.user.mention}. Executing...",
            ephemeral=False
        )
        self.stop()
        
    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.red)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.approved = False
        self.responder = interaction.user
        await interaction.response.send_message(
            f"❌ **Denied** by {interaction.user.mention}. Action cancelled.",
            ephemeral=False
        )
        self.stop()
        
    @discord.ui.button(label="ℹ️ Details", style=discord.ButtonStyle.secondary)
    async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"**Command to execute:**\n```bash\n{self.command_to_run[:1900]}\n```",
            ephemeral=True
        )

    async def on_timeout(self):
        self.approved = False


class ClaudeCodeExecutor:
    """
    Wrapper for Claude Code CLI execution.
    Handles running Claude with prompts and collecting responses.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.codebase_path = Path(config.codebase_path)
    
    def _get_disallowed_tools(self) -> Optional[List[str]]:
        """Get list of disallowed tools based on environment."""
        # Always disallow interactive tools that don't work in --print mode
        always_disallowed = ["AskUserQuestion"]
        
        if self.config.allow_edit_tools:
            # Dev environment: allow most tools, but not interactive ones
            return always_disallowed
        else:
            # Non-dev: block write/edit tools plus interactive
            return always_disallowed + ["Write", "Edit", "MultiEdit"]
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with infrastructure context for accurate responses."""
        return f"""You are Oracle, the AI support agent for a homelab infrastructure.

{INFRASTRUCTURE_CONTEXT}

## Execution Rules
1. **Be efficient** - Use SSH commands directly, don't search codebase unless specifically needed
2. **Use the Infrastructure Map** to identify correct hosts and ports - DON'T search for this info
3. **SSH pattern**: VLAN 20 hosts use ProxyJump through hermes-dev automatically via SSH config
4. **Container names** are prefixed with `homelab-` (e.g., homelab-docs, homelab-harbor-core)
5. **Harbor containers**: harbor-core, harbor-portal, harbor-db, harbor-redis, harbor-registry, harbor-jobservice, harbor-registryctl
6. **Don't ask questions** - You're running in non-interactive mode. Make reasonable assumptions.
7. **Keep responses concise** - Focus on actions taken and results.

## Environment: {self.config.environment.upper()}
- Edit Tools: {'ENABLED' if self.config.allow_edit_tools else 'DISABLED'}
"""
        
    async def execute(
        self,
        prompt: str,
        allowed_tools: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None,
        max_budget_usd: float = 1.0,
        timeout: int = 450,
        skip_permissions: bool = False,
        session_id: Optional[str] = None,
        resume_session: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a prompt using Claude Code CLI.
        
        Args:
            prompt: The prompt/task for Claude
            allowed_tools: List of allowed tools (None = all allowed)
            disallowed_tools: List of disallowed tools
            max_budget_usd: Maximum budget in USD for the request
            timeout: Timeout in seconds
            skip_permissions: If True, skip tool permission prompts (use after Discord approval)
            session_id: Session ID for conversation continuity
            resume_session: If True and session_id provided, resume existing session
            
        Returns:
            Dict with 'success', 'output', 'cost', and 'session_id'
        """
        try:
            # Build the claude command
            cmd = ["claude", "--print", "--output-format", "json"]
            
            # Session management - resume if continuing conversation
            if resume_session and session_id:
                cmd.append("-r")  # Resume flag
            
            if session_id:
                cmd.extend(["--session-id", session_id])
            
            # Skip permission prompts if approved via Discord
            if skip_permissions:
                cmd.append("--dangerously-skip-permissions")
            
            # Limit turns to control token usage
            cmd.extend(["--max-turns", "15"])
            
            # Use Claude Opus 4.5 for best reasoning capability
            cmd.extend(["--model", "claude-opus-4-5-20250514"])
            
            # Add allowed tools if specified
            if allowed_tools:
                cmd.extend(["--allowedTools", ",".join(allowed_tools)])
            
            # Add disallowed tools if specified
            if disallowed_tools:
                cmd.extend(["--disallowedTools", ",".join(disallowed_tools)])
            
            # Add budget limit for safety (in USD)
            cmd.extend(["--max-budget-usd", str(max_budget_usd)])
            
            # Write system prompt to temp file for context injection
            system_prompt = self._build_system_prompt()
            system_prompt_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
            try:
                system_prompt_file.write(system_prompt)
                system_prompt_file.close()
                cmd.extend(["--system-prompt", system_prompt_file.name])
            except Exception as e:
                logger.warning(f"Could not write system prompt file: {e}")
            
            # Add the prompt as a positional argument (last)
            cmd.append(prompt)
            
            logger.info(f"Executing Claude CLI in {self.codebase_path}...")
            logger.debug(f"Command: {' '.join(cmd[:8])}...")
            
            # Run in the codebase directory
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.codebase_path)
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            stdout_text = stdout.decode('utf-8', errors='replace')
            stderr_text = stderr.decode('utf-8', errors='replace')
            
            # Log execution result for debugging
            logger.info(f"Claude CLI completed with exit code {process.returncode}")
            if stderr_text:
                logger.warning(f"Claude CLI stderr: {stderr_text[:500]}")
            if process.returncode != 0:
                logger.error(f"Claude CLI failed. stdout: {stdout_text[:500]}")
            
            # Clean up system prompt temp file
            try:
                if 'system_prompt_file' in locals():
                    os.unlink(system_prompt_file.name)
            except Exception:
                pass
            
            # Try to parse JSON output
            try:
                result = json.loads(stdout_text)
                return {
                    'success': process.returncode == 0,
                    'output': result.get('result', stdout_text),
                    'cost': result.get('cost_usd', 0),
                    'session_id': result.get('session_id', ''),
                    'num_turns': result.get('num_turns', 0),
                    'raw': result
                }
            except json.JSONDecodeError:
                # Return raw output if not JSON
                error_msg = stderr_text if stderr_text else None
                # If no stderr but command failed, include stdout as potential error info
                if process.returncode != 0 and not error_msg:
                    error_msg = f"Command failed (exit code {process.returncode}). Output: {stdout_text[:500]}" if stdout_text else f"Command failed with exit code {process.returncode}"
                return {
                    'success': process.returncode == 0,
                    'output': stdout_text,
                    'cost': 0,
                    'session_id': '',
                    'error': error_msg
                }
                
        except asyncio.TimeoutError:
            return {
                'success': False,
                'output': '',
                'error': f'Claude CLI timed out after {timeout} seconds'
            }
        except FileNotFoundError:
            return {
                'success': False,
                'output': '',
                'error': 'Claude CLI not found. Ensure it is installed and in PATH.'
            }
        except Exception as e:
            logger.exception("Claude CLI execution failed")
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }
    
    async def investigate_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Investigate an alert using Claude Code CLI.
        """
        prompt = f"""You are investigating an infrastructure alert in a homelab environment.

## Alert Details
- **Title:** {alert_data.get('title', 'Unknown')}
- **Level:** {alert_data.get('level', 'unknown')}
- **Description:** {alert_data.get('description', 'No description')}
- **Source Channel:** {alert_data.get('channel', 'unknown')}
- **Additional Fields:** {json.dumps(alert_data.get('fields', {}), indent=2)}
- **Timestamp:** {alert_data.get('timestamp', 'unknown')}

## Your Tasks
1. **Search the codebase** for relevant documentation, playbooks, and configuration files related to this alert
2. **Analyze** the likely cause based on the alert details and codebase context
3. **Identify** the affected service(s) and their configuration
4. **Suggest diagnostic commands** that should be run to gather more information
5. **Propose remediation steps** if applicable

## Codebase Structure
This is a homelab infrastructure managed with:
- Ansible playbooks and roles in `playbooks/`
- Documentation in `docs/`
- Inventory files in `inventories/`
- Host variables in `host_vars/`
- Group variables in `group_vars/`

## Output Format
Provide your response as a structured analysis with:
- Summary of findings
- Likely root cause(s)
- Relevant files found in the codebase
- Recommended diagnostic commands
- Proposed remediation steps (if any)
- Risk assessment for any proposed actions
"""
        
        # Use environment-based tool restrictions
        return await self.execute(
            prompt, 
            disallowed_tools=self._get_disallowed_tools(),
            timeout=180
        )
    
    async def run_diagnostics(
        self,
        alert_data: Dict[str, Any],
        analysis: str
    ) -> Dict[str, Any]:
        """
        Run diagnostic commands based on initial analysis.
        """
        prompt = f"""Based on the following alert and analysis, run diagnostic commands to gather more information.

## Alert
- **Title:** {alert_data.get('title')}
- **Level:** {alert_data.get('level')}
- **Description:** {alert_data.get('description', '')}

## Previous Analysis
{analysis[:3000]}

## Your Tasks
1. Run appropriate diagnostic commands (docker ps, logs, status checks, etc.)
2. Analyze the output of each command
3. Correlate findings with the alert
4. Provide updated assessment

## Safety Notes
- Only run read-only diagnostic commands
- Do not restart services or make changes yet
- Focus on gathering information

## Allowed Commands
You may run these types of commands:
- docker ps, docker logs, docker inspect
- systemctl status
- journalctl
- curl (for health checks)
- ping, dig, nslookup
- df, free, top -bn1
- ps aux, netstat, ss
- cat, grep, head, tail (for reading files/logs)
"""
        
        # Use environment-based tool restrictions
        return await self.execute(
            prompt,
            allowed_tools=[
                "Read",
                "Glob",
                "Grep",
                "Bash",
            ],
            disallowed_tools=self._get_disallowed_tools(),
            timeout=120
        )
    
    async def attempt_remediation(
        self,
        alert_data: Dict[str, Any],
        diagnostics: str,
        approved_actions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Attempt to remediate an issue.
        """
        approved_text = ""
        if approved_actions:
            approved_text = f"\n## Pre-Approved Actions\nThe following actions have been approved:\n" + \
                           "\n".join(f"- {action}" for action in approved_actions)
        
        prompt = f"""Based on the diagnostics, attempt to remediate the issue.

## Alert
- **Title:** {alert_data.get('title')}
- **Level:** {alert_data.get('level')}

## Diagnostic Findings
{diagnostics[:3000]}
{approved_text}

## Your Tasks
1. Determine the most appropriate remediation action
2. Execute the remediation
3. Verify the fix was successful
4. Document what was done

## Allowed Remediation Actions
- Restart containers: docker restart <container>
- Start stopped containers: docker start <container>
- Check and report status: docker ps, systemctl status
- Health checks: curl to service endpoints

## Safety Rules
- Only restart containers if necessary
- Do not delete data or configurations
- Do not modify files in the codebase
- Verify service health after any changes
- If unsure, document the issue and recommend manual intervention
"""
        
        # Use environment-based tool restrictions
        return await self.execute(
            prompt,
            allowed_tools=["Read", "Glob", "Grep", "Bash"],
            disallowed_tools=self._get_disallowed_tools(),
            timeout=120
        )


class OracleAgent(commands.Bot):
    """Oracle - Main AI Support Agent bot class using Claude Code CLI."""
    
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix=config.command_prefix,
            intents=intents,
            description="Oracle - Homelab AI Support Agent (Claude Code)"
        )
        
        self.config = config
        self.start_time = datetime.now(timezone.utc)
        self.claude_executor = ClaudeCodeExecutor(config)
        
        # Track ongoing incidents
        self.active_incidents: Dict[str, Dict[str, Any]] = {}
        
        # Auto-response mode
        self.auto_respond = config.auto_respond
        
        # Total cost tracking
        self.total_cost_usd = 0.0
        
        # Channel provisioning flag
        self._channels_provisioned = False
        
        # Conversation channel reference
        self.agent_channel: Optional[discord.TextChannel] = None
        
        # Session manager for per-channel Claude sessions
        self.session_manager = SessionManager(session_timeout_minutes=30)
        
    async def setup_hook(self):
        """Called when the bot is starting up."""
        logger.info("Setting up Oracle AI Support Agent with Claude Code CLI...")
        
        # Register tree error handler
        @self.tree.error
        async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            """Handle command tree errors (catches CommandNotFound before on_app_command_error)."""
            if isinstance(error, app_commands.CommandNotFound):
                logger.debug(f"Unknown command attempted (tree handler): {error}")
                return
            # Let other errors propagate to on_app_command_error
            raise error
        
        # Verify Claude CLI is available
        try:
            process = await asyncio.create_subprocess_exec(
                "claude", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            version = stdout.decode().strip()
            logger.info(f"Claude CLI version: {version}")
        except FileNotFoundError:
            logger.error("Claude CLI not found! Please install it first.")
            raise RuntimeError("Claude CLI not found")
        
        # Verify codebase path exists
        if not Path(self.config.codebase_path).exists():
            logger.warning(f"Codebase path does not exist: {self.config.codebase_path}")
        else:
            logger.info(f"Codebase path: {self.config.codebase_path}")
        
        # Sync slash commands
        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Synced commands to guild {self.config.guild_id}")
        else:
            await self.tree.sync()
            logger.info("Synced global commands")
    
    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        logger.info(f"Auto-respond mode: {self.auto_respond}")
        logger.info(f"Environment: {self.config.environment} (Edit tools: {'enabled' if self.config.allow_edit_tools else 'disabled'})")
        
        # Provision agent channel if enabled
        if not self._channels_provisioned and self.config.auto_provision_channels:
            await self._provision_agent_channel()
        
        # Set presence
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"🔮 Oracle | {self.config.environment.upper()}"
        )
        await self.change_presence(activity=activity)
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle application command errors gracefully."""
        if isinstance(error, app_commands.CommandNotFound):
            # Old command names or stale cache - ignore silently
            logger.debug(f"Unknown command attempted: {error}")
            return
        
        # Log other errors
        logger.error(f"App command error: {error}", exc_info=error)
        
        # Try to respond to user if we can
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ An error occurred: {str(error)[:200]}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ An error occurred: {str(error)[:200]}",
                    ephemeral=True
                )
        except Exception:
            pass  # Can't respond, interaction may have timed out
    
    async def _provision_agent_channel(self):
        """Create or find the agent conversation channel."""
        for guild in self.guilds:
            # Skip if guild_id is configured and doesn't match
            if self.config.guild_id and guild.id != self.config.guild_id:
                continue
            
            logger.info(f"Provisioning agent channel for guild: {guild.name}")
            
            try:
                # Find or create category
                category = discord.utils.get(guild.categories, name=self.config.agent_category_name)
                if not category:
                    logger.info(f"Creating category: {self.config.agent_category_name}")
                    category = await guild.create_category(
                        self.config.agent_category_name,
                        reason="Oracle AI Agent channel provisioning"
                    )
                
                # Find or create agent channel
                channel_name = f"{self.config.agent_channel_name}-{self.config.environment}"
                channel = discord.utils.get(category.channels, name=channel_name)
                
                if not channel:
                    logger.info(f"Creating channel: {channel_name}")
                    channel = await guild.create_text_channel(
                        channel_name,
                        category=category,
                        topic=f"🔮 Oracle AI Agent | Environment: {self.config.environment.upper()} | Use /ask-oracle to interact",
                        reason="Oracle AI Agent channel provisioning"
                    )
                    
                    # Send welcome message
                    await channel.send(
                        embed=discord.Embed(
                            title="🔮 Oracle AI Agent Ready",
                            description=f"Greetings! I am Oracle, your homelab AI support agent.\n\n"
                                       f"**Environment:** `{self.config.environment.upper()}`\n"
                                       f"**Edit Tools:** {'✅ Enabled' if self.config.allow_edit_tools else '❌ Disabled'}\n"
                                       f"**Auto-Respond:** {'✅ Enabled' if self.auto_respond else '❌ Disabled'}\n"
                                       f"**Auto-Remediate:** {'✅ Enabled' if self.config.auto_remediate else '❌ Disabled'}\n\n"
                                       f"**Available Commands:**\n"
                                       f"• `/ask-oracle <question>` - Ask me anything about the homelab\n"
                                       f"• `/oracle-status` - View my current status\n"
                                       f"• `/run-task <task>` - Run a custom task (admin)\n"
                                       f"• `/incidents` - List active incidents\n\n"
                                       f"I monitor alerts and can diagnose and resolve issues automatically.",
                            color=discord.Color.purple(),
                            timestamp=datetime.now(timezone.utc)
                        ).set_footer(text="Powered by Claude Code CLI")
                    )
                
                self.agent_channel = channel
                self.config.channels['ai_agent'] = channel.id
                logger.info(f"Agent channel ready: {channel.name} (ID: {channel.id})")
                
            except discord.Forbidden:
                logger.error(f"Missing permissions to create channels in {guild.name}")
            except Exception as e:
                logger.exception(f"Error provisioning channel: {e}")
        
        self._channels_provisioned = True
        
        # Set presence
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"🔮 Oracle | {self.config.environment.upper()}"
        )
        await self.change_presence(activity=activity)
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages - especially alerts and agent channel conversations."""
        # Ignore own messages
        if message.author == self.user:
            return
        
        # Handle conversations in the agent channel
        agent_channel_id = self.config.channels.get('ai_agent')
        if agent_channel_id and message.channel.id == agent_channel_id:
            # Respond to direct messages in agent channel (not commands)
            if not message.content.startswith(self.config.command_prefix) and not message.content.startswith('/'):
                await self._handle_agent_conversation(message)
                return
        
        # Check if this is in a monitored alert channel
        alert_channels = [
            self.config.channels.get('alerts'),
            self.config.channels.get('critical'),
            self.config.channels.get('infrastructure'),
            self.config.channels.get('docker'),
        ]
        
        if message.channel.id in [c for c in alert_channels if c]:
            # Check if message is from the monitoring bot or contains alert embeds
            if message.embeds or self._is_alert_message(message):
                await self.handle_alert(message)
        
        # Process commands
        await self.process_commands(message)
    
    def _is_alert_message(self, message: discord.Message) -> bool:
        """Check if a message appears to be an alert."""
        alert_indicators = ['🚨', '⚠️', '🔴', 'CRITICAL', 'WARNING', 'ERROR', 'ALERT', 'DOWN']
        content = message.content.upper()
        return any(indicator in content or indicator in message.content for indicator in alert_indicators)
    
    async def _handle_agent_conversation(self, message: discord.Message):
        """Handle a conversation message in the agent channel."""
        # Show typing indicator
        async with message.channel.typing():
            logger.info(f"Handling conversation from {message.author.name}: {message.content[:50]}...")
            
            # Get or create session for this channel
            session_id, is_resume = self.session_manager.get_or_create_session(message.channel.id)
            session_info = self.session_manager.get_session_info(message.channel.id)
            
            if is_resume:
                logger.info(f"Resuming session {session_id[:8]}... (message #{session_info.message_count})")
            else:
                logger.info(f"Starting new session {session_id[:8]}...")
            
            # Build the prompt with context about capabilities
            edit_tools_note = ""
            if self.config.allow_edit_tools:
                edit_tools_note = "\nYou have WRITE and EDIT access to the codebase in this development environment. You can create, modify, and delete files if needed."
            else:
                edit_tools_note = "\nYou have READ-ONLY access to the codebase. You cannot modify files."
            
            prompt = f"""A user is asking you a question in Discord.
{edit_tools_note}

## User Message
**User:** {message.author.name}
**Message:** {message.content}

## Your Capabilities
- Search and read the homelab codebase (Ansible playbooks, documentation, configs)
- Run diagnostic commands via Bash (docker ps, docker logs, curl, ssh, etc.)
- Analyze infrastructure issues
- {'Create, edit, and modify files in the codebase' if self.config.allow_edit_tools else 'Suggest changes (but cannot modify files directly)'}

## ACCURACY REQUIREMENTS
1. **For status questions:** ALWAYS run live diagnostic commands first (docker ps, curl endpoints)
2. **For configuration questions:** Search the codebase AND verify against the Infrastructure Map
3. **Never guess service locations:** Use the host/port mapping in your system prompt
4. **SSH to remote hosts:** Use `ssh -o ProxyJump=root@192.168.68.10 root@<target_ip> "<command>"` for VLAN 20 hosts
5. **Verify before responding:** If unsure, run a command to check

## Example Verification Commands
- Check container status: `ssh -o ProxyJump=root@192.168.68.10 root@192.168.20.200 "docker ps -a --filter name=homelab-docs"`
- Check service health: `curl -s http://192.168.20.200:8081/ -o /dev/null -w '%{{http_code}}'`
- Check logs: `ssh -o ProxyJump=root@192.168.68.10 root@<host> "docker logs <container> --tail 20"`

Respond directly and accurately to the user's question.
"""
            
            result = await self.claude_executor.execute(
                prompt,
                disallowed_tools=self.claude_executor._get_disallowed_tools(),
                timeout=180,
                session_id=session_id,
                resume_session=is_resume
            )
            
            self.total_cost_usd += result.get('cost', 0)
            self.session_manager.update_cost(message.channel.id, result.get('cost', 0))
            
            if result['success']:
                output = result['output']
                
                # Split long responses
                if len(output) > 1900:
                    # Send as multiple messages
                    chunks = [output[i:i+1900] for i in range(0, len(output), 1900)]
                    for i, chunk in enumerate(chunks[:5]):  # Max 5 chunks
                        if i == 0:
                            await message.reply(chunk)
                        else:
                            await message.channel.send(chunk)
                    if len(chunks) > 5:
                        await message.channel.send("... (response truncated)")
                else:
                    await message.reply(output)
                
                # Add cost footer with session info
                session_info = self.session_manager.get_session_info(message.channel.id)
                if result.get('cost', 0) > 0:
                    await message.channel.send(
                        f"_Cost: ${result.get('cost', 0):.4f} | Session: ...{session_id[-8:]} ({session_info.message_count} msgs, ${session_info.total_cost:.4f} total)_",
                        silent=True
                    )
            else:
                await message.reply(
                    f"❌ Sorry, I encountered an error: {result.get('error', 'Unknown error')}"
                )

    async def handle_alert(self, message: discord.Message):
        """Process an incoming alert and determine response."""
        logger.info(f"Processing alert from channel {message.channel.name}")
        
        # Extract alert information
        alert_data = await self._parse_alert(message)
        
        if not alert_data:
            logger.warning("Could not parse alert data from message")
            return
        
        # Create incident tracking
        incident_id = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        self.active_incidents[incident_id] = {
            'id': incident_id,
            'alert': alert_data,
            'status': 'investigating',
            'started_at': datetime.now(timezone.utc),
            'message': message,
            'thread': None,
            'cost_usd': 0.0
        }
        
        # Create a thread for this incident
        try:
            thread = await message.create_thread(
                name=f"🤖 {incident_id}: {alert_data.get('title', 'Investigation')[:50]}",
                auto_archive_duration=1440  # 24 hours
            )
            self.active_incidents[incident_id]['thread'] = thread
            
            # Send initial response
            await thread.send(
                embed=discord.Embed(
                    title="🤖 Claude AI Agent Investigating",
                    description=f"**Incident ID:** `{incident_id}`\n\n"
                               f"I'm using Claude Code to analyze this alert and search the codebase for relevant information.",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc)
                ).set_footer(text="Powered by Claude Code CLI")
            )
        except Exception as e:
            logger.error(f"Could not create thread: {e}")
            thread = message.channel
            self.active_incidents[incident_id]['thread'] = thread
        
        # Start investigation
        if self.auto_respond:
            asyncio.create_task(self._investigate_incident(incident_id))
        else:
            await thread.send(
                "⏸️ Auto-respond is disabled. Use `/investigate` to start investigation."
            )
    
    async def _parse_alert(self, message: discord.Message) -> Optional[Dict[str, Any]]:
        """Parse alert data from a Discord message."""
        alert_data = {
            'raw_content': message.content,
            'timestamp': message.created_at.isoformat(),
            'channel': message.channel.name,
            'author': str(message.author),
        }
        
        # Parse embeds if present
        if message.embeds:
            embed = message.embeds[0]
            alert_data['title'] = embed.title or 'Unknown Alert'
            alert_data['description'] = embed.description or ''
            alert_data['fields'] = {f.name: f.value for f in embed.fields}
            alert_data['level'] = self._determine_alert_level(embed)
        else:
            alert_data['title'] = message.content[:100] if message.content else 'Unknown Alert'
            alert_data['description'] = message.content
            alert_data['level'] = 'warning'
        
        return alert_data
    
    def _determine_alert_level(self, embed: discord.Embed) -> str:
        """Determine alert severity level from embed."""
        if embed.color:
            if embed.color.value == discord.Color.red().value:
                return 'critical'
            elif embed.color.value == discord.Color.orange().value:
                return 'warning'
        
        title = (embed.title or '').upper()
        if 'CRITICAL' in title or '🚨' in (embed.title or ''):
            return 'critical'
        elif 'WARNING' in title or '⚠️' in (embed.title or ''):
            return 'warning'
        
        return 'info'
    
    async def _investigate_incident(self, incident_id: str):
        """Investigate and attempt to resolve an incident using Claude Code."""
        incident = self.active_incidents.get(incident_id)
        if not incident:
            return
        
        thread = incident['thread']
        alert_data = incident['alert']
        
        try:
            # Step 1: Initial investigation with Claude
            await thread.send("📚 **Step 1:** Analyzing alert and searching codebase...")
            
            investigation = await self.claude_executor.investigate_alert(alert_data)
            incident['cost_usd'] += investigation.get('cost', 0)
            
            if investigation['success']:
                # Truncate output for Discord (max 4096 chars for embed description)
                output = investigation['output']
                if len(output) > 3500:
                    output = output[:3500] + "\n\n... (truncated)"
                
                await thread.send(
                    embed=discord.Embed(
                        title="📋 Initial Analysis",
                        description=output[:4096],
                        color=discord.Color.blue()
                    )
                )
            else:
                await thread.send(
                    embed=discord.Embed(
                        title="⚠️ Investigation Issue",
                        description=f"```\n{investigation.get('error', 'Unknown error')}\n```",
                        color=discord.Color.orange()
                    )
                )
                return
            
            # Step 2: Run diagnostics
            await thread.send("🔍 **Step 2:** Running diagnostic commands...")
            
            diagnostics = await self.claude_executor.run_diagnostics(
                alert_data,
                investigation['output']
            )
            incident['cost_usd'] += diagnostics.get('cost', 0)
            
            if diagnostics['success']:
                output = diagnostics['output']
                if len(output) > 3500:
                    output = output[:3500] + "\n\n... (truncated)"
                
                await thread.send(
                    embed=discord.Embed(
                        title="🔍 Diagnostic Results",
                        description=output[:4096],
                        color=discord.Color.blue()
                    )
                )
            else:
                await thread.send(f"⚠️ Diagnostics issue: {diagnostics.get('error', 'Unknown error')}")
            
            # Step 3: Attempt remediation if enabled
            if self.config.auto_remediate:
                await thread.send("🔧 **Step 3:** Attempting automatic remediation...")
                
                remediation = await self.claude_executor.attempt_remediation(
                    alert_data,
                    diagnostics.get('output', '') or investigation.get('output', '')
                )
                incident['cost_usd'] += remediation.get('cost', 0)
                
                if remediation['success']:
                    output = remediation['output']
                    if len(output) > 3500:
                        output = output[:3500] + "\n\n... (truncated)"
                    
                    await thread.send(
                        embed=discord.Embed(
                            title="🔧 Remediation Results",
                            description=output[:4096],
                            color=discord.Color.green()
                        )
                    )
                    incident['status'] = 'resolved'
                else:
                    await thread.send(
                        embed=discord.Embed(
                            title="⚠️ Remediation Issue",
                            description=f"```\n{remediation.get('error', 'Unknown error')}\n```",
                            color=discord.Color.orange()
                        )
                    )
                    incident['status'] = 'needs_review'
            else:
                await thread.send(
                    embed=discord.Embed(
                        title="📝 Manual Action Required",
                        description="Auto-remediation is disabled. Review the analysis above and take appropriate action.\n\n"
                                   "Use `/remediate` to execute suggested fixes with approval.",
                        color=discord.Color.orange()
                    )
                )
                incident['status'] = 'needs_action'
            
            # Update total cost
            self.total_cost_usd += incident['cost_usd']
            
            # Final summary
            await thread.send(
                embed=discord.Embed(
                    title=f"📊 Incident Summary: {incident_id}",
                    color=discord.Color.green() if incident['status'] == 'resolved' else discord.Color.orange(),
                    timestamp=datetime.now(timezone.utc)
                ).add_field(
                    name="Status",
                    value=incident['status'].upper().replace('_', ' '),
                    inline=True
                ).add_field(
                    name="Duration",
                    value=str(datetime.now(timezone.utc) - incident['started_at']).split('.')[0],
                    inline=True
                ).add_field(
                    name="API Cost",
                    value=f"${incident['cost_usd']:.4f}",
                    inline=True
                ).set_footer(text=f"Total session cost: ${self.total_cost_usd:.4f}")
            )
            
        except Exception as e:
            logger.exception(f"Error investigating incident {incident_id}")
            await thread.send(
                embed=discord.Embed(
                    title="❌ Investigation Error",
                    description=f"An error occurred during investigation:\n```\n{str(e)}\n```",
                    color=discord.Color.red()
                )
            )
            incident['status'] = 'error'
    
    async def close(self):
        """Cleanup on shutdown."""
        await super().close()


# Slash Commands
@app_commands.command(name="investigate", description="Start Oracle investigation on an alert")
@app_commands.describe(incident_id="The incident ID to investigate (optional)")
async def investigate_command(interaction: discord.Interaction, incident_id: Optional[str] = None):
    """Manually trigger investigation."""
    await interaction.response.defer()
    
    bot: OracleAgent = interaction.client
    
    if incident_id and incident_id in bot.active_incidents:
        asyncio.create_task(bot._investigate_incident(incident_id))
        await interaction.followup.send(f"🔍 Started investigation for incident `{incident_id}`")
    else:
        await interaction.followup.send(
            "Please reply to an alert message or provide a valid incident ID.",
            ephemeral=True
        )


@app_commands.command(name="ask-oracle", description="Ask Oracle a question about the homelab")
@app_commands.describe(question="Your question about the homelab infrastructure")
async def ask_oracle_command(interaction: discord.Interaction, question: str):
    """Ask Oracle a question about the homelab."""
    await interaction.response.defer()
    
    bot: OracleAgent = interaction.client
    
    result = await bot.claude_executor.execute(
        f"""Answer the following question about this homelab infrastructure.

**Question:** {question}

## Instructions
1. First, check if this question requires knowing the CURRENT state of a service (up/down, running, etc.)
2. If yes, run appropriate diagnostic commands FIRST (docker ps, curl health endpoints, etc.)
3. Search the codebase for relevant configuration and documentation
4. Cross-reference the Infrastructure Map in your system prompt for correct hosts/ports
5. Provide a clear, accurate answer with specific details

**Important:** Never assume service status - always verify with live commands if asked about current state.""",
        disallowed_tools=bot.claude_executor._get_disallowed_tools(),
        timeout=180
    )
    
    bot.total_cost_usd += result.get('cost', 0)
    
    if result['success']:
        output = result['output']
        if len(output) > 1900:
            output = output[:1900] + "\n\n... (truncated)"
        
        # Plain text response for better readability
        response = f"**🔮 Oracle's Response**\n\n{output}\n\n_Cost: ${result.get('cost', 0):.4f}_"
        await interaction.followup.send(response)
    else:
        await interaction.followup.send(
            f"❌ Error: {result.get('error', 'Unknown error')}",
            ephemeral=True
        )


@app_commands.command(name="oracle-status", description="Show Oracle AI Agent status")
async def oracle_status_command(interaction: discord.Interaction):
    """Show Oracle status."""
    bot: OracleAgent = interaction.client
    
    uptime = datetime.now(timezone.utc) - bot.start_time
    
    embed = discord.Embed(
        title="🔮 Oracle AI Agent Status",
        color=discord.Color.purple() if bot.is_ready() else discord.Color.red(),
        timestamp=datetime.now(timezone.utc)
    )
    
    embed.add_field(name="Status", value="🟢 Online" if bot.is_ready() else "🔴 Offline", inline=True)
    embed.add_field(name="Uptime", value=str(uptime).split('.')[0], inline=True)
    embed.add_field(name="Environment", value=bot.config.environment.upper(), inline=True)
    embed.add_field(name="Engine", value="Claude Code CLI", inline=True)
    embed.add_field(name="Edit Tools", value="✅ Enabled" if bot.config.allow_edit_tools else "❌ Disabled (prod)", inline=True)
    embed.add_field(name="Auto-Respond", value="✅ Enabled" if bot.auto_respond else "❌ Disabled", inline=True)
    embed.add_field(name="Auto-Remediate", value="✅ Enabled" if bot.config.auto_remediate else "❌ Disabled", inline=True)
    embed.add_field(name="Active Incidents", value=str(len(bot.active_incidents)), inline=True)
    embed.add_field(name="Total API Cost", value=f"${bot.total_cost_usd:.4f}", inline=True)
    embed.add_field(name="Codebase Path", value=f"`{bot.config.codebase_path}`", inline=False)
    
    if bot.agent_channel:
        embed.add_field(name="Agent Channel", value=f"<#{bot.agent_channel.id}>", inline=True)
    
    await interaction.response.send_message(embed=embed)


@app_commands.command(name="toggle-auto", description="Toggle auto-respond or auto-remediate")
@app_commands.describe(feature="Feature to toggle")
@app_commands.choices(feature=[
    app_commands.Choice(name="Auto-Respond", value="respond"),
    app_commands.Choice(name="Auto-Remediate", value="remediate"),
])
@app_commands.checks.has_permissions(administrator=True)
async def toggle_auto_command(interaction: discord.Interaction, feature: str):
    """Toggle auto features."""
    bot: OracleAgent = interaction.client
    
    if feature == "respond":
        bot.auto_respond = not bot.auto_respond
        status = "enabled" if bot.auto_respond else "disabled"
        await interaction.response.send_message(f"✅ Auto-respond is now **{status}**")
    elif feature == "remediate":
        bot.config.auto_remediate = not bot.config.auto_remediate
        status = "enabled" if bot.config.auto_remediate else "disabled"
        await interaction.response.send_message(f"✅ Auto-remediate is now **{status}**")


@app_commands.command(name="run-task", description="Run a custom task with Oracle")
@app_commands.describe(task="The task for Oracle to perform")
@app_commands.checks.has_permissions(administrator=True)
async def run_task_command(interaction: discord.Interaction, task: str):
    """Run a custom task with Oracle."""
    await interaction.response.defer()
    
    bot: OracleAgent = interaction.client
    
    # Show edit tools status in the task
    edit_note = ""
    if bot.config.allow_edit_tools:
        edit_note = " (Edit tools ENABLED - dev environment)"
    else:
        edit_note = " (Edit tools DISABLED - non-dev environment)"
    
    # Admin-only command - skip permissions since they have Discord admin rights
    result = await bot.claude_executor.execute(
        task,
        disallowed_tools=bot.claude_executor._get_disallowed_tools(),
        timeout=600,  # 10 minutes for complex tasks with SSH
        skip_permissions=True  # Admin already authorized via Discord permissions
    )
    bot.total_cost_usd += result.get('cost', 0)
    
    if result['success']:
        output = result['output']
        
        # Split into multiple messages if needed
        if len(output) > 1900:
            chunks = [output[i:i+1900] for i in range(0, len(output), 1900)]
            for i, chunk in enumerate(chunks[:3]):  # Limit to 3 chunks
                header = f"**🔮 Oracle Task Result ({i+1}/{min(len(chunks), 3)})**{edit_note}\n\n" if i == 0 else ""
                await interaction.followup.send(f"{header}{chunk}")
            if len(chunks) > 3:
                await interaction.followup.send(f"... and {len(chunks) - 3} more chunks (truncated)")
            await interaction.followup.send(f"_Cost: ${result.get('cost', 0):.4f}_")
        else:
            response = f"**🔮 Oracle Task Result**{edit_note}\n\n{output}\n\n_Cost: ${result.get('cost', 0):.4f}_"
            await interaction.followup.send(response)
    else:
        await interaction.followup.send(
            f"❌ Error: {result.get('error', 'Unknown error')}",
            ephemeral=True
        )


@app_commands.command(name="incidents", description="List active incidents")
async def incidents_command(interaction: discord.Interaction):
    """List active incidents."""
    bot: OracleAgent = interaction.client
    
    if not bot.active_incidents:
        await interaction.response.send_message("No active incidents.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📋 Active Incidents",
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    )
    
    for inc_id, incident in list(bot.active_incidents.items())[-10:]:  # Last 10
        duration = datetime.now(timezone.utc) - incident['started_at']
        embed.add_field(
            name=f"{inc_id}",
            value=f"**Status:** {incident['status']}\n"
                  f"**Alert:** {incident['alert'].get('title', 'Unknown')[:50]}\n"
                  f"**Duration:** {str(duration).split('.')[0]}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)


@app_commands.command(name="remediate", description="Execute a remediation with approval")
@app_commands.describe(
    action="Describe what you want Oracle to fix or remediate",
    skip_approval="Skip the approval step (admin only)"
)
@app_commands.checks.has_permissions(administrator=True)
async def remediate_command(
    interaction: discord.Interaction, 
    action: str,
    skip_approval: bool = False
):
    """Execute a remediation action with Discord approval."""
    await interaction.response.defer()
    
    bot: OracleAgent = interaction.client
    
    # Phase 1: Ask Oracle to analyze and propose a solution
    analysis_prompt = f"""Analyze this remediation request and propose a solution:

**Request:** {action}

## IMPORTANT - How to access hosts:
- You are running on argus-dev (192.168.20.50)
- Harbor is on hephaestus-dev - use: `ssh hephaestus-dev "command"`
- Other hosts: orion-dev, hermes-dev - same SSH pattern
- DO NOT run local commands expecting to find Harbor - it's on hephaestus-dev!

## Instructions:
1. SSH to the correct host and check current state
2. Propose a SPECIFIC fix with exact SSH commands
3. Keep it brief - just state what you found and what to do

Example for Harbor:
```bash
ssh hephaestus-dev "cd /opt/harbor && docker compose ps"
```"""

    await interaction.followup.send(
        f"**🔍 Oracle Analyzing...**\n\nAnalyzing remediation request:\n> {action[:200]}"
    )
    
    # Run analysis - need skip_permissions to allow SSH commands
    analysis_result = await bot.claude_executor.execute(
        analysis_prompt,
        disallowed_tools=["Write", "Edit", "MultiEdit"],  # Read-only for analysis
        max_budget_usd=0.05,  # Limit analysis cost
        timeout=120,
        skip_permissions=True  # Allow Bash/SSH during analysis
    )
    bot.total_cost_usd += analysis_result.get('cost', 0)
    
    if not analysis_result['success']:
        await interaction.followup.send(
            f"❌ Analysis failed: {analysis_result.get('error', 'Unknown error')}"
        )
        return
    
    analysis_output = analysis_result['output']
    
    # Phase 2: Request approval (unless skipped)
    if skip_approval:
        approved = True
        approver = interaction.user
    else:
        # Create approval embed
        approval_embed = discord.Embed(
            title="⚠️ Remediation Approval Required",
            description=f"**Requested Action:**\n{action}\n\n**Oracle's Analysis:**\n{analysis_output[:2000]}",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        approval_embed.set_footer(text="Click Approve to execute, Deny to cancel")
        
        # Create approval view
        view = ApprovalView(
            action_description=action,
            command_to_run=analysis_output[:1900],
            timeout=300  # 5 minute timeout
        )
        
        approval_msg = await interaction.followup.send(
            embed=approval_embed,
            view=view
        )
        
        # Wait for approval
        await view.wait()
        
        if view.approved is None:
            await interaction.followup.send("⏰ Approval timed out. Remediation cancelled.")
            return
        
        approved = view.approved
        approver = view.responder
    
    if not approved:
        return  # User denied
    
    # Phase 3: Execute the remediation
    execute_prompt = f"""Execute this remediation NOW:

**Request:** {action}

## SSH Access:
- Harbor is on hephaestus-dev: `ssh hephaestus-dev "cd /opt/harbor && docker compose up -d"`
- Use SSH for all remote hosts, don't search for local files

Execute the fix and report the result briefly."""

    execution_msg = f"**🔧 Executing Remediation...**\n\nApproved by {approver.mention}\nExecuting fix with full permissions..."
    await interaction.followup.send(execution_msg)
    
    # Execute with full permissions - skip_permissions=True since Discord approval was given
    exec_result = await bot.claude_executor.execute(
        execute_prompt,
        disallowed_tools=bot.claude_executor._get_disallowed_tools(),
        max_budget_usd=0.10,  # Limit budget to $0.10 per remediation
        timeout=300,  # 5 minutes should be enough
        skip_permissions=True  # User approved via Discord buttons
    )
    bot.total_cost_usd += exec_result.get('cost', 0)
    
    if exec_result['success']:
        result_output = exec_result['output'][:1800]
        total_cost = analysis_result.get('cost', 0) + exec_result.get('cost', 0)
        result_msg = f"**✅ Remediation Complete**\n\n{result_output}\n\n**Approved By:** {approver.mention}\n**Total Cost:** ${total_cost:.4f}"
    else:
        result_msg = f"**❌ Remediation Failed**\n\nError: {exec_result.get('error', 'Unknown')}"
    
    await interaction.followup.send(result_msg)


@app_commands.command(name="new-session", description="Start a fresh Claude session (clears conversation history)")
async def new_session_command(interaction: discord.Interaction):
    """Reset the Claude session for this channel."""
    bot: OracleAgent = interaction.client
    
    old_session = bot.session_manager.get_session_info(interaction.channel_id)
    new_session_id = bot.session_manager.reset_session(interaction.channel_id)
    
    if old_session:
        msg = f"**🔄 Session Reset**\n\nPrevious session: `...{old_session.session_id[-8:]}` ({old_session.message_count} messages, ${old_session.total_cost:.4f})\nNew session: `...{new_session_id[-8:]}`\n\nConversation history cleared. Oracle will start fresh."
    else:
        msg = f"**🔄 New Session Started**\n\nSession ID: `...{new_session_id[-8:]}`"
    
    await interaction.response.send_message(msg)


@app_commands.command(name="session-info", description="Show current Claude session info for this channel")
async def session_info_command(interaction: discord.Interaction):
    """Show session information for the current channel."""
    bot: OracleAgent = interaction.client
    
    session = bot.session_manager.get_session_info(interaction.channel_id)
    
    if session:
        age = datetime.now(timezone.utc) - session.created_at
        idle = datetime.now(timezone.utc) - session.last_used
        
        msg = f"""**📊 Session Info**

**Session ID:** `...{session.session_id[-8:]}`
**Channel:** <#{session.channel_id}>
**Messages:** {session.message_count}
**Total Cost:** ${session.total_cost:.4f}
**Age:** {str(age).split('.')[0]}
**Idle:** {str(idle).split('.')[0]}
**Timeout:** 30 minutes

_Sessions automatically expire after 30 minutes of inactivity._"""
    else:
        msg = "**📊 Session Info**\n\nNo active session for this channel. Send a message to Oracle to start one."
    
    await interaction.response.send_message(msg)


async def main():
    """Main entry point."""
    config = Config.from_env()
    bot = OracleAgent(config)
    
    # Add commands
    bot.tree.add_command(investigate_command)
    bot.tree.add_command(ask_oracle_command)
    bot.tree.add_command(oracle_status_command)
    bot.tree.add_command(toggle_auto_command)
    bot.tree.add_command(run_task_command)
    bot.tree.add_command(incidents_command)
    bot.tree.add_command(remediate_command)
    bot.tree.add_command(new_session_command)
    bot.tree.add_command(session_info_command)
    
    try:
        await bot.start(config.discord_token)
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
