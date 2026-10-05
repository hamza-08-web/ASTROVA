import unittest
from unittest.mock import Mock, patch

import server


LIVE_FEATURES = {
    "B2_blue": .086963, "B3_green": .112317, "B4_red": .121293,
    "B8_nir": .24825, "B11_swir1": .233266, "B12_swir2": .171218,
    "ndvi": .411198, "ndwi": -.421007,
}


class MineralModelsTests(unittest.TestCase):
    @patch("server.sentinel.features")
    def test_same_satellite_observation_uses_independent_mineral_models(self, satellite):
        satellite.return_value = (LIVE_FEATURES, {"observation_date": "2026-10-04"})
        client = server.app.test_client()
        scores = {}
        for mineral in ["Manganese", "Nickel", "Cobalt"]:
            with patch.dict(server.models, {mineral: Mock(wraps=server.models[mineral])}):
                response = client.post("/analyze", json={
                    "mineral": mineral, "latitude": 12.9716, "longitude": 77.5946,
                    "data_source": "live", "analysis_run": "first",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json["model_target"], mineral)
                self.assertEqual(response.json["features"], LIVE_FEATURES)
                self.assertEqual(response.json["scenario_variation"], 0)
                server.models[mineral].predict_proba.assert_called_once()
                scores[mineral] = response.json["prospectivity_score"]
        # This real-observation regression fixture previously gave one shared score.
        self.assertEqual(len(set(scores.values())), 3, scores)
        for mineral, score in scores.items():
            response = client.post("/analyze", json={
                "mineral": mineral, "latitude": 12.9716, "longitude": 77.5946,
                "data_source": "live", "analysis_run": "second",
            })
            self.assertEqual(response.json["prospectivity_score"], score)

    def test_demo_and_heatmap_route_supported_minerals(self):
        client = server.app.test_client()
        for mineral in server.models:
            response = client.post("/analyze", json={"mineral": mineral, "data_source": "demo"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["model_target"], mineral)
        self.assertEqual(client.get("/heatmap?mineral=gold").status_code, 400)
        self.assertEqual(client.get("/heatmap?latitude=nan").status_code, 400)


if __name__ == "__main__":
    unittest.main()
