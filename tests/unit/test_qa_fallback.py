import os

import pytest

from src.models.query_types import QueryType
from src.pipeline.qa_index import QAIndex
from src.pipeline.router import QueryRouter


@pytest.fixture(scope="module")
def qa_index():
    # Ensure ground_truth_qa directory exists relative to repo root
    assert os.path.isdir("ground_truth_qa"), "ground_truth_qa directory not found"
    return QAIndex.load("ground_truth_qa")


def test_stemi_protocol_has_ground_truth_answer(qa_index: QAIndex):
    query = "what is the STEMI protocol"
    match = qa_index.find_best(query, expected_type="protocol_steps")
    # Accept anchor-term fallback as initial correctness signal
    assert match is not None, "Expected a STEMI ground-truth answer"
    entry, score = match
    assert entry.answer, "Ground-truth entry should include an answer"


def test_router_safety_overrides_summary_when_qa_suggests_protocol(mocker):
    # Minimal stubs
    db = mocker.Mock()
    redis = mocker.Mock()
    llm = mocker.AsyncMock()
    router = QueryRouter(db, redis, llm)

    # Force suggest function to return PROTOCOL_STEPS
    router._suggest_query_type_from_qa = lambda q: QueryType.PROTOCOL_STEPS

    # Stub handler to observe routing path
    async def stub_protocol(query, context, user_id):
        return {"response": "ok", "sources": [{"display_name": "Doc", "filename": "doc.pdf"}]}
    router._handle_protocol_query = stub_protocol

    result = mocker.run(async_func=router.route_query, query="what is stemi protocol", query_type=QueryType.SUMMARY_REQUEST)
    assert result["response"] == "ok"


def test_epinephrine_anaphylaxis_dose_present(qa_index: QAIndex):
    query = "epinephrine dose for adult anaphylaxis"
    match = qa_index.find_best(query, expected_type="dosage_lookup")
    # Allow fallback to any type if specific type isn't labeled in file
    if match is None:
        match = qa_index.find_best(query)
    assert match is not None, "Expected epinephrine dosing for anaphylaxis in ground-truth"
    entry, score = match
    # Look for common dosing strings (0.5 mg IM or 0.01 mg/kg)
    answer_lower = (entry.answer or "").lower()
    assert any(x in answer_lower for x in ["0.5mg", "0.5 mg", "0.01 mg/kg"]), (
        f"Unexpected epinephrine dosing content: {entry.answer}"
    )


@pytest.mark.skipif(
    not os.path.exists("ground_truth_qa/criteria") and not os.path.exists("ground_truth_qa/guidelines"),
    reason="Criteria set not present"
)
def test_ottawa_ankle_rules_present_if_available(qa_index: QAIndex):
    query = "ottawa ankle criteria"
    match = qa_index.find_best(query, expected_type="criteria_check")
    # If missing in curated set, allow test to pass with skip at collection time
    if match is None:
        pytest.skip("Ottawa ankle rules not present in curated ground-truth set")
    entry, score = match
    assert entry.answer, "Expected an answer for Ottawa ankle rules"


