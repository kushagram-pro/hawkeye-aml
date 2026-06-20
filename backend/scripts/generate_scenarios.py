"""Generates the 3 synthetic scenario datasets used by the demo.

Each scenario mixes a hand-seeded suspicious pattern (guaranteed to trip the
rule pre-filters in agent2_detection.py) with randomized ordinary "noise"
transactions among an unrelated pool of accounts, so detection isn't trivial.

Run: python scripts/generate_scenarios.py
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "scenarios"
NOISE_ACCOUNTS = [f"ACC{i:03d}" for i in range(1, 16)]


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def generate_noise(count: int, seed: int, start: datetime, span_days: int) -> list[dict]:
    rng = random.Random(seed)
    noise = []
    for _ in range(count):
        sender, receiver = rng.sample(NOISE_ACCOUNTS, 2)
        amount = rng.choice([12000, 18500, 25000, 31000, 42000, 60000, 75000, 88000, 110000, 5400])
        offset = timedelta(
            days=rng.randint(0, span_days), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
        )
        noise.append(
            {
                "from_account": sender,
                "to_account": receiver,
                "amount": amount,
                "timestamp": _iso(start + offset),
                "currency": "INR",
            }
        )
    return noise


def build_structuring() -> dict:
    base = datetime(2026, 6, 5, 9, 0, 0)
    senders = [f"ACC10{i}" for i in range(1, 7)]
    amounts = [42000, 38000, 45000, 41000, 47000, 39000]
    pattern = [
        {
            "from_account": sender,
            "to_account": "ACC301",
            "amount": amount,
            "timestamp": _iso(base + timedelta(hours=6 * i)),
            "currency": "INR",
        }
        for i, (sender, amount) in enumerate(zip(senders, amounts))
    ]
    pattern.append(
        {
            "from_account": "ACC301",
            "to_account": "ACC302",
            "amount": sum(amounts),
            "timestamp": _iso(base + timedelta(hours=46)),
            "currency": "INR",
        }
    )
    noise = generate_noise(23, seed=1, start=datetime(2026, 6, 1), span_days=14)
    transactions = pattern + noise
    transactions.sort(key=lambda t: t["timestamp"])
    return {
        "scenario_id": "structuring",
        "seeded_pattern": {"type": "structuring", "accounts": ["ACC301"] + senders},
        "transactions": transactions,
    }


def build_layering() -> dict:
    base = datetime(2026, 6, 3, 8, 0, 0)
    chain_accounts = [f"ACC40{i}" for i in range(1, 7)]
    amounts = [120000, 114000, 108000, 102000, 96000]
    hour_offsets = [0, 12, 25, 38, 51]
    pattern = [
        {
            "from_account": chain_accounts[i],
            "to_account": chain_accounts[i + 1],
            "amount": amounts[i],
            "timestamp": _iso(base + timedelta(hours=hour_offsets[i])),
            "currency": "INR",
        }
        for i in range(5)
    ]
    noise = generate_noise(23, seed=2, start=datetime(2026, 6, 1), span_days=14)
    transactions = pattern + noise
    transactions.sort(key=lambda t: t["timestamp"])
    return {
        "scenario_id": "layering",
        "seeded_pattern": {"type": "layering", "accounts": chain_accounts},
        "transactions": transactions,
    }


def build_mule_network() -> dict:
    base = datetime(2026, 6, 8, 9, 0, 0)
    mules = [f"ACC60{i}" for i in range(1, 7)]
    cashouts = [f"ACC70{i}" for i in range(1, 7)]
    in_amounts = [90000, 85000, 95000, 88000, 92000, 87000]

    pattern = []
    for i, (mule, amount) in enumerate(zip(mules, in_amounts)):
        pattern.append(
            {
                "from_account": "ACC501",
                "to_account": mule,
                "amount": amount,
                "timestamp": _iso(base + timedelta(minutes=10 * i)),
                "currency": "INR",
            }
        )
    for i, (mule, cashout, amount) in enumerate(zip(mules, cashouts, in_amounts)):
        pattern.append(
            {
                "from_account": mule,
                "to_account": cashout,
                "amount": round(amount * 0.9),
                "timestamp": _iso(base + timedelta(hours=5, minutes=10 * i)),
                "currency": "INR",
            }
        )
    noise = generate_noise(18, seed=3, start=datetime(2026, 6, 1), span_days=14)
    transactions = pattern + noise
    transactions.sort(key=lambda t: t["timestamp"])
    return {
        "scenario_id": "mule_network",
        "seeded_pattern": {"type": "mule_network", "accounts": ["ACC501"] + mules},
        "transactions": transactions,
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = {
        "structuring": build_structuring(),
        "layering": build_layering(),
        "mule_network": build_mule_network(),
    }
    for scenario_id, data in scenarios.items():
        path = OUT_DIR / f"{scenario_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"wrote {path} ({len(data['transactions'])} transactions)")


if __name__ == "__main__":
    main()
