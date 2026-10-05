import os
import unittest
from unittest.mock import Mock, patch

import requests

from backend.satellite import SentinelHub, SatelliteError, FEATURES, STATS_URL
import server


def observation(day, missing=10):
    return {
        "interval": {"from": day+"T00:00:00Z", "to": day+"T23:59:59Z"},
        "outputs": {"data": {"bands": {
            f"B{i}": {"stats": {"mean": .2+i*.02, "sampleCount": 100, "noDataCount": missing}}
            for i in range(8)
        }}},
    }


class SatelliteTests(unittest.TestCase):
    def test_selects_latest_clear_observation_and_rejects_invalid_values(self):
        malformed = observation("2026-10-04")
        malformed["outputs"]["data"]["bands"]["B2"]["stats"]["mean"] = float("nan")
        data = {"status": "OK", "data": [observation("2026-10-02"), observation("2026-10-05", 80), malformed, observation("2026-10-03")]}
        features, meta = SentinelHub.parse(data, [1, 2, 3, 4])
        self.assertEqual(tuple(features), FEATURES)
        self.assertEqual(meta["observation_date"], "2026-10-03")
        self.assertEqual(meta["valid_pixel_percent"], 90)

    def test_no_usable_imagery(self):
        for data in [{"status": "OK", "data": []}, {"status": "OK", "data": [observation("2026-10-03", 100)]}]:
            with self.assertRaises(SatelliteError) as error:
                SentinelHub.parse(data, [])
            self.assertEqual(error.exception.status, 422)

    @patch.dict(os.environ, {"SH_CLIENT_ID": "test-client", "SH_CLIENT_SECRET": "test-secret"})
    @patch("backend.satellite.requests.post")
    def test_authentication_request_cache_and_geographic_payload(self, post):
        auth = Mock(ok=True, status_code=200)
        auth.json.return_value = {"access_token": "test-token", "expires_in": 3600}
        stats = Mock(ok=True, status_code=200)
        stats.json.return_value = {"status": "OK", "data": [observation("2026-10-03")]}
        post.side_effect = [auth, stats, stats]
        hub = SentinelHub()
        first = hub.features(12.9716, 77.5946)
        self.assertEqual(first, hub.features(12.9716, 77.5946))
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.args[0], STATS_URL)
        payload = post.call_args.kwargs["json"]
        bbox = payload["input"]["bounds"]["bbox"]
        self.assertLess(bbox[0], 77.5946)
        self.assertGreater(bbox[2], 77.5946)
        self.assertEqual(payload["aggregation"]["aggregationInterval"]["of"], "P1D")
        self.assertNotIn("test-secret", str(payload))
        hub.features(13, 77)
        self.assertEqual(post.call_count, 3)

    @patch("backend.satellite.requests.post")
    def test_provider_errors_do_not_expose_response_secrets(self, post):
        for code, status in [(401, 503), (403, 503), (429, 429), (500, 502)]:
            post.return_value = Mock(ok=False, status_code=code, text="SECRET")
            with self.assertRaises(SatelliteError) as error:
                SentinelHub()._post(STATS_URL)
            self.assertEqual(error.exception.status, status)
            self.assertNotIn("SECRET", str(error.exception))
        post.side_effect = requests.Timeout()
        with self.assertRaises(SatelliteError):
            SentinelHub()._post(STATS_URL)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_credentials_and_explicit_demo(self):
        client = server.app.test_client()
        live = client.post("/analyze", json={"latitude": 12, "longitude": 77})
        self.assertEqual(live.status_code, 503)
        self.assertNotIn("features", live.json)
        demo = client.post("/analyze", json={"latitude": 12, "longitude": 77, "data_source": "demo"})
        self.assertEqual(demo.status_code, 200)
        self.assertEqual(demo.json["data_source"], "demo")

    @patch("server.sentinel.features")
    def test_live_model_uses_satellite_features_without_random_variation(self, features):
        raw, meta = SentinelHub.parse({"status": "OK", "data": [observation("2026-10-03")]}, [])
        features.return_value = (raw, meta)
        client = server.app.test_client()
        response = client.post("/analyze", json={"latitude": 12, "longitude": 77, "analysis_run": "123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["features"], raw)
        self.assertEqual(response.json["satellite"]["observation_date"], "2026-10-03")
        self.assertEqual(response.json["scenario_variation"], 0)
        features.reset_mock()
        for body in [{"latitude": "nan"}, {"longitude": 181}, [1], {"mineral": "gold"}, {"data_source": "fake"}]:
            self.assertEqual(client.post("/analyze", json=body).status_code, 400)
        features.assert_not_called()


if __name__ == "__main__":
    unittest.main()
