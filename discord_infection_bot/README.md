# Discord Infection Bot

A playful Discord bot that tracks two infection types: `shit` and `super_shit`.
A member can have both at once. Data is saved in a local SQLite database.

## Requirements
- Python 3.10+
- A Discord application/bot from https://discord.com/developers/applications

## Setup
1. In the Discord Developer Portal, create an application, add a Bot, and copy its token.
2. Under **Bot → Privileged Gateway Intents**, enable **Message Content Intent** and **Server Members Intent**.
3. Invite the bot to your server with permissions to view channels and send messages. It does not need Administrator permissions.
4. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
5. Set the token as an environment variable (do not paste it into public code or share it):
   - Windows PowerShell:
     ```powershell
     $env:DISCORD_TOKEN="YOUR_BOT_TOKEN"
     python bot.py
     ```
   - macOS/Linux:
     ```bash
     export DISCORD_TOKEN="YOUR_BOT_TOKEN"
     python bot.py
     ```

## Commands
- `!infect @user shit` — admin or Manage Server adds `shit`
- `!infect @user super_shit` — admin or Manage Server adds `super_shit`
- `!cure @user shit` — admin or Manage Server removes `shit`
- `!cure @user super_shit` — admin or Manage Server removes `super_shit`
- `!infections [@user]` — view current infection status
- `!infected [@user]` — number of unique people currently infected by that user
- `!leaderboard` — top 10 infection counts
- `!infectionhelp` — show help

## Automatic infection rules
Any ordinary message that mentions a member or replies to one automatically adds `shit`, credited to the message author. This includes Discord reply references where the replied-to author is not explicitly mentioned in the text. Bot commands are excluded from automatic infection so `!infect @user super_shit` doesn't also trigger an accidental `shit` infection. Automatic infections never add `super_shit`.

## Counting details
- Each member can have one record for each infection type; duplicate infections of the same type do not stack.
- `!infected` counts distinct people who currently have at least one infection attributed to that user.
- If an admin infects someone with a type they already have, attribution for that type moves to that admin.
- Removing an infection removes only the selected type.

## Notes
The `pray` command has a 5% chance per use to remove both `shit` and `super_shit` from the person praying. It clears the bot's infection records and attempts to remove Discord roles named `shit`, `super shit`, `super_shit`, or `super-shit`. The bot needs Manage Roles permission, and its role must be higher than the infection roles in Server Settings → Roles. The bot must be online to notice messages and replies. SQLite data is stored in `infections.sqlite3` in the folder where you run the bot.
