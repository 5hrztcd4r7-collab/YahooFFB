# Yahoo Fantasy Football Plugin for LEDMatrix

Displays your Yahoo Fantasy Football league standings or scores on a Raspberry Pi LED Matrix.

## Setup

1. Create a Yahoo Developer App with Fantasy Sports scope
   - Get `client_id` and `client_secret`
2. Obtain a refresh token via OAuth2 authorization code flow with redirect URI `oob`
3. Find your league ID in Yahoo Fantasy League Settings
4. Optionally find your team key: `league_id.nfl.t.X`

## Configuration

Add to `config/config.json`:
```json
{
  "yahoo-fantasy-football": {
    "enabled": true,
    "yahoo_client_id": "...",
    "yahoo_client_secret": "...",
    "yahoo_refresh_token": "...",
    "league_id": "12345",
    "game_key": "nfl",
    "team_key": "",
    "display_mode": "standings",
    "layout": "auto",
    "enable_scroll": false,
    "scroll_speed": 2,
    "max_lines": 0,
    "dry_run": false,
    "display_duration": 30,
    "update_interval": 300,
    "color": [255,255,255]
  }
}
```

### Dry-run mode

Set `"dry_run": true` to test layouts and scrolling without Yahoo credentials. The plugin will generate mock standings/scoreboard data:

```json
"dry_run": true,
"display_mode": "standings"
```

This is useful for verifying display on your Pi before obtaining OAuth tokens. No network calls are made.

### Layouts & scrolling

- `layout`: `auto` | `compact` | `wide` | `large`. Auto-detects from matrix width/height.
- `enable_scroll`: when true and lines exceed visible area, content scrolls vertically.
- `max_lines`: override auto line count (0 = auto).

### Vegas mode

The plugin integrates with LEDMatrix Vegas mode:
- `get_vegas_participation()` returns `scroll` if scrolling enabled, otherwise `pause`.
- `get_vegas_content()` provides a concatenated string of lines for the scrolling strip.

Enable scrolling in config to participate in Vegas strip.

Display modes:
- `standings` – league standings
- `scoreboard` – current week matchups
- `myteam` – your team's record, requires `team_key`

## Installation

Copy this folder to `plugin-repos/` and restart LEDMatrix, or install via Plugin Store.

Requires `requests` Python package.

Attribution: Fantasy data provided by Yahoo Fantasy.
