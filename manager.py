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

        league_key = f"{self.league_id}.{self.game_key}"
        if not league_key or not self.league_id:
            self.logger.warning("League ID not configured")
            return

        try:
            if self.display_mode == 'standings':
                data = self._api_get(f'/league/{league_key}/standings')
                if data:
                    self.last_data = self._parse_standings(data)
            elif self.display_mode == 'scoreboard':
                data = self._api_get(f'/league/{league_key}/scoreboard')
                if data:
                    self.last_data = self._parse_scoreboard(data)
            elif self.display_mode == 'myteam':
                if self.team_key:
                    data = self._api_get(f'/team/{self.team_key}/standings')
                    if data:
                        self.last_data = self._parse_myteam(data)
                else:
                    self.logger.warning("team_key required for myteam mode")
            else:
                self.logger.warning(f"Unknown display_mode {self.display_mode}")
        except Exception as e:
            self.logger.error(f"Update error: {e}")

    def _generate_mock_data(self):
        """Generate mock data for dry-run testing."""
        mode = self.display_mode
        if mode == 'standings':
            teams = [
                'Eagles', 'Patriots', 'Cowboys', 'Packers', 'Chiefs', '49ers', 'Ravens', 'Bills',
                'Chargers', 'Dolphins', 'Steelers', 'Broncos'
            ]
            lines = []
            for i, name in enumerate(teams, start=1):
                wins = max(0, 10 - i)
                losses = i - 1
                lines.append(f"{i}. {name[:10]} {wins}-{losses}")
            return {'type': 'standings', 'lines': lines, 'league_name': 'Mock League'}
        elif mode == 'scoreboard':
            lines = [
                'Eagles 112.4 @ Patriots 98.2',
                'Cowboys 105.1 @ Packers 110.3',
                'Chiefs 124.0 @ 49ers 119.8',
                'Ravens 87.5 @ Bills 92.1',
                'Chargers 101.2 @ Dolphins 95.6',
                'Steelers 88.9 @ Broncos 103.4'
            ]
            return {'type': 'scoreboard', 'lines': lines, 'week': 'Mock Week 12'}
        elif mode == 'myteam':
            lines = ['My Team', 'Rank 3 8-4', 'PF 1150.2', 'PA 1084.7']
            return {'type': 'myteam', 'lines': lines}
        else:
            return {'type': 'unknown', 'lines': ['Dry run mode']}

    def _parse_standings(self, data):
        try:
            league = data.get('fantasy_content', {}).get('league', {})
            teams = league.get('standings', {}).get('teams', {}).get('team', [])
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
            team = data.get('fantasy_content', {}).get('team', {})
            name = team.get('name', 'Unknown')
            standings = team.get('standings', {})
            rank = standings.get('rank', '?')
            w = standings.get('outcome_totals', {}).get('wins', 0)
            l = standings.get('outcome_totals', {}).get('losses', 0)
            return {'type': 'myteam', 'lines': [f"{name}", f"Rank {rank} {w}-{l}"]}
        except Exception as e:
            self.logger.error(f"Parse myteam error: {e}")
            return {'type': 'myteam', 'lines': ['Error parsing']}

    def display(self, force_clear=False):
        if force_clear:
            self.display_manager.clear()
        width = self.display_manager.width
        height = self.display_manager.height

        if not self.last_data:
            if self.dry_run:
                # Generate mock data immediately for testing
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
            visible_lines = []
            for i in range(max_visible):
                idx = (start + i) % len(lines)
                visible_lines.append(lines[idx])
        else:
            self._scroll_offset = 0
            visible_lines = lines[:max_visible]

        # Simple header if space allows
        y_start = height // 6
        line_height = max(6, height // max(max_visible + 1, 2))
        for i, line in enumerate(visible_lines):
            y = y_start + i * line_height
            # Truncate line to fit width roughly
            display_line = line[:32]
            self.display_manager.draw_text(display_line, x=width//2, y=y, color=self.color, centered=True)

        self.display_manager.update_display()

    def validate_config(self):
        if not super().validate_config():
            return False
        if self.dry_run:
            # Dry run does not require real credentials
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

    # Vegas mode integration
    def get_vegas_participation(self):
        # Participate in scroll when scrolling is enabled, otherwise pause
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
