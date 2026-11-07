from __future__ import annotations

import copy
import unittest

from scripts.style_memory import add_decision, compile_contract, load_memory, local_qa_passed, validate_memory


class StyleMemoryTests(unittest.TestCase):
    def test_project_memory_is_valid(self):
        memory = load_memory()
        self.assertGreaterEqual(len(memory["decisions"]), 10)

    def test_contract_separates_rules_bans_and_experiments(self):
        contract = compile_contract(load_memory())
        self.assertTrue(contract["acceptedRules"])
        self.assertTrue(contract["hardBans"])
        self.assertTrue(contract["disabledExperiments"])
        accepted_ids = {item["decisionId"] for item in contract["acceptedRules"]}
        banned_ids = {item["decisionId"] for item in contract["hardBans"]}
        self.assertTrue(accepted_ids.isdisjoint(banned_ids))

    def test_unconfirmed_decision_is_rejected(self):
        memory = copy.deepcopy(load_memory())
        memory["decisions"][0]["userConfirmed"] = False
        with self.assertRaisesRegex(ValueError, "potwierdzenia"):
            validate_memory(memory)

    def test_experiment_cannot_be_auto_applied(self):
        memory = copy.deepcopy(load_memory())
        experiment = next(item for item in memory["decisions"] if item["status"] == "experimental")
        experiment["autoApply"] = True
        with self.assertRaisesRegex(ValueError, "autoApply"):
            validate_memory(memory)

    def test_real_local_qa_verdict_is_accepted_but_failure_is_not(self):
        self.assertTrue(local_qa_passed({"verdict": "pass-local-gates-needs-semantic-review"}))
        self.assertFalse(local_qa_passed({"verdict": "fail-local-gates"}))

    def test_record_does_not_overwrite_existing_decision(self):
        memory = load_memory()
        with self.assertRaisesRegex(ValueError, "już istnieje"):
            add_decision(memory, copy.deepcopy(memory["decisions"][0]))


if __name__ == "__main__":
    unittest.main()
