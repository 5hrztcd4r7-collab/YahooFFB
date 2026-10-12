""" 
Yahoo Fantasy Football Plugin for LEDMatrix

Displays Yahoo Fantasy Football league standings and scores.
"""

from src.plugin_system.base_plugin import BasePlugin
import time
import requests
from datetime import datetime, timezone

class YahooFantasyFootballPlugin(BasePlugin):
    """Yahoo Fantasy Football plugin."""

    FONT = ("press_start", 8)

    def __init__(self, plugin_id, config, display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        self._load_config(config)
        self._token_cache = None
        self._token_expires = 0
        self.last_data = None
        self.last_update = 0
        self._scroll_offset = 0
        self._last_display_time = 0
        self.bdf_font = None
        self.logger.info("Yahoo Fantasy Football plugin initialized")

    def _load_config(self, config):
        self.client_id = config.get('yahoo_client_id', '')
        self.client_secret = config.get('yahoo_client_secret', '')
        self.refresh_token = config.get('yahoo_refresh_token', '')
        self.league_id = config.get('league_id', '')
        self.game_key = config.get('game_key', 'nfl')
        self.team_key = config.get('team_key', '')
        self.display_mode = config.get('display_mode', 'standings')
        self.update_interval = config.get('update_interval', 300)
        self.display_duration = config.get('display_duration', 30)
        self.color = tuple(config.get('color', [255, 255, 255]))
        self.layout_mode = config.get('layout', 'auto')
        self.enable_scroll = config.get('enable_scroll', False)
        self.scroll_speed = config.get('scroll_speed', 2)
        self.max_lines = config.get('max_lines', 0)
        self.dry_run = config.get('dry_run', True)

    def on_config_change(self, new_config):
        super().on_config_change(new_config)
        self._load_config(self.config)
        self._token_cache = None

    def _get_access_token(self):
        now = time.time()
        if self._token_cache and now < self._token_expires - 60:
            return self._token_cache

        if not self.client_id or not self.client_secret or not self.refresh_token:
            self.logger.error("Yahoo credentials not configured")
            return None

        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token
        }
        try:
            resp = requests.post('https://api.login.yahoo.com/oauth2/get_token', data=data, timeout=10)
            resp.raise_for_status()
            j = resp.json()
            token = j.get('access_token')
            expires_in = j.get('expires_in', 3600)
            if token:
                self._token_cache = token
                self._token_expires = now + expires_in
                self.logger.debug("Yahoo access token refreshed")
                return token
        except Exception as e:
            self.logger.error(f"Failed to refresh Yahoo token: {e}")
        return None

    def _api_get(self, path):
        token = self._get_access_token()
        if not token:
            return None
        url = f"https://fantasysports.yahooapis.com/fantasy/v2{path}"
        headers = {'Authorization': f'Bearer {token}'}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"API request failed {path}: {e}")
            return None

    def update(self):
        if self.dry_run:
            self.logger.info("Dry run mode enabled – using mock data")
            self.last_data = self._generate_mock_data()
            self.last_update = time.time()
            return

        if not self.league_id:
            self.logger.error("league_id required")
            return

        path = f"/league/{self.game_key}.l.{self.league_id}/settings"
        data = self._api_get(path)
        if not data:
            self.logger.error("Failed to fetch league data")
            return

        if self.display_mode == 'standings':
            parsed = self._parse_standings(data)
        elif self.display_mode == 'scoreboard':
            parsed = self._parse_scoreboard(data)
        elif self.display_mode == 'myteam':
            parsed = self._parse_myteam(data)
        else:
            parsed = {'type': 'standings', 'lines': ['Unknown mode']}

        self.last_data = parsed
        self.last_update = time.time()

    def _generate_mock_data(self):
        if self.display_mode == 'standings':
            lines = [
                "1. Team Alpha 8-0",
                "2. Team Beta 7-1",
                "3. Team Gamma 6-2",
                "4. Team Delta 5-3",
                "5. Team Epsilon 4-4",
                "6. Team Zeta 3-5",
                "7. Team Eta 2-6",
                "8. Team Theta 1-7",
                "9. Team Iota 0-8",
                "10. Team Kappa 0-8"
            ]
        elif self.display_mode == 'scoreboard':
            lines = [
                "Alpha 120 @ Beta 98",
                "Gamma 105 @ Delta 110",
                "Epsilon 88 @ Zeta 92",
                "Eta 75 @ Theta 80"
            ]
        else:
            lines = [
                "My Team: Alpha",
                "Record: 8-0",
                "Points For: 1120",
                "Points Against: 890",
                "Next Matchup: vs Beta"
            ]
        return {'type': self.display_mode, 'lines': lines, 'league_name': 'Mock League'}

    def _parse_standings(self, data):
        try:
            league = data.get('fantasy_content', {}).get('league', {})
            teams = league.get('teams', {}).get('team', [])
            if not isinstance(teams, list):
                teams = [teams]
            standings = []
            for t in teams[:8]:
                team = t.get('team', {})
                name = team.get('name', 'Unknown')
                rank = team.get('team_standings', {}).get('rank', '?')
                w = team.get('team_standings', {}).get('outcome_totals', {}).get('wins', 0)
                l = team.get('team_standings', {}).get('outcome_totals', {}).get('losses', 0)
                standings.append(f"{rank}. {name[:14]} {w}-{l}")
            return {'type': 'standings', 'lines': standings, 'league_name': league.get('name', '')}
        except Exception as e:
            self.logger.error(f"Parse standings error: {e}")
            return {'type': 'standings', 'lines': ['Error parsing']}

    def _parse_scoreboard(self, data):
        try:
            league = data.get('fantasy_content', {}).get('league', {})
            scoreboard = league.get('scoreboard', {})
            matchups = scoreboard.get('matchups', {}).get('matchup', [])
            if not isinstance(matchups, list):
                matchups = [matchups]
            lines = []
            for m in matchups[:4]:
                teams = m.get('matchup_teams', {}).get('matchup_team', [])
                if not isinstance(teams, list):
                    teams = [teams]
                t1 = teams[0].get('team', {}) if len(teams) > 0 else {}
                t2 = teams[1].get('team', {}) if len(teams) > 1 else {}
                n1 = t1.get('name', 'T1')[:10]
                n2 = t2.get('name', 'T2')[:10]
                s1 = t1.get('team_points', {}).get('total', {}).get('total', '0')
                s2 = t2.get('team_points', {}).get('total', {}).get('total', '0')
                lines.append(f"{n1} {s1} @ {n2} {s2}")
            return {'type': 'scoreboard', 'lines': lines, 'week': scoreboard.get('week', '')}
        except Exception as e:
            self.logger.error(f"Parse scoreboard error: {e}")
            return {'type': 'scoreboard', 'lines': ['Error parsing']}

    def _parse_myteam(self, data):
        try:
            league = data.get('fantasy_content', {}).get('league', {})
            teams = league.get('teams', {}).get('team', [])
            if not isinstance(teams, list):
                teams = [teams]
            lines = []
            for t in teams:
                team = t.get('team', {})
                if self.team_key and team.get('team_key') != self.team_key:
                    continue
                name = team.get('name', 'Unknown')
                rank = team.get('team_standings', {}).get('rank', '?')
                w = team.get('team_standings', {}).get('outcome_totals', {}).get('wins', 0)
                l = team.get('team_standings', {}).get('outcome_totals', {}).get('losses', 0)
                pf = team.get('team_points', {}).get('total', {}).get('total', '0')
                lines.append(f"{name}: {w}-{l} PF {pf}")
                break
            return {'type': 'myteam', 'lines': lines}
        except Exception as e:
            self.logger.error(f"Parse myteam error: {e}")
            return {'type': 'myteam', 'lines': ['Error parsing']}

    def display(self, force_clear=False):
        # Always clear to avoid white fill artifacts
        self.display_manager.clear()
        width = self.display_manager.width
        height = self.display_manager.height

        if not self.last_data:
            if self.dry_run:
                self.last_data = self._generate_mock_data()
            else:
                self.display_manager.draw_text("Yahoo Fantasy", x=width//2, y=height//2, color=self.color, centered=True)
                self.display_manager.update_display()
                return

        lines = self.last_data.get('lines', [])
        # Determine layout and max lines
        if self.layout_mode == 'auto':
            if width >= 128 and height >= 64:
                layout_key = 'large'
            elif width >= 64:
                layout_key = 'wide'
            else:
                layout_key = 'compact'
        else:
            layout_key = self.layout_mode

        if self.max_lines > 0:
            max_visible = self.max_lines
        else:
            defaults = {'compact': 3, 'wide': 5, 'large': 8}
            max_visible = defaults.get(layout_key, 4)

        # Scroll handling
        if self.enable_scroll and len(lines) > max_visible:
            now = time.time()
            if now - self._last_display_time > 0.5:
                self._scroll_offset = (self._scroll_offset + 1) % len(lines)
                self._last_display_time = now
            start = self._scroll_offset
            visible_lines = [lines[(start + i) % len(lines)] for i in range(max_visible)]
        else:
            self._scroll_offset = 0
            visible_lines = lines[:max_visible]

        # Better spacing
        top_margin = height // 8
        line_height = max(8, (height - 2*top_margin) // max_visible)
        y_start = top_margin + line_height // 2
        for i, line in enumerate(visible_lines):
            y = y_start + i * line_height
            display_line = line[:32]
            self.display_manager.draw_text(display_line, x=width//2, y=y, color=self.color, centered=True)

        self.display_manager.update_display()

    def validate_config(self):
        if not super().validate_config():
            return False
        if self.dry_run:
            return True
        missing = []
        for k in ['yahoo_client_id', 'yahoo_client_secret', 'yahoo_refresh_token', 'league_id']:
            if not self.config.get(k):
                missing.append(k)
        if missing:
            self.logger.error(f"Missing config: {', '.join(missing)}")
            return False
        return True

    def get_info(self):
        info = super().get_info()
        info['mode'] = self.display_mode
        info['league_id'] = self.league_id
        info['last_update'] = self.last_update
        return info

    def get_vegas_participation(self):
        return 'scroll' if self.enable_scroll else 'pause'

    def get_vegas_content(self):
        if not self.last_data:
            return "Yahoo Fantasy"
        lines = self.last_data.get('lines', [])
        if not lines:
            return "No data"
        return "  •  ".join(lines)

    def get_vegas_render_width(self):
        return 40
