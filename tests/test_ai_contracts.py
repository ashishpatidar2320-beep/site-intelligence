import unittest

from construction_ai import demo_crack_report, demo_safety_report, answer_construction_question


class DemoContractTests(unittest.TestCase):
    def test_safety_demo_has_required_report_fields(self):
        report = demo_safety_report()
        self.assertIn(report["safety_score"], range(101))
        self.assertIn("overall_status", report)
        self.assertEqual(
            set(report["ppe_detection"]),
            {"helmets", "high_visibility_vests", "steel_toe_boots", "safety_harnesses"},
        )
        self.assertTrue(report["hazards"])
        self.assertEqual(report["analysis_mode"], "demo")

    def test_crack_demo_has_required_report_fields(self):
        report = demo_crack_report()
        self.assertIn("defect_type", report)
        self.assertIn("estimated_width_mm", report)
        self.assertTrue(report["root_causes"])
        self.assertTrue(report["recommended_repairs"])
        self.assertIn("urgency", report)
        self.assertEqual(report["analysis_mode"], "demo")

    def test_chat_fallback_includes_selected_weather_protocol(self):
        answer = answer_construction_question("How should I cure concrete?", [], "Extreme Heat", "")
        self.assertIn("Demo assistant", answer)
        self.assertIn("hydration", answer.lower())


if __name__ == "__main__":
    unittest.main()
