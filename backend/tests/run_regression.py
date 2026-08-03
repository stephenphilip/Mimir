import sys
import os
# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath("."))

import pytest

# Ensure data directory is redirected for regression run
import tempfile
if "MIMIR_DATA_DIR" not in os.environ:
    os.environ["MIMIR_DATA_DIR"] = tempfile.gettempdir()

class ResultCollector:
    def __init__(self):
        self.results = {}

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            nodeid = report.nodeid
            test_name = nodeid.split("::")[-1]
            self.results[test_name] = {
                "outcome": report.outcome,
                "duration": report.duration,
                "message": str(report.longrepr) if report.failed else ""
            }
        elif report.when == "setup" and report.skipped:
            nodeid = report.nodeid
            test_name = nodeid.split("::")[-1]
            self.results[test_name] = {
                "outcome": "skipped",
                "duration": 0,
                "message": ""
            }

def main():
    print("=" * 80)
    print("                    MIMIR MEMORY SYSTEM REGRESSION RUN                   ")
    print("=" * 80)
    print("Running pytest suite...")
    
    collector = ResultCollector()
    # Run pytest programmatically on tests/test_memory_regression.py
    pytest.main(["-v", "tests/test_memory_regression.py"], plugins=[collector])
    
    bug_mapping = {
        "Bug 1: Token counting not populated on message insert": [
            "test_new_message_has_nonzero_token_count",
            "test_all_message_insertion_paths_set_token_count"
        ],
        "Bug 2: Pinning never triggers automatically": [
            "test_correction_message_gets_auto_pinned",
            "test_non_correction_message_not_pinned",
            "test_pinned_message_survives_compaction"
        ],
        "Bug 3: Context assembly drops/misselects prior message content": [
            "test_full_history_present_in_assembled_payload",
            "test_model_does_not_contradict_prior_stated_fact"
        ],
        "Bug 4: Fabrication of details never present in conversation": [
            "test_no_fabricated_entities_in_response",
            "test_ambiguous_question_does_not_hallucinate"
        ],
        "Bug 5: Prompt template scaffolding leaks into stored/displayed content": [
            "test_no_template_markers_in_saved_content",
            "test_saved_content_matches_actual_latest_user_message"
        ],
        "Bug 6: False refusals on benign requests": [
            "test_benign_creative_continuation_not_refused",
            "test_refusal_only_on_actually_flagged_content"
        ],
        "Bug 7: Compaction/summary text or narration leaking into live chat responses": [
            "test_no_narration_leak_in_response",
            "test_duplicate_consecutive_messages_answered_correctly",
            "test_variant_after_duplicate_messages_answered_correctly"
        ],
        "Bug 8: Identical/cached-looking responses to different turns": [
            "test_different_turns_produce_non_identical_responses"
        ],
        "Bug 9: Multiple message-insertion code paths behave inconsistently": [
            "test_single_canonical_insertion_path"
        ]
    }
    
    print("\n" + "=" * 80)
    print("                                REGRESSION SUMMARY                               ")
    print("=" * 80)
    print(f"{'BUG / SCENARIO':<70} | {'STATUS':<10}")
    print("-" * 83)
    
    failures = []
    
    for bug, test_names in bug_mapping.items():
        bug_status = "PASSED"
        bug_results = []
        
        for name in test_names:
            res = collector.results.get(name)
            if res:
                bug_results.append(res)
                if res["outcome"] == "failed":
                    bug_status = "FAILED"
            else:
                # If test wasn't collected or failed setup
                bug_results.append({"outcome": "missing", "message": "Test did not execute"})
                bug_status = "FAILED"
                
        # Status coloring indicator
        status_str = f"[\033[92mPASSED\033[0m]" if bug_status == "PASSED" else f"[\033[91mFAILED\033[0m]"
        # Fallback without color if console doesn't support it
        if sys.platform == "win32":
            status_str = f"[{bug_status}]"
            
        print(f"{bug:<70} | {status_str:<10}")
        
        # Collect failure details
        for name in test_names:
            res = collector.results.get(name)
            if res and res["outcome"] == "failed":
                failures.append((bug, name, res["message"]))
                
    print("=" * 80)
    
    if failures:
        print("\nFAILURE DETAILS:")
        print("=" * 80)
        for bug, test_name, msg in failures:
            print(f"[{bug}] -> {test_name}:")
            print("-" * 80)
            # Indent lines of error messages
            for line in msg.splitlines()[-10:]: # last 10 lines of trackback
                print(f"  {line}")
            print("=" * 80)
    else:
        print("\nALL REGRESSION TESTS PASSED SUCCESSFULLY!")
        
if __name__ == "__main__":
    main()
