"""
Yahoo Fantasy Football Plugin for LEDMatrix

Displays Yahoo Fantasy Football league standings and scores.
"""

from src.plugin_system.base_plugin import BasePlugin
import time
import requests
import xml.etree.ElementTree as ET

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
        self.bdf_font = None  # avoid AttributeError
        self.logger.info("Yahoo Fantasy Football plugin initialized")

    def _load_config(self, config):
        self.cfg_client_id = config.get('yahoo_client_id', '')
        self.cfg_client_secret = config.get('yahoo_client_secret', '')
        self.cfg_refresh_token = config.get('yahoo_refresh_token', '')
        self.cfg_league_id = config.get('league_id', '')
        self.cfg_game_key = config.get('game_key', '461')
        self.cfg_team_key = config.get('team_key', '')
        self.cfg_display_mode = config.get('display_mode', 'standings')
        self.cfg_update_interval = config.get('update_interval', 300)
        self.cfg_display_duration = config.get('display_duration', 30)
        self.cfg_color = tuple(config.get('color', [255, 255, 255]))
        self.cfg_layout = config.get('layout', 'auto')
        self.cfg_enable_scroll = config.get('enable_scroll', False)
        self.cfg_scroll_speed = config.get('scroll_speed', 2)
        self.cfg_max_lines = config.get('max_lines', 0)
        self.cfg_dry_run = config.get('dry_run', True)

    def on_config_change(self, new_config):
        super().on_config_change(new_config)
        self._load_config(self.config)
        self._token_cache = None

    def _get_access_token(self):
        now = time.time()
        if self._token_cache and now < self._token_expires - 60:
            return self._token_cache

        if not self.cfg_client_id or not self.cfg_client_secret or not self.cfg_refresh_token:
            self.logger.error("Yahoo credentials not configured")
            return None

        data = {
            'grant_type': 'refresh_token',
            'client_id': self.cfg_client_id,
            'client_secret': self.cfg_client_secret,
            'refresh_token': self.cfg_refresh_token
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
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            content = resp.text
            return ET.fromstring(content)
        except Exception as e:
            self.logger.error(f"Yahoo API error {path}: {e}")
            return None

    def update(self):
        now = time.time()
        if now - self.last_update < self.cfg_update_interval:
            return
        self.last_update = now

        if self.cfg_dry_run:
            self.logger.info("Dry run mode enabled – using mock data")
            self.last_data = self._generate_mock_data()
            return

        if not self.cfg_league_id:
            self.logger.warning("League ID not configured")
            return

        league_key = f"{self.cfg_game_key}.l.{self.cfg_league_id}"
        try:
            if self.cfg_display_mode == 'standings':
                data = self._api_get(f'/league/{league_key}/standings')
                if data is not None:
                    self.last_data = self._parse_standings_xml(data)
            elif self.cfg_display_mode == 'scoreboard':
                data = self._api_get(f'/league/{league_key}/scoreboard')
                if data is not None:
                    self.last_data = self._parse_scoreboard_xml(data)
            elif self.cfg_display_mode == 'myteam':
                if self.cfg_team_key:
                    data = self._api_get(f'/team/{self.cfg_team_key}')
                    if data is not None:
                        self.last_data = self._parse_myteam_xml(data)
                else:
                    self.logger.warning("team_key required for myteam mode")
            else:
                self.logger.warning(f"Unknown display_mode {self.cfg_display_mode}")
        except Exception as e:
            self.logger.error(f"Update error: {e}")

    def _generate_mock_data(self):
        mode = self.cfg_display_mode
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

    def _text(self, elem):
        return elem.text.strip() if elem is not None and elem.text else ''

    def _parse_standings_xml(self, root):
        try:
            league = root.find('.//league')
            league_name = self._text(league.find('name')) if league is not None else ''
            teams_elem = root.find('.//standings/teams')
            lines = []
            if teams_elem is not None:
                for team_elem in teams_elem.findall('team'):
                    name = self._text(team_elem.find('name'))
                    standings_elem = team_elem.find('team_standings')
                    rank = self._text(standings_elem.find('rank')) if standings_elem is not None else '?'
                    wins = self._text(standings_elem.find('outcome_totals/wins')) if standings_elem is not None else '0'
                    losses = self._text(standings_elem.find('outcome_totals/losses')) if standings_elem is not None else '0'
                    lines.append(f"{rank}. {name[:14]} {wins}-{losses}")
            return {'type': 'standings', 'lines': lines or ['No teams'], 'league_name': league_name}
        except Exception as e:
            self.logger.error(f"Parse standings error: {e}")
            return {'type': 'standings', 'lines': ['Error parsing']}

    def _parse_scoreboard_xml(self, root):
        try:
            matchups_elem = root.find('.//scoreboard/matchups')
            lines = []
            if matchups_elem is not None:
                for matchup in matchups_elem.findall('matchup')[:4]:
                    teams = matchup.find('matchup_teams')
                    if teams is None:
                        continue
                    matchup_teams = teams.findall('matchup_team')
                    if len(matchup_teams) < 2:
                        continue
                    t1 = matchup_teams[0]
                    t2 = matchup_teams[1]
                    n1 = self._text(t1.find('team/name'))
                    n2 = self._text(t2.find('team/name'))
                    s1 = self._text(t1.find('team_points/total'))
                    s2 = self._text(t2.find('team_points/total'))
                    lines.append(f"{n1[:10]} {s1} @ {n2[:10]} {s2}")
            return {'type': 'scoreboard', 'lines': lines or ['No matchups'], 'week': ''}
        except Exception as e:
            self.logger.error(f"Parse scoreboard error: {e}")
            return {'type': 'scoreboard', 'lines': ['Error parsing']}

    def _parse_myteam_xml(self, root):
        try:
            team = root.find('.//team')
            name = self._text(team.find('name')) if team is not None else 'Unknown'
            standings = team.find('team_standings') if team is not None else None
            rank = self._text(standings.find('rank')) if standings is not None else '?'
            wins = self._text(standings.find('outcome_totals/wins')) if standings is not None else '0'
            losses = self._text(standings.find('outcome_totals/losses')) if standings is not None else '0'
            return {'type': 'myteam', 'lines': [name, f"Rank {rank} {wins}-{losses}"]}
        except Exception as e:
            self.logger.error(f"Parse myteam error: {e}")
            return {'type': 'myteam', 'lines': ['Error parsing']}

    def display(self, force_clear=False):
        width = self.display_manager.width
        height = self.display_manager.height
        self.display_manager.clear()
        if not self.last_data:
            self.display_manager.draw_text("Yahoo Fantasy", x=width//2, y=height//2, color=self.cfg_color, centered=True)
            self.display_manager.update_display()
            return
        lines = self.last_data.get('lines', [])
        if self.cfg_layout == 'auto':
            if width >= 128 and height >= 64:
                layout_key = 'large'
            elif width >= 64:
                layout_key = 'wide'
            else:
                layout_key = 'compact'
        else:
            layout_key = self.cfg_layout
        if self.cfg_max_lines > 0:
            max_visible = self.cfg_max_lines
        else:
            defaults = {'compact': 3, 'wide': 5, 'large': 8}
            max_visible = defaults.get(layout_key, 4)
        if self.cfg_enable_scroll and len(lines) > max_visible:
            now = time.time()
            if now - self._last_display_time > 0.5:
                self._scroll_offset = (self._scroll_offset + 1) % len(lines)
                self._last_display_time = now
            start = self._scroll_offset
            visible_lines = [lines[(start + i) % len(lines)] for i in range(max_visible)]
        else:
            self._scroll_offset = 0
            visible_lines = lines[:max_visible]
        top_margin = height // 8
        line_height = max(8, height // max(max_visible + 2, 2))
        y_start = top_margin
        for i, line in enumerate(visible_lines):
            y = y_start + i * line_height
            display_line = line[:32]
            self.display_manager.draw_text(display_line, x=width//2, y=y, color=self.cfg_color, centered=True)
        self.display_manager.update_display()

    def validate_config(self):
        if not super().validate_config():
            return False
        if self.cfg_dry_run:
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
        info['mode'] = self.cfg_display_mode
        info['league_id'] = self.cfg_league_id
        info['last_update'] = self.last_update
        return info

    def get_vegas_participation(self):
        return 'scroll' if self.cfg_enable_scroll else 'pause'

    def get_vegas_content(self):
        if not self.last_data:
            return "Yahoo Fantasy"
        lines = self.last_data.get('lines', [])
        return "  •  ".join(lines) if lines else "No data"

    def get_vegas_render_width(self):
        return 40