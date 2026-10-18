# Client for fetching arriving commuter trains to a station using
# Finnish Transport agency's DigiTraffic API.
# https://www.digitraffic.fi/en/railway-traffic/
# https://www.digitraffic.fi/rautatieliikenne/#liikennepaikan-saapuvat-ja-l%C3%A4htev%C3%A4t-junat-lukum%C3%A4%C3%A4r%C3%A4rajoitus

import datetime

import requests
from dateutil import tz

from alarmpi.clients import SourceError


class TrainClient:

    def __init__(self, section_data):
        self.section_data = section_data

    def fetch(self):
        """Fetch and format the next departures."""
        api_response = self.fetch_daily_train_data()
        return self.format_next_departures(api_response)

    def close(self):
        # No persistent resources to release.
        return

    def format_next_departures(self, api_response):
        """Format a list of API response departures to a list of dicts
        to pass back to clock.py.
        """
        locals_ = self.filter_commuter_trains(api_response)

        departure_rows = []
        for train in locals_:
            row = self.get_local_departure_row(train)

            # Ignore already departed trains
            if "actualTime" in row:
                continue

            # Determine the timestamp key to be used for sorting:
            # Prefer an estimate over the scheduled departure time.
            sort_key = "scheduledTime"
            scheduled_time_dt = self.utc_timestamp_to_local_datetime(
                row["scheduledTime"],
            )
            live_estimate_time_dt = None
            if "liveEstimateTime" in row:
                # Only display estimates differing by at least one minute.
                live_estimate_time_dt = self.utc_timestamp_to_local_datetime(
                    row["liveEstimateTime"],
                )
                td = live_estimate_time_dt - scheduled_time_dt
                sort_key = "liveEstimateTime"

                if abs(td.seconds) < 60:
                    live_estimate_time_dt = None

            sort_dt = self.utc_timestamp_to_local_datetime(row[sort_key])
            departure_rows.append({
                "liveEstimateTime": live_estimate_time_dt,
                "scheduledTime": scheduled_time_dt,
                "commuterLineID": train["commuterLineID"],
                "cancelled": train["cancelled"],
                "sortKey": sort_dt
            })

        departure_rows.sort(key=lambda row: row["sortKey"])

        # Limit trains to return to the count in the config
        MAX_NUMBER_OF_TRAINS = self.section_data["trains"]
        return departure_rows[:MAX_NUMBER_OF_TRAINS]

    def fetch_daily_train_data(self):
        """API call to get the next local arrivivals."""
        station = self.section_data["station_code"]
        URL = (
            f"https://rata.digitraffic.fi/api/v1/live-trains/station/{station}"
        )
        params = {
            "arrived_trains": 1,  # API minimum
            "arriving_trains": 20,
            "departed_trains": 1
        }

        # Catch any network related errors from the request itself
        try:
            r = requests.get(URL, params=params, timeout=(5, 10))
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            raise SourceError(f"Train request failed: {e}") from e

    def filter_commuter_trains(self, response):
        """Filter commuter trains heading towards Helsinki.
        Args:
            trains (list): list of API response trains
        Return:
            list of filtered trains
        """
        filtered = [train for train in response if
                    train["timetableType"] == "REGULAR" and
                    train["trainCategory"] == "Commuter" and
                    train["timeTableRows"][-1]["stationShortCode"] == "HKI"
                    ]

        return filtered

    def get_local_departure_row(self, train):
        """Return the local DEPARTURE row of an API response train.
        Args:
            train (dict): a single train object from an API response
        Return:
            the local departure row of the train's timeTableRows
        """
        rows = [row for row in train["timeTableRows"] if
                row["type"] == "DEPARTURE" and
                row["stationShortCode"] == self.section_data["station_code"]
                ]

        return rows[0]

    def timestamp_to_datetime(self, s):
        """Convert a timestamp to a Python datetime.
        Args:
            s (str) a timestamp in %Y-%m-%dT%H:%M:%S.000Z
        Returns:
            a datetime.datetime instance
        """
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.000Z")

    def utc_timestamp_to_local_datetime(self, s):
        """Convert a timestamp str in UTC as returned by the API to a datetime
        in local timezone.
        Args:
            s (str) a timestamp in %Y-%m-%dT%H:%M:%S.000Z
        Returns:
            a datetime.datetime instance
        """
        tz_utc = tz.tzutc()
        tz_local = tz.tzlocal()

        utc = datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.000Z")

        # Tell the datetime object that it's in UTC time zone since
        # datetime objects are 'naive' by default
        utc = utc.replace(tzinfo=tz_utc)

        return utc.astimezone(tz_local)

    def msecs_until_datetime(self, d):
        """Compute milliseconds until a future, timezone-aware local datetime.
        """
        tz_local = tz.tzlocal()
        now = datetime.datetime.now(tz=tz_local)

        if d <= now:
            return 0

        return (d - now).seconds * 1000
