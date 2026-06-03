import discord
from discord import app_commands
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')

class DeployClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
    
    async def on_ready(self):
        await self.tree.sync()
        print(f"✅ Commands deployed! Logged in as {self.user}")
        await self.close()

async def main():
    client = DeployClient()
    
    @client.tree.command(name="hidelua", description="Upload a Roblox Lua script to LuaBin and get loadstring")
    @app_commands.describe(code="The Lua script to upload")
    async def hidelua(interaction: discord.Interaction, code: str):
        pass
    
    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
