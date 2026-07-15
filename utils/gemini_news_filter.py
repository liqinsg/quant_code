"""
Gemini LLM News Sentiment Filter
Low-quota design: only calls LLM if high-impact news exists
"""
import os
import sys
import json
from datetime import datetime
from google import genai

# Add project root so config/utils load correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    USE_GEMINI_AI,
    GEMINI_API_KEY,
    GEMINI_NEWS_MODEL,
    GEMINI_NEWS_FALLBACK_MODEL,
    GEMINI_NEWS_LOOKBACK_HOURS,
    GEMINI_QUOTA_SAVE_MODE,
    ENABLE_GEMINI_NEWS_FILTER
)
from utils.strategy_helpers import NewsFilter


class GeminiNewsChecker:
    def __init__(self):
        self.enabled = USE_GEMINI_AI and bool(GEMINI_API_KEY)
        self.base_filter = NewsFilter()
        self.client = None
        self.call_count = 0  # Track Gemini usage

        if self.enabled:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            print(f"[GEMINI] News filter enabled | Model: {GEMINI_MODEL} | Quota save: {GEMINI_QUOTA_SAVE_MODE}")
        else:
            print("[GEMINI] News filter disabled via config or missing API key")

    def check_pair(self, pair: str, direction: str) -> tuple[bool, str]:
        """
        Returns: (allow_trade: bool, reason: str)
        """
        # Pass through if disabled
        if not self.enabled:
            return True, "Gemini filter disabled"

        # First run lightweight existing news filter (no LLM cost)
        base_avoid, base_reason = self.base_filter.should_avoid_pair(pair)
        if base_avoid:
            return False, f"Base news filter: {base_reason}"

        # Quota save: skip LLM call if no high-impact news found
        if GEMINI_QUOTA_SAVE_MODE:
            has_high_impact = getattr(self.base_filter, "has_high_impact_news", lambda p, h: True)(pair, hours=GEMINI_NEWS_LOOKBACK_HOURS)
            if not has_high_impact:
                return True, "No high-impact news — skipped LLM call (quota saved)"

        # Only call Gemini if needed
        try:
            self.call_count += 1
            prompt = f"""
You are a cautious forex news analyst.
Check recent news for currency pair: {pair.replace('_', '/')}
Trade direction being considered: {direction}

Rules:
1. Only flag a conflict if there is HIGH-CONFIDENCE news that DIRECTLY contradicts this direction.
2. Ignore low-impact rumors, forecasts, or old news.
3. Return JSON only: {{"allow": true/false, "reason": "short reason"}}
            """

            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                generation_config={"response_mime_type": "application/json"}
            )

            result = json.loads(response.text)
            allow = result.get("allow", True)
            reason = result.get("reason", "No conflict found")
            return allow, f"Gemini: {reason}"

        except Exception as e:
            print(f"[GEMINI] API error: {str(e)[:100]} — allowing trade")
            return True, f"Gemini unavailable: {str(e)[:80]}"


# Singleton instance
gemini_checker = GeminiNewsChecker()


# ==========================================
# 🧪 TEST MAIN FUNCTION — RUN DIRECTLY
# ==========================================
def main():
    print("=" * 60)
    print("🧪 TESTING GEMINI NEWS FILTER MODULE")
    print("=" * 60)
    print(f"Config Status:")
    print(f"  ENABLE_GEMINI_NEWS_FILTER = {ENABLE_GEMINI_NEWS_FILTER}")
    print(f"  GEMINI_QUOTA_SAVE_MODE    = {GEMINI_QUOTA_SAVE_MODE}")
    print(f"  API Key present           = {bool(GEMINI_API_KEY)}")
    print()

    # Test cases covering typical scenarios
    test_cases = [
        ("USD_JPY", "BUY"),
        ("EUR_JPY", "SELL"),
        ("GBP_JPY", "BUY"),
        ("AUD_JPY", "SELL"),
    ]

    print(f"Running {len(test_cases)} test pairs...\n")

    for idx, (pair, direction) in enumerate(test_cases, 1):
        print(f"[{idx}] Checking {direction} {pair}...")
        allow, reason = gemini_checker.check_pair(pair, direction)
        status = "✅ ALLOW" if allow else "❌ BLOCK"
        print(f"       → {status}: {reason}\n")

    print("=" * 60)
    print(f"📊 Test Complete — Total Gemini API calls made: {gemini_checker.call_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()