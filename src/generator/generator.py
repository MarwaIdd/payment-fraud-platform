"""
generator.py - Générateur de transactions de paiement synthétiques (version 1)

Chaque transaction = un achat d'un client chez un marchand.
"""
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np

SEED = 42 #Pour avoir les memes resultats dans chaque lancement du code
random.seed(SEED)
rng = np.random.default_rng(SEED)

COUNTRY_CURRENCY = {"MA": "MAD", "FR": "EUR", "ES": "EUR", "US": "USD", "AE": "AED"}
COUNTRIES = list(COUNTRY_CURRENCY)

# catégorie : (montant médian, dispersion, canal)
CATEGORIES = {
    "GROCERY": (150, 0.6, "POS"),
    "FUEL": (300, 0.4, "POS"),
    "RESTAURANT": (120, 0.6, "POS"),
    "ECOMMERCE": (250, 0.9, "ECOM"),
    "ELECTRONICS": (1500, 0.8, "ECOM"),
    "ATM": (1000, 0.5, "ATM"),
}


def make_customers(n):
    customers = []
    for i in range(n):
        customers.append({
            "customer_id": f"C{i:06d}",
            "country": random.choices(COUNTRIES, weights=[70, 10, 5, 10, 5])[0],
            "devices": [f"D_{i:06d}_{k}" for k in range(random.randint(1, 2))],
            "spend_factor": float(rng.lognormal(0, 0.4)),
            "categories": random.sample(list(CATEGORIES), 3),
        })
    return customers


def make_merchants(n):
    cats = list(CATEGORIES)
    merchants_by_cat = {c: [] for c in cats}
    for i in range(n):
        cat = cats[i % len(cats)]
        merchants_by_cat[cat].append({"merchant_id": f"M{i:05d}", "category": cat})
    return merchants_by_cat

# pour assembler une transaction avec les 12 champs, dans un dictionnaire Python
def build_tx(customer, merchant, amount, country, channel, device_id, status, when):
    return {
        "schema_version": 1,
        "transaction_id": str(uuid.uuid4()),
        "event_time": when.isoformat(),
        "customer_id": customer["customer_id"],
        "merchant_id": merchant["merchant_id"],
        "merchant_category": merchant["category"],
        "amount": round(float(amount), 2),
        "currency": COUNTRY_CURRENCY[country],
        "country": country,
        "channel": channel,
        "device_id": device_id,
        "status": status,
    }


def pick_device(customer, channel):
    return random.choice(customer["devices"]) if channel == "ECOM" else None


def foreign_country(customer):
    return random.choice([c for c in COUNTRIES if c != customer["country"]])


def normal_transaction(customer, mbc, when):
    cat = random.choice(customer["categories"])
    median, sigma, channel = CATEGORIES[cat]
    amount = rng.lognormal(np.log(median * customer["spend_factor"]), sigma)
    country = customer["country"] if random.random() < 0.95 else random.choice(COUNTRIES)
    status = "DECLINED" if random.random() < 0.04 else "APPROVED"
    merchant = random.choice(mbc[cat])
    tx = build_tx(customer, merchant, amount, country, channel,
                  pick_device(customer, channel), status, when)
    return [(tx, None)]


def card_testing(customer, mbc, when):
    merchant = random.choice(mbc["ECOMMERCE"])
    device = f"D_{random.randint(200, 999999):06d}_0"
    country = foreign_country(customer)
    events = []
    for k in range(random.randint(4, 6)):
        status = "DECLINED" if random.random() < 0.6 else "APPROVED"
        tx = build_tx(customer, merchant, rng.uniform(1, 5), country, "ECOM",
                      device, status, when + timedelta(seconds=8 * k))
        events.append((tx, "card_testing"))
    return events


def account_takeover(customer, mbc, when):
    cat = random.choice(["ELECTRONICS", "ECOMMERCE"])
    median = CATEGORIES[cat][0]
    amount = median * customer["spend_factor"] * random.uniform(4, 8)
    merchant = random.choice(mbc[cat])
    tx = build_tx(customer, merchant, amount, foreign_country(customer), "ECOM",
                  f"D_{random.randint(200, 999999):06d}_0", "APPROVED", when)
    return [(tx, "account_takeover")]


def abnormal_amount(customer, mbc, when):
    cat = random.choice(customer["categories"])
    median, _, channel = CATEGORIES[cat]
    amount = median * customer["spend_factor"] * random.uniform(8, 15)
    merchant = random.choice(mbc[cat])
    tx = build_tx(customer, merchant, amount, customer["country"], channel,
                  pick_device(customer, channel), "APPROVED", when)
    return [(tx, "abnormal_amount")]


def generate(n_events=30, fraud_rate=0.15):
    customers = make_customers(200)
    mbc = make_merchants(60)
    now = datetime.now(timezone.utc)
    events = []
    while len(events) < n_events:
        customer = random.choice(customers)
        now += timedelta(seconds=random.uniform(0.2, 3))
        if random.random() < fraud_rate:
            scenario = random.choice([card_testing, account_takeover, abnormal_amount])
            events.extend(scenario(customer, mbc, now))
        else:
            events.extend(normal_transaction(customer, mbc, now))
    return events


if __name__ == "__main__":
    for tx, fraud_type in generate():
        flag = f"   <-- FRAUDE ({fraud_type})" if fraud_type else ""
        print(json.dumps(tx, ensure_ascii=False) + flag)