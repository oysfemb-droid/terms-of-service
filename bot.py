import os
import sqlite3
import random
import discord
from discord.ext import commands

# Set DISCORD_TOKEN in your environment before running.
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"
DB_PATH = "infections.sqlite3"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=[PREFIX, "?"], intents=intents, help_command=None)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS infections (
            guild_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            infection_type TEXT NOT NULL CHECK(infection_type IN ('shit', 'super_shit')),
            infected_by INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, target_id, infection_type)
        )
    """)
    return conn


def add_infection(guild_id: int, target_id: int, infection_type: str, infected_by: int):
    with db() as conn:
        conn.execute("""
            INSERT INTO infections (guild_id, target_id, infection_type, infected_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, target_id, infection_type)
            DO UPDATE SET infected_by=excluded.infected_by, created_at=CURRENT_TIMESTAMP
        """, (guild_id, target_id, infection_type, infected_by))


def remove_infection(guild_id: int, target_id: int, infection_type: str) -> bool:
    with db() as conn:
        cur = conn.execute(
            "DELETE FROM infections WHERE guild_id=? AND target_id=? AND infection_type=?",
            (guild_id, target_id, infection_type)
        )
        return cur.rowcount > 0


def remove_all_infections(guild_id: int, target_id: int) -> set[str]:
    with db() as conn:
        rows = conn.execute(
            "SELECT infection_type FROM infections WHERE guild_id=? AND target_id=?",
            (guild_id, target_id)
        ).fetchall()
        conn.execute(
            "DELETE FROM infections WHERE guild_id=? AND target_id=?",
            (guild_id, target_id)
        )
    return {row[0] for row in rows}


async def remove_infection_roles(member: discord.Member) -> list[discord.Role]:
    """Remove infection roles whose names match common spellings."""
    role_names = {"shit", "super shit", "super_shit", "super-shit"}
    roles_to_remove = [role for role in member.roles if role.name.lower() in role_names]
    if not roles_to_remove:
        return []
    try:
        await member.remove_roles(*roles_to_remove, reason="Successful /pray infection cleanse")
        return roles_to_remove
    except (discord.Forbidden, discord.HTTPException):
        # Database infection records are still cleared even if role permissions prevent removal.
        return []


def get_types(guild_id: int, target_id: int):
    with db() as conn:
        rows = conn.execute(
            "SELECT infection_type FROM infections WHERE guild_id=? AND target_id=?",
            (guild_id, target_id)
        ).fetchall()
    return {row[0] for row in rows}


def count_people_infected_by(guild_id: int, user_id: int) -> int:
    # Counts distinct people currently carrying an infection attributed to this user.
    with db() as conn:
        row = conn.execute("""
            SELECT COUNT(DISTINCT target_id)
            FROM infections
            WHERE guild_id=? AND infected_by=? AND target_id != ?
        """, (guild_id, user_id, user_id)).fetchone()
    return row[0]


def is_admin(ctx: commands.Context) -> bool:
    return bool(ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild)


async def get_targets(message: discord.Message):
    """Return mentioned users plus the author of a replied-to message, if resolvable."""
    targets = {u.id: u for u in message.mentions if not u.bot}
    if message.reference:
        resolved = message.reference.resolved
        if isinstance(resolved, discord.Message) and not resolved.author.bot:
            targets[resolved.author.id] = resolved.author
        elif message.reference.message_id and message.guild:
            try:
                referenced = await message.channel.fetch_message(message.reference.message_id)
                if not referenced.author.bot:
                    targets[referenced.author.id] = referenced.author
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
    return list(targets.values())


@bot.event
async def on_ready():
    db().close()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except discord.HTTPException as exc:
        print(f"Could not sync slash commands: {exc}")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    # Don't auto-infect from bot commands. Ordinary @mentions and replies
    # automatically add a "shit" infection, credited to the message author.
    is_command = message.content.startswith((PREFIX, "?"))
    if not is_command:
        targets = await get_targets(message)
        for target in targets:
            if target.id != message.author.id:
                add_infection(message.guild.id, target.id, "shit", message.author.id)

    await bot.process_commands(message)


@bot.command(name="infect")
async def infect(ctx: commands.Context, target: discord.Member = None, infection_type: str = None):
    """Admin: !infect @user shit|super_shit"""
    if not is_admin(ctx):
        await ctx.reply("Only server admins (or members with Manage Server) can use this command.")
        return
    if target is None or infection_type is None:
        await ctx.reply("Usage: `!infect @user shit` or `!infect @user super_shit`")
        return
    infection_type = infection_type.lower().replace("-", "_")
    if infection_type not in {"shit", "super_shit"}:
        await ctx.reply("Type must be `shit` or `super_shit`.")
        return
    if target.bot:
        await ctx.reply("Bots can't be infected.")
        return
    add_infection(ctx.guild.id, target.id, infection_type, ctx.author.id)
    await ctx.reply(f"💩 {target.mention} now has **{infection_type}**!")


@bot.command(name="cure", aliases=["uninfect"])
async def cure(ctx: commands.Context, target: discord.Member = None, infection_type: str = None):
    """Admin: !cure @user shit|super_shit"""
    if not is_admin(ctx):
        await ctx.reply("Only server admins (or members with Manage Server) can use this command.")
        return
    if target is None or infection_type is None:
        await ctx.reply("Usage: `!cure @user shit` or `!cure @user super_shit`")
        return
    infection_type = infection_type.lower().replace("-", "_")
    if infection_type not in {"shit", "super_shit"}:
        await ctx.reply("Type must be `shit` or `super_shit`.")
        return
    if remove_infection(ctx.guild.id, target.id, infection_type):
        await ctx.reply(f"🧼 Removed **{infection_type}** from {target.mention}.")
    else:
        await ctx.reply(f"{target.mention} didn't have **{infection_type}**.")


@bot.command(name="infections", aliases=["status", "check"])
async def infections(ctx: commands.Context, target: discord.Member = None):
    target = target or ctx.author
    types = get_types(ctx.guild.id, target.id)
    shit = "Yes 💩" if "shit" in types else "No"
    super_shit = "YES 💀" if "super_shit" in types else "No"
    await ctx.reply(
        f"**Infection status for {target.display_name}**\n"
        f"• shit: {shit}\n• super shit: {super_shit}"
    )


@bot.command(name="infected", aliases=["myinfected", "count"])
async def infected(ctx: commands.Context, target: discord.Member = None):
    target = target or ctx.author
    count = count_people_infected_by(ctx.guild.id, target.id)
    await ctx.reply(f"🦠 {target.mention} has infected **{count} unique people** (currently attributed to them).")


@bot.command(name="pray")
async def pray(ctx: commands.Context):
    """Try your luck and get all infection types removed."""
    # 5% chance to be cleansed each time.
    chance = 0.05
    if random.random() >= chance:
        await ctx.reply("🙏 You prayed... but the infection remains. Try again later!")
        return

    removed = remove_all_infections(ctx.guild.id, ctx.author.id)
    removed_roles = await remove_infection_roles(ctx.author)
    if not removed and not removed_roles:
        await ctx.reply("🙏 Your prayer was heard, but you weren't infected in the first place.")
        return

    await ctx.reply("✨🙏 A MIRACLE! Your **shit** and **super shit** infections have been cleansed!")


@bot.tree.command(name="pray", description="Pray for a small chance to remove all your infections.")
async def slash_pray(interaction: discord.Interaction):
    if interaction.guild_id is None or interaction.user.bot:
        await interaction.response.send_message("This command only works in a server.")
        return

    if random.random() >= 0.05:
        await interaction.response.send_message("🙏 You prayed... but the infection remains. Try again later!")
        return

    removed = remove_all_infections(interaction.guild_id, interaction.user.id)
    removed_roles = []
    if isinstance(interaction.user, discord.Member):
        removed_roles = await remove_infection_roles(interaction.user)
    if not removed and not removed_roles:
        await interaction.response.send_message("🙏 Your prayer was heard, but you weren't infected in the first place.")
        return

    await interaction.response.send_message(
        "✨🙏 A MIRACLE! Your **shit** and **super shit** infections have been cleansed!"
    )


@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard(ctx: commands.Context):
    with db() as conn:
        rows = conn.execute("""
            SELECT infected_by, COUNT(DISTINCT target_id) AS people
            FROM infections
            WHERE guild_id=? AND target_id != infected_by
            GROUP BY infected_by
            ORDER BY people DESC, infected_by ASC
            LIMIT 10
        """, (ctx.guild.id,)).fetchall()
    if not rows:
        await ctx.reply("No infections recorded yet.")
        return
    lines = []
    for rank, (user_id, count) in enumerate(rows, start=1):
        member = ctx.guild.get_member(user_id)
        name = member.display_name if member else f"User {user_id}"
        lines.append(f"**{rank}.** {name} — {count} people")
    await ctx.reply("**💩 Infection leaderboard**\n" + "\n".join(lines))


@bot.command(name="infectionhelp", aliases=["commands"])
async def infectionhelp(ctx: commands.Context):
    await ctx.reply(
        "**Infection Bot Commands**\n"
        "`!infect @user shit` — admin adds shit\n"
        "`!infect @user super_shit` — admin adds super shit\n"
        "`!cure @user shit` — admin removes shit\n"
        "`!cure @user super_shit` — admin removes super shit\n"
        "`!infections [@user]` — check infection status\n"
        "`!infected [@user]` — count unique people they've infected\n"
        "`!leaderboard` — top infection counts\n\n"
        "Ordinary @mentions and replies automatically add **shit** (not super shit)."
    )


if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable. See README.md.")
bot.run(TOKEN)
