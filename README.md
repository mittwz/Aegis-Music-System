# Aegis Music System

**Adaptive music direction for Dota 2 and Spotify.**

Aegis Music System listens to Dota 2 Game State Integration (GSI), infers the current match mood, and adjusts Spotify playlists and volume in real time.

## What it does

- Starts a menu playlist as soon as the script boots.
- Detects pre-game phases such as hero selection, strategy time, team showcase, and pre-game.
- Reacts to match phases such as early game, lane control, teamfights, low HP, death, late game, victory, and defeat.
- Supports a **cinema mode** that smooths transitions and avoids frantic state switching.
- Applies a single **global master gain** so you can make the whole system louder or quieter with one setting.
- Keeps logs readable and color-coded.

## Quick start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create your `.env` file from `.env.example`.

3. Copy the Dota GSI file from:

```text
dota_gsi/gamestate_integration_aegis_music_system.cfg
```

to:

```text
<YOUR_DOTA_PATH>/game/dota/cfg/gamestate_integration/
```

Example:

```text
G:/SteamLibrary/steamapps/common/dota 2 beta/game/dota/cfg/gamestate_integration/
```

4. Run the project:

```bash
python main.py
```

## Spotify setup

Create a Spotify developer app and place these values in `.env`:

```env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

Your Spotify redirect URI must also be added in the Spotify developer dashboard.

## Configuration

The project uses `config.json`, but it is parsed as **JSON with comments**. That means you can keep helpful `// comments` inside the file.

### The most important settings

```jsonc
"active_profile": "copyrighted_mainstream",
"audio": {
  "mode": "cinema",
  "master_gain_percent": 100
}
```

### Recommended master gain values

- `70` → quieter / headphones
- `100` → neutral
- `120` → louder room speakers
- `140` → aggressive output

### Available profiles

- `default` → safer creator-friendly setup
- `custom_user_electronic` → uses the user's electronic playlist
- `copyrighted_mainstream` → mainstream copyrighted playlists

## Why there is no separate “output profile” system

Earlier versions included multiple named output profiles such as `headphones` and `home_speakers`. That was removed in favor of one simpler control:

```jsonc
"master_gain_percent": 100
```

This gives you one direct knob for the entire system without forcing a preset system that may not match your real setup.

## Cinema mode

Cinema mode changes how quickly the volume moves and how long dramatic states are held.

It is designed to:

- drop volume faster during intense situations
- recover volume more smoothly afterward
- avoid jitter between `teamfight`, `low_hp`, and calmer states

## Troubleshooting

### No Dota payload

- Check that the GSI file was copied to the correct Dota folder.
- Make sure the auth token in the GSI file matches the token in `config.json`.
- Restart Dota after copying the file.
- Make sure the local server port matches the GSI URI.

### No Spotify playback

- Open the Spotify desktop app.
- Start playback on that device at least once.
- Make sure the device is active in your Spotify account.

## Files included for GitHub

- `README.md`
- `README.pt-BR.md`
- `BRANDING.md`
- `CHANGELOG.md`
- `LICENSE`
- `.gitignore`
- `dota_gsi/gamestate_integration_aegis_music_system.cfg`

## License

MIT
