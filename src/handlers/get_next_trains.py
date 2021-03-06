# Helper module for fetching the next 3 trains arriving at Kerava station using the
# Finnish Transport agency's DigiTraffic API.
# https://www.digitraffic.fi/en/railway-traffic/
# https://www.digitraffic.fi/rautatieliikenne/#liikennepaikan-saapuvat-ja-l%C3%A4htev%C3%A4t-junat-lukum%C3%A4%C3%A4r%C3%A4rajoitus

# This module differs from the other content handlers in that it is not a subclass
# of AlarmpiContent and not called by alarm_builder. Instead this serves
# as a pure helper class to clock.py for fetching the next train departures.


import requests
import datetime
import logging
from dateutil import tz


# Define common top level parameters: number of arriving trains
# and API response values to parse,
MAX_NUMBER_OF_TRAINS = 5
ARRIVING_STATION_CODE = "KE"
RETURN_TEMPLATE_KEYS = [
    "liveEstimateTime",
    "scheduledTime",
    "commuterLineID",
    "cancelled",
    "sortKey"
]

event_logger = logging.getLogger("eventLogger")

class TrainParser:

    def run(self):
        """Run the parser: either fetch the next departures or, in case of
        requests errors, return a list of templated error dicts.
        """
        try:
            api_response = self.fetch_daily_train_data()
            return self.format_next_departures(api_response)
        except requests.exceptions.RequestException as e:
            event_logger.error(str(e))
            return None

    def format_next_departures(self, api_response):
        """Format a list of API response departures to a list of dicts
        to pass back to clock.py.
        """
        locals_ = self.filter_commuter_trains(api_response)

        departure_rows = []
        for train in locals_:
            row = self.get_local_departure_row(train)

            # Drop already departed trains
            if "actualTime" in row:
                continue

            # Determine the timestamp key to be used for sorting:
            # if an estimate exists, use it, otherwise use scheduled departure time
            sort_key = "scheduledTime"
            scheduled_time_dt = self.utc_timestamp_to_local_datetime(row["scheduledTime"])
            live_estimate_time_dt = None
            if "liveEstimateTime" in row:
                # Check that liveEstimateTime differs from scheduledTime by at least 1 minute
                live_estimate_time_dt = self.utc_timestamp_to_local_datetime(
                    row["liveEstimateTime"])
                td = live_estimate_time_dt - scheduled_time_dt
                sort_key = "liveEstimateTime"

                if abs(td.seconds) < 60:
                    live_estimate_time_dt = None

            sort_dt = self.utc_timestamp_to_local_datetime(row[sort_key])

            d = dict.fromkeys(RETURN_TEMPLATE_KEYS)
            d.update({
                "liveEstimateTime": live_estimate_time_dt,
                "scheduledTime": scheduled_time_dt,
                "commuterLineID": train["commuterLineID"],
                "cancelled": train["cancelled"],
                "sortKey": sort_dt
            })
            departure_rows.append(d)

        departure_rows.sort(key=lambda row: row["sortKey"])
        return departure_rows[:MAX_NUMBER_OF_TRAINS]

    def fetch_daily_train_data(self):
        """API call to get the next local arrivivals."""
        URL = "https://rata.digitraffic.fi/api/v1/live-trains/station/{}".format(ARRIVING_STATION_CODE)
        params = {
            "arrived_trains": 1,  # API minumum to already arrived and departed trains is 1
            "arriving_trains": 20,
            "departed_trains": 1
        }

        r = requests.get(URL, params=params)
        return r.json()

    def filter_commuter_trains(self, response):
        """Filter a list of API response trains to commuter trains heading towards Helsinki.
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
        """Given an API response train, return the DEPARTURE row of its timeTableRows
        Args:
            train (dict): a single train object from an API response
        Return:
            the local departure row of the train's timeTableRows
        """
        rows = [row for row in train["timeTableRows"] if
                row["type"] == "DEPARTURE" and
                row["stationShortCode"] == ARRIVING_STATION_CODE
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
        """Compute the number of milliseconds until input datetime. Input is
        assumed to be a local, future timestamp as a timezone aware datetime instance.
        """
        tz_local = tz.tzlocal()
        now = datetime.datetime.now(tz=tz_local)

        if d <= now:
            return 0

        return (d - now).seconds * 1000
