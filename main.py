from engine.risk_engine_v2 import PrivacyRiskEngineV2

def main():
    print("🔐 Starting Privacy Risk Checker...\n")

    engine = PrivacyRiskEngineV2()

    # Sample user input (you can change later)
    user_data = {
        "user_info": {
            "name": "Pranav"
        },
        "responses": {
            "AS01": True,
            "AS02": False,
            "AS03": 1,
            "DE01": True,
            "DE02": False,
            "NS01": True,
            "DS02": 2,
            "BH01": False
        }
    }

    # Run full system
    result = engine.full_assess(
        user_data,
        scenario_id="student",
        simulate_events=True
    )

    print("===== FINAL RESULT =====")
    print("Score:", result["score_result"]["final_score"])
    print("Risk Level:", result["score_result"]["risk_level"]["label"])

    print("\n--- History Comparison ---")
    print(result["history_comparison"])

    print("\n--- Trend Analysis ---")
    print(result["trend"])

    print("\n--- Live Simulation ---")
    print(result["live_simulation"])

    print("\n--- Recommendations ---")
    for rec in result["recommendations"]:
        if isinstance(rec, dict):
            print("-", rec.get("title", "Recommendation"))
        else:
            print("-", rec)


if __name__ == "__main__":
    main()