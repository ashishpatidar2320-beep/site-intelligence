import unittest

from planning import estimate_project, format_inr, rendering_prompt


class EstimateProjectTests(unittest.TestCase):
    def test_project_totals_follow_completion(self):
        half = estimate_project("Residential", 2000, "Tier 2", 50)
        complete = estimate_project("Residential", 2000, "Tier 2", 100)
        self.assertEqual(half["project_budget_inr"], 4_200_000)
        self.assertEqual(half["capex_incurred_inr"], 2_100_000)
        self.assertEqual(half["budget_remaining_inr"], 2_100_000)
        self.assertEqual(half["asset_value_inr"], complete["asset_value_inr"] // 2)

    def test_material_quantities_are_area_based(self):
        estimate = estimate_project("Residential", 1000, "Tier 2", 0)
        self.assertEqual(estimate["steel_kg"], 3800)
        self.assertEqual(estimate["cement_bags"], 400)
        self.assertEqual(estimate["capex_incurred_inr"], 0)

    def test_tier_changes_cost_and_market_benchmark(self):
        tier_one = estimate_project("Commercial", 1000, "Tier 1", 100)
        tier_three = estimate_project("Commercial", 1000, "Tier 3", 100)
        self.assertGreater(tier_one["project_budget_inr"], tier_three["project_budget_inr"])
        self.assertGreater(tier_one["asset_value_on_completion_inr"], tier_three["asset_value_on_completion_inr"])

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            estimate_project("Unknown", 1000, "Tier 2", 50)
        with self.assertRaises(ValueError):
            estimate_project("Residential", 1000, "Tier 4", 50)

    def test_currency_format_and_rendering_prompt(self):
        self.assertEqual(format_inr(12_500_000), "₹ 1.25 Cr")
        self.assertEqual(format_inr(750_000), "₹ 7.50 L")
        prompt = rendering_prompt("Residential", 2000, "Tier 2")
        self.assertIn("2,000 square feet", prompt)
        self.assertIn("tier 2", prompt.lower())


if __name__ == "__main__":
    unittest.main()
