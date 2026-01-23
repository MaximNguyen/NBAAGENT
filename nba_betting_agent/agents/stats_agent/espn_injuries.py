"""ESPN Injuries API client.

Fetches injury reports from ESPN's unofficial JSON API.
Endpoint: https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team}/injuries

Note: This is an unofficial API. Structure discovered via network inspection.
"""

import httpx
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

from nba_betting_agent.agents.stats_agent.cache import StatsCache
from nba_betting_agent.agents.stats_agent.models import InjuryReport


# ESPN API accepts team abbreviations directly (BOS, LAL, etc.)
ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team}/injuries"


class ESPNInjuriesClient:
    """Client for fetching injury data from ESPN's API.

    Uses httpx for async HTTP requests with retry logic.
    Caches results with 1-hour TTL (injuries change frequently).
    """

    def __init__(self, cache: StatsCache | None = None):
        self._cache = cache or StatsCache()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _fetch_injuries(self, team_abbr: str) -> dict:
        """Fetch raw injury data from ESPN API.

        Args:
            team_abbr: Team abbreviation (e.g., "BOS", "LAL")

        Returns:
            Raw JSON response from ESPN API

        Raises:
            httpx.HTTPStatusError: On HTTP errors (4xx, 5xx)
            httpx.RequestError: On network errors
        """
        url = ESPN_INJURIES_URL.format(team=team_abbr.lower())

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    def _parse_injuries(self, data: dict, team_abbr: str) -> list[InjuryReport]:
        """Parse ESPN injury response into InjuryReport models.

        Args:
            data: Raw JSON from ESPN API
            team_abbr: Team abbreviation for the reports

        Returns:
            List of InjuryReport models
        """
        injuries = []
        now = datetime.now()

        # ESPN response structure (discovered via inspection):
        # {
        #   "team": {...},
        #   "injuries": [
        #     {
        #       "athlete": {"displayName": "...", "position": {"abbreviation": "..."}},
        #       "status": "Out" | "Questionable" | "Day-To-Day" | "Probable",
        #       "type": {"name": "Ankle"},  # Injury type
        #       "details": {"detail": "Out for season"}
        #     }
        #   ]
        # }

        raw_injuries = data.get("injuries", [])
        for item in raw_injuries:
            try:
                athlete = item.get("athlete", {})
                position_data = athlete.get("position", {})

                # Get injury type - can be in "type" or directly as "injury"
                injury_type = item.get("type", {})
                if isinstance(injury_type, dict):
                    injury_name = injury_type.get("name", "Unknown")
                else:
                    injury_name = str(injury_type) if injury_type else "Unknown"

                # Get details
                details_data = item.get("details", {})
                if isinstance(details_data, dict):
                    details = details_data.get("detail", "")
                else:
                    details = str(details_data) if details_data else ""

                injury = InjuryReport(
                    team=team_abbr.upper(),
                    player=athlete.get("displayName", "Unknown"),
                    position=position_data.get("abbreviation") if isinstance(position_data, dict) else None,
                    status=item.get("status", "Unknown"),
                    injury=injury_name,
                    details=details if details else None,
                    fetched_at=now,
                )
                injuries.append(injury)
            except Exception:
                # Skip malformed injury entries
                continue

        return injuries

    async def get_team_injuries(
        self, team_abbr: str
    ) -> tuple[list[InjuryReport], list[str]]:
        """Get injury reports for a team with cache fallback.

        Args:
            team_abbr: Team abbreviation (e.g., "BOS", "LAL")

        Returns:
            Tuple of (list of InjuryReport, list of error/warning messages)
        """
        errors = []
        cache_key = f"injuries:{team_abbr.upper()}"

        # Try live fetch
        try:
            data = await self._fetch_injuries(team_abbr)
            injuries = self._parse_injuries(data, team_abbr)

            # Cache the raw data (not parsed models)
            await self._cache.set(
                cache_key,
                {"injuries": [inj.model_dump(mode="json") for inj in injuries]},
                "injuries",
            )
            return injuries, errors

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Team not found - might be wrong abbreviation
                errors.append(f"ESPN injuries: team '{team_abbr}' not found (404)")
            else:
                errors.append(f"ESPN injuries: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            errors.append(f"ESPN injuries: network error - {e}")
        except Exception as e:
            errors.append(f"ESPN injuries: {type(e).__name__}: {e}")

        # Fall back to cache
        cached = await self._cache.get(cache_key, "injuries")
        if cached:
            if cached.is_stale:
                errors.append(f"Using stale injury data for {team_abbr}")

            # Parse cached data back into models
            injuries = [
                InjuryReport.model_validate(inj)
                for inj in cached.data.get("injuries", [])
            ]
            return injuries, errors

        # No cached data available - return empty list
        errors.append(f"No injury data available for {team_abbr}")
        return [], errors

    async def get_injuries_for_teams(
        self, team_abbrs: list[str]
    ) -> tuple[list[InjuryReport], list[str]]:
        """Get injuries for multiple teams.

        Args:
            team_abbrs: List of team abbreviations

        Returns:
            Tuple of (combined list of InjuryReport, combined error messages)
        """
        all_injuries = []
        all_errors = []

        for abbr in team_abbrs:
            injuries, errors = await self.get_team_injuries(abbr)
            all_injuries.extend(injuries)
            all_errors.extend(errors)

        return all_injuries, all_errors
