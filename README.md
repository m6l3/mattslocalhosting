# Ultimate LocalHost

A desktop application for hosting and joining  Studio team test sessions over the internet using Playit.gg tunnels. Built with Python and Tkinter.

---

## Requirements

- Windows 10 or later
- Studio installed (the app locates it automatically)
- A [Playit.gg](https://playit.gg) account and tunnel (required for remote play, not needed for local testing)

Install Python dependencies (standard library only — no pip install required).

---

## Installation

1. Go to Releases and install last release .exe file
2. Run it


On first launch, a loading screen will appear while the app searches for your Studio installation via PowerShell. This takes a few seconds. If Studio is not found, you will see a warning — verify that Roblox Studio is installed before proceeding.

---

## How to Use

### Hosting a Server

This section is for the person who wants to create and share a game session.

1. On the welcome screen, click **Create Server**.
2. Fill in the following fields:
   - **User ID** — your numeric user ID. You can find it in your profile URL (`.com/users/XXXXXXXXXX/profile`).
   - **Playit.gg Address** — the tunnel address provided by Playit.gg in the format `hostname:port` (e.g. `higher-disposition.gl.at.ply.gg:2142`). Leave this blank if you only intend to test locally.
   - **TeamTest Server Port** — the port Studio will listen on. Default is `55555`. Change this only if the port is already in use on your machine.
3. Click **Create**. The server console will open and Studio will launch automatically as a TeamTest server.
4. Wait approximately 5 seconds for Studio to initialize. Once the status reads **SERVER IS LIVE**, the server is ready.
5. To join the server yourself from the same machine, click **Join This Server (local)**. This launches a Studio client connected directly to your local server.

Share your Playit.gg tunnel address (the `hostname:port` string) with anyone who wants to join remotely.

---

### Joining a Server

This section is for players connecting to someone else's hosted session.

1. On the welcome screen, click **Join Server**.
2. Enter the Playit.gg tunnel address provided by the host, in the format `hostname:port`.
3. Click **Join**. The connection console will open and the application will establish a connection to the remote server.
4. Studio will launch automatically as a client. Wait for it to connect — you will see incoming packets logged in the console once the session is active.
5. To disconnect, click **Disconnect & Back**. This cleanly shuts down the connection and returns you to the main menu.

---

## Credits

Author: s0m3thing_matters  
Discord Server: https://discord.gg/H3K2xeU96A

---
btw README was made by ai, yes
if you are afraid that this file is a virus, check it with virustotal and other services. You can unpack it, the file was packed using pyinstaller, there is no obfuscation.
