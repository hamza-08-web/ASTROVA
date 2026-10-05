from __future__ import annotations

import csv
import random
from pathlib import Path

BASE_PROFILES = {
    "manganese": {
        "B2_blue": 0.22,
        "B3_green": 0.30,
        "B4_red": 0.27,
        "B8_nir": 0.44,
        "B11_swir1": 0.36,
        "B12_swir2": 0.30,
        "ndvi": 0.26,
        "ndwi": 0.12,
    },
    "nickel": {
        "B2_blue": 0.26,
        "B3_green": 0.35,
        "B4_red": 0.29,
        "B8_nir": 0.48,
        "B11_swir1": 0.41,
        "B12_swir2": 0.37,
        "ndvi": 0.30,
        "ndwi": 0.18,
    },
    "cobalt": {
        "B2_blue": 0.18,
        "B3_green": 0.27,
        "B4_red": 0.21,
        "B8_nir": 0.36,
        "B11_swir1": 0.31,
        "B12_swir2": 0.27,
        "ndvi": 0.18,
        "ndwi": 0.09,
    },
}

FEATURE_KEYS = [
    "B2_blue",
    "B3_green",
    "B4_red",
    "B8_nir",
    "B11_swir1",
    "B12_swir2",
    "ndvi",
    "ndwi",
]


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def generate_extended_dataset(output_path: Path | str, rows_per_mineral: int = 1800):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(42)
    rows = []

    for mineral_name, base_profile in BASE_PROFILES.items():
        mineral_rows = []
        mineral_scores = []

        for index in range(rows_per_mineral):
            latitude = (rng.uniform(-35, 35) if index % 2 == 0 else rng.uniform(-10, 25))
            longitude = rng.uniform(-160, 180)

            signal = rng.uniform(0.18, 0.82)
            feature_row = {}
            for feature_name in FEATURE_KEYS:
                profile_value = base_profile[feature_name]
                noise = (rng.uniform(-0.12, 0.12))
                feature_row[feature_name] = clamp(
                    profile_value + (signal - 0.5) * 0.18 + noise,
                    0.03,
                    0.9,
                )

            if mineral_name == "manganese":
                feature_row["ndvi"] = clamp(feature_row["ndvi"] + 0.08 * (1 if signal > 0.58 else -1), -0.9, 0.95)
            elif mineral_name == "nickel":
                feature_row["B8_nir"] = clamp(feature_row["B8_nir"] + 0.10, 0.05, 0.95)
                feature_row["B11_swir1"] = clamp(feature_row["B11_swir1"] + 0.08, 0.04, 0.9)
            else:
                feature_row["B4_red"] = clamp(feature_row["B4_red"] - 0.03, 0.05, 0.8)
                feature_row["ndwi"] = clamp(feature_row["ndwi"] + 0.04, -0.9, 0.85)

            score = (
                0.28 * feature_row["B2_blue"]
                + 0.22 * feature_row["B3_green"]
                + 0.26 * feature_row["B4_red"]
                + 0.35 * feature_row["B8_nir"]
                + 0.24 * feature_row["B11_swir1"]
                + 0.23 * feature_row["B12_swir2"]
                + 0.18 * max(feature_row["ndvi"], 0.0)
                + 0.14 * max(feature_row["ndwi"], 0.0)
            )

            mineral_scores.append(score)
            mineral_rows.append(
                {
                    "latitude": round(latitude, 5),
                    "longitude": round(longitude, 5),
                    "mineral": mineral_name,
                    "label": 0,
                    **feature_row,
                }
            )

        sorted_scores = sorted(mineral_scores)
        cutoff = sorted_scores[int(len(sorted_scores) * 0.58)]
        for row, score in zip(mineral_rows, mineral_scores):
            row["label"] = 1 if score >= cutoff else 0
            rows.append(row)

    with output_path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["latitude", "longitude", "mineral", "label", *FEATURE_KEYS])
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)



def train_models():
    """Train one prototype classifier per mineral; labels remain synthetic."""
    import tempfile
    import joblib
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split

    with tempfile.TemporaryDirectory() as directory:
        dataset = Path(directory) / "training.csv"
        generate_extended_dataset(dataset, rows_per_mineral=1800)
        data = pd.read_csv(dataset)
    models = {}
    validation = {}
    for mineral, rows in data.groupby("mineral"):
        X = rows[FEATURE_KEYS]
        y = rows["label"]
        train_X, test_X, train_y, test_y = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        classifier = RandomForestClassifier(
            n_estimators=160, min_samples_leaf=2,
            random_state=42, class_weight="balanced_subsample"
        )
        classifier.fit(train_X, train_y)
        validation[mineral.title()] = float(accuracy_score(test_y, classifier.predict(test_X)))
        # Refit the shipped model on all of this mineral's samples.
        classifier.fit(X, y)
        models[mineral.title()] = classifier
    bundle = {
        "format_version": 2,
        "models": models,
        "feature_names": FEATURE_KEYS,
        "training_scope": "Synthetic per-mineral demonstration labels; not geological validation.",
        "samples_per_mineral": 1800,
        "synthetic_holdout_accuracy": validation,
    }
    target = Path(__file__).resolve().parent / "expo_model.pkl"
    joblib.dump(bundle, target)
    print("Saved independent mineral models:", ", ".join(sorted(models)))
    print("Synthetic holdout accuracy (not real-world accuracy):", validation)


if __name__ == "__main__":
    train_models()
