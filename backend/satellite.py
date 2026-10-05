"""Copernicus Sentinel Hub access. Credentials and tokens stay on the server."""
import math
import os
import time
from datetime import datetime, timedelta, timezone
from threading import Lock

import requests

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STATS_URL = "https://sh.dataspace.copernicus.eu/statistics/v1"
FEATURES = ("B2_blue", "B3_green", "B4_red", "B8_nir", "B11_swir1", "B12_swir2", "ndvi", "ndwi")
EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["B02","B03","B04","B08","B11","B12","SCL","dataMask"]}],
    output: [{id: "data", bands: 8, sampleType: "FLOAT32"}, {id: "dataMask", bands: 1}]
  };
}
function evaluatePixel(s) {
  const valid = s.dataMask && ![0,1,3,8,9,10,11].includes(s.SCL)
    && (s.B08+s.B04)>0 && (s.B03+s.B08)>0;
  return {
    data: [s.B02,s.B03,s.B04,s.B08,s.B11,s.B12,
      valid ? (s.B08-s.B04)/(s.B08+s.B04) : 0,
      valid ? (s.B03-s.B08)/(s.B03+s.B08) : 0],
    dataMask: [valid ? 1 : 0]
  };
}
"""


class SatelliteError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def configured():
    return bool(os.environ.get("SH_CLIENT_ID") and os.environ.get("SH_CLIENT_SECRET"))


class SentinelHub:
    def __init__(self):
        self._token = None
        self._expires = 0
        self._token_lock = Lock()
        self._cache_lock = Lock()
        self._cache = {}

    def _post(self, url, **kwargs):
        try:
            response = requests.post(url, timeout=(5, 45), **kwargs)
        except requests.RequestException:
            raise SatelliteError("Copernicus could not be reached. Please try again.") from None
        if response.status_code in (401, 403):
            raise SatelliteError("Copernicus credentials or service permissions were rejected.", 503)
        if response.status_code == 429:
            raise SatelliteError("Copernicus request quota reached. Please try again later.", 429)
        if not response.ok:
            raise SatelliteError("Copernicus could not process this satellite request.")
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except ValueError:
            raise SatelliteError("Copernicus returned an invalid response.") from None

    def token(self):
        if not configured():
            raise SatelliteError("Live satellite data is not configured. Add SH_CLIENT_ID and SH_CLIENT_SECRET to the backend's Railway variables.", 503)
        with self._token_lock:
            if self._token and time.monotonic() < self._expires:
                return self._token
            data = self._post(TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": os.environ["SH_CLIENT_ID"],
                "client_secret": os.environ["SH_CLIENT_SECRET"],
            })
            try:
                token = data["access_token"]
                lifetime = float(data.get("expires_in", 300))
                if not isinstance(token, str) or not token or not math.isfinite(lifetime):
                    raise ValueError()
            except (KeyError, TypeError, ValueError):
                raise SatelliteError("Copernicus returned an invalid authentication response.") from None
            self._token = token
            self._expires = time.monotonic() + max(0, lifetime - 60)
            return token

    def features(self, latitude, longitude):
        token = self.token()
        key = (latitude, longitude)
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached and time.monotonic() < cached[0]:
                return cached[1]
        # 200 m square footprint, sampled at approximately 20 m.
        half_lat = 100 / 111320
        half_lon = half_lat / max(0.01, math.cos(math.radians(latitude)))
        bbox = [longitude-half_lon, latitude-half_lat, longitude+half_lon, latitude+half_lat]
        if bbox[0] < -180 or bbox[2] > 180 or bbox[1] < -90 or bbox[3] > 90:
            raise SatelliteError("Choose a location away from the poles or date line.", 400)
        end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        start = end - timedelta(days=30)
        iso = lambda d: d.isoformat().replace("+00:00", "Z")
        payload = {
            "input": {
                "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}},
                "data": [{"type": "sentinel-2-l2a", "dataFilter": {"mosaickingOrder": "mostRecent"}}],
            },
            "aggregation": {
                "timeRange": {"from": iso(start), "to": iso(end)},
                "aggregationInterval": {"of": "P1D"},
                "resx": 2*half_lon/10, "resy": 2*half_lat/10, "evalscript": EVALSCRIPT,
            },
        }
        data = self._post(STATS_URL, json=payload, headers={"Authorization": "Bearer " + token})
        result = self.parse(data, bbox)
        with self._cache_lock:
            if len(self._cache) >= 256:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = (time.monotonic()+900, result)
        return result

    @staticmethod
    def parse(data, bbox):
        if data.get("status") != "OK" or not isinstance(data.get("data"), list):
            raise SatelliteError("Copernicus returned incomplete satellite statistics.")
        for interval in sorted(data["data"], key=lambda row: row.get("interval", {}).get("from", ""), reverse=True):
            try:
                bands = interval["outputs"]["data"]["bands"]
                values = {}
                fractions = []
                for i, name in enumerate(FEATURES):
                    stats = bands[f"B{i}"]["stats"]
                    total, missing = stats["sampleCount"], stats["noDataCount"]
                    if total <= 0 or not 0 <= missing <= total:
                        raise ValueError()
                    fractions.append((total-missing)/total)
                    value = float(stats["mean"])
                    if not math.isfinite(value) or not (0 <= value <= 2 if i < 6 else -1 <= value <= 1):
                        raise ValueError()
                    values[name] = value
                if min(fractions) < .5:
                    continue
                observation = interval["interval"]
                datetime.fromisoformat(observation["from"].replace("Z", "+00:00"))
                return values, {
                    "provider": "Copernicus Sentinel Hub", "collection": "sentinel-2-l2a",
                    "observation_date": observation["from"][:10],
                    "observation_interval": observation, "bbox": bbox,
                    "valid_pixel_percent": round(min(fractions)*100, 1),
                    "footprint_metres": 200, "lookback_days": 30,
                    "description": "Latest usable daily observation; mean of cloud/shadow/snow-masked pixels in a 200 m area. Not a real-time satellite feed.",
                }
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                continue
        raise SatelliteError("No usable Sentinel-2 observation with at least 50% clear pixels was found here in the last 30 days. Try another location.", 422)


sentinel = SentinelHub()
