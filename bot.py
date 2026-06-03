import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
import os
import threading
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
API_URL = 'https://lua-hider.onrender.com/api/v1/upload'
API_KEY = 'sttaralbiola'
DELETE_URL = 'https://lua-hider.onrender.com/api/v1/script'
PORT = int(os.getenv('PORT', 8080))

# Cache for script data
script_cache = {}

# Flask app
flask_app = Flask(__name__)

# HTML template for web status page
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>LuaBin Discord Bot Status</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 50px;
            margin: 0;
        }
        .container {
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 30px;
            max-width: 600px;
            margin: 0 auto;
            backdrop-filter: blur(10px);
        }
        h1 { margin-bottom: 10px; }
        .status {
            font-size: 24px;
            margin: 20px 0;
        }
        .online {
            color: #57f287;
        }
        .stats {
            text-align: left;
            margin: 20px 0;
            padding: 20px;
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
        }
        .stat-item {
            margin: 10px 0;
            font-size: 16px;
        }
        .command {
            background: #1e1e2f;
            padding: 10px;
            border-radius: 8px;
            font-family: monospace;
            margin: 10px 0;
        }
        button {
            background: #57f287;
            color: #1e1e2f;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            margin-top: 20px;
        }
        button:hover {
            background: #45c97a;
        }
        footer {
            margin-top: 30px;
            font-size: 12px;
            opacity: 0.8;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 LuaBin Discord Bot</h1>
        <div class="status">
            Status: <span class="online">🟢 ONLINE</span>
        </div>
        <div class="stats">
            <div class="stat-item">📊 <strong>Bot Name:</strong> {{ bot_name }}</div>
            <div class="stat-item">🆔 <strong>Bot ID:</strong> {{ bot_id }}</div>
            <div class="stat-item">👥 <strong>Servers:</strong> {{ guild_count }}</div>
            <div class="stat-item">💾 <strong>Cached Scripts:</strong> {{ cache_count }}</div>
            <div class="stat-item">⏰ <strong>Uptime:</strong> {{ uptime }}</div>
        </div>
        <div class="command">
            /hidelua [code] - Upload Lua script to LuaBin
        </div>
        <button onclick="window.location.reload()">🔄 Refresh Status</button>
        <footer>
            Powered by Flask & Discord.py
        </footer>
    </div>
</body>
</html>
'''

# Flask routes
@flask_app.route('/')
def home():
    """Web status page"""
    uptime_seconds = int(bot_uptime) if 'bot_uptime' in globals() else 0
    uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
    
    return render_template_string(
        HTML_TEMPLATE,
        bot_name=bot.user.name if bot.user else "Offline",
        bot_id=bot.user.id if bot.user else "N/A",
        guild_count=len(bot.guilds) if bot.guilds else 0,
        cache_count=len(script_cache),
        uptime=uptime_str
    )

@flask_app.route('/health')
def health():
    """Health check endpoint for uptime monitoring"""
    return jsonify({
        'status': 'online',
        'bot_ready': bot.is_ready(),
        'guilds': len(bot.guilds) if bot.guilds else 0,
        'cached_scripts': len(script_cache)
    })

@flask_app.route('/stats')
def stats():
    """Detailed statistics endpoint"""
    return jsonify({
        'bot_name': bot.user.name if bot.user else None,
        'bot_id': bot.user.id if bot.user else None,
        'guild_count': len(bot.guilds) if bot.guilds else 0,
        'cached_scripts': len(script_cache),
        'api_url': API_URL
    })

def run_flask():
    """Run Flask server in a separate thread"""
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

# Discord Bot
class DeleteButton(discord.ui.Button):
    def __init__(self, script_id: str, message_id: int):
        super().__init__(label="🗑️ Delete Script", style=discord.ButtonStyle.danger)
        self.script_id = script_id
        self.message_id = message_id
    
    async def callback(self, interaction: discord.Interaction):
        async with aiohttp.ClientSession() as session:
            url = f"{DELETE_URL}/{self.script_id}?api_key={API_KEY}"
            async with session.delete(url) as resp:
                result = await resp.json()
                
                if result.get('success'):
                    await interaction.response.send_message("✅ Script deleted successfully!", ephemeral=True)
                    
                    if self.message_id in script_cache:
                        del script_cache[self.message_id]
                    
                    new_embed = discord.Embed(
                        title="🗑️ Script Deleted",
                        description="This script has been deleted from LuaBin.",
                        color=discord.Color.red()
                    )
                    await interaction.message.edit(embed=new_embed, view=None)
                else:
                    await interaction.response.send_message(f"❌ Failed to delete: {result.get('error', 'Unknown error')}", ephemeral=True)

class CopyButton(discord.ui.Button):
    def __init__(self, loadstring: str):
        super().__init__(label="📋 Copy Loadstring", style=discord.ButtonStyle.primary)
        self.loadstring = loadstring
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"```lua\n{self.loadstring}\n```", ephemeral=True)

class ScriptView(discord.ui.View):
    def __init__(self, script_id: str, loadstring: str, message_id: int):
        super().__init__(timeout=300)
        self.add_item(CopyButton(loadstring))
        self.add_item(DeleteButton(script_id, message_id))

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Bot commands synced!")

bot = Bot()
start_time = None

@bot.tree.command(name="hidelua", description="Upload a Roblox Lua script to LuaBin and get loadstring")
@app_commands.describe(code="The Lua script to upload")
async def hidelua(interaction: discord.Interaction, code: str):
    truncated = code[:800] + "..." if len(code) > 800 else code
    loading_embed = discord.Embed(
        title="📤 Uploading Script to LuaBin...",
        description=f"```lua\n{truncated}\n```",
        color=discord.Color.gold()
    )
    loading_embed.add_field(name="⏳ Status", value="Sending to server...", inline=True)
    loading_embed.set_footer(text="LuaBin Script Hosting")
    
    await interaction.response.send_message(embed=loading_embed)
    message = await interaction.original_response()
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"api_key": API_KEY, "code": code}
            async with session.post(API_URL, json=payload) as resp:
                data = await resp.json()
                
                if data.get('success'):
                    success_embed = discord.Embed(
                        title="✅ Script Uploaded Successfully!",
                        color=discord.Color.green()
                    )
                    success_embed.add_field(name="🆔 Script ID", value=f"`{data['id']}`", inline=True)
                    success_embed.add_field(name="📏 Code Length", value=f"{len(code)} characters", inline=True)
                    success_embed.add_field(name="🔧 Loadstring Command", value=f"```lua\n{data['loadstring']}\n```", inline=False)
                    success_embed.add_field(name="🔗 Direct URL", value=data['url'], inline=False)
                    success_embed.set_footer(text="Click the buttons below to copy or delete")
                    success_embed.timestamp = discord.utils.utcnow()
                    
                    script_cache[message.id] = {
                        'id': data['id'],
                        'loadstring': data['loadstring']
                    }
                    
                    view = ScriptView(data['id'], data['loadstring'], message.id)
                    await message.edit(embed=success_embed, view=view)
                else:
                    error_embed = discord.Embed(
                        title="❌ Upload Failed",
                        description=f"**Error:** {data.get('error', 'Unknown error')}",
                        color=discord.Color.red()
                    )
                    await message.edit(embed=error_embed)
                    
    except Exception as e:
        print(f"Error: {e}")
        error_embed = discord.Embed(
            title="❌ Upload Failed",
            description="Failed to connect to LuaBin API. Please try again later.",
            color=discord.Color.red()
        )
        await message.edit(embed=error_embed)

@bot.event
async def on_ready():
    global start_time, bot_uptime
    start_time = asyncio.get_event_loop().time()
    bot_uptime = start_time
    print(f"✅ Bot is online! Logged in as {bot.user}")
    print(f"📍 Invite URL: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=2147567616&scope=bot%20applications.commands")
    print(f"🌐 Flask server running on port {PORT}")
    print(f"📊 Status page: http://localhost:{PORT}")

# Run both bot and Flask
def run_bot():
    """Run the Discord bot"""
    bot.run(TOKEN)

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Run Discord bot (this blocks)
    run_bot()
