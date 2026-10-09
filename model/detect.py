import os
import pickle
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "model", "fake_review_model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "model", "vectorizer.pkl")

_model = None
_vectorizer = None

SUPERLATIVES = [
    "best ever", "life changing", "life-changing", "perfect in every way",
    "no flaws", "no complaints whatsoever", "buy it now", "buy now",
    "highly highly", "amazing amazing", "perfect perfect", "10/10",
    "5 stars", "five stars", "100 stars", "game changer", "must buy",
    "everyone needs", "everyone should", "changed my life", "blown away",
    "outstanding", "incredible", "unbelievable results",
]
INCENTIVE_PHRASES = [
    "free in exchange", "received this product for free", "in exchange for my honest review",
    "sponsored", "affiliate",
]


def _load():
    global _model, _vectorizer
    if _model is None or _vectorizer is None:
        with open(MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
        with open(VECTORIZER_PATH, "rb") as f:
            _vectorizer = pickle.load(f)
    return _model, _vectorizer


def _rule_signals(text):
    lower = text.lower()
    signals = []

    exclam_count = text.count("!")
    if exclam_count >= 4:
        signals.append(f"Excessive exclamation marks ({exclam_count})")

    caps_words = re.findall(r"\b[A-Z]{3,}\b", text)
    if len(caps_words) >= 2:
        signals.append(f"Unusual amount of ALL-CAPS words ({len(caps_words)})")

    found_superlatives = [s for s in SUPERLATIVES if s in lower]
    if found_superlatives:
        shown = ", ".join(found_superlatives[:4])
        signals.append(f"Generic superlative phrasing: {shown}")

    found_incentive = [s for s in INCENTIVE_PHRASES if s in lower]
    if found_incentive:
        signals.append("Mentions receiving the product free / incentivized review")

    word_count = len(text.split())
    if word_count < 12:
        signals.append("Review is unusually short for a detailed opinion")

    repeated = re.findall(r"\b(\w+)\b(?:\s+\1\b)+", lower)
    if repeated:
        signals.append(f"Repeated word pattern detected ('{repeated[0]}')")

    return signals, word_count, exclam_count


def analyze_review(text):
    """
    Returns a dict:
        prediction: 'fake' | 'genuine'
        confidence: float 0-100
        suspicious_keywords: list[str]  (human-readable rule signals)
        word_count: int
    """
    text = (text or "").strip()
    if not text:
        return {
            "prediction": "genuine",
            "confidence": 0.0,
            "suspicious_keywords": [],
            "word_count": 0,
        }

    model, vectorizer = _load()
    vec = vectorizer.transform([text])
    proba = model.predict_proba(vec)[0]  # [P(genuine), P(fake)]
    fake_proba = float(proba[1])

    signals, word_count, exclam_count = _rule_signals(text)

    rule_nudge = min(len(signals) * 0.03, 0.15)
    if signals:
        fake_proba = min(1.0, fake_proba + rule_nudge) if fake_proba > 0.4 else fake_proba

    prediction = "fake" if fake_proba >= 0.5 else "genuine"
    confidence = fake_proba if prediction == "fake" else (1 - fake_proba)
    confidence = round(confidence * 100, 1)

    return {
        "prediction": prediction,
        "confidence": confidence,
        "suspicious_keywords": signals,
        "word_count": word_count,
    }
