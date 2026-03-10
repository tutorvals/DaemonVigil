"""Tests for Claude SDK response normalization."""

from src.claude import _parse_heartbeat_decision


def test_parse_heartbeat_decision_prefers_structured_output_dict():
    decision = _parse_heartbeat_decision({
        "structured_output": {"action": "stay_silent", "reasoning": "All quiet"},
        "result": "",
        "assistant_text": "",
    })

    assert decision == {"action": "stay_silent", "reasoning": "All quiet"}


def test_parse_heartbeat_decision_parses_json_result_string():
    decision = _parse_heartbeat_decision({
        "structured_output": None,
        "result": '{"action":"send_message","message":"Hello","reasoning":"Check in"}',
        "assistant_text": "",
    })

    assert decision["action"] == "send_message"
    assert decision["message"] == "Hello"
    assert decision["reasoning"] == "Check in"


def test_parse_heartbeat_decision_falls_back_to_assistant_text_json():
    decision = _parse_heartbeat_decision({
        "structured_output": None,
        "result": "",
        "assistant_text": '{"action":"stay_silent","reasoning":"Nothing to add"}',
    })

    assert decision == {"action": "stay_silent", "reasoning": "Nothing to add"}


def test_parse_heartbeat_decision_reports_empty_sdk_output():
    decision = _parse_heartbeat_decision({
        "structured_output": None,
        "result": "",
        "assistant_text": "",
    })

    assert decision["action"] == "stay_silent"
    assert "no parseable heartbeat decision" in decision["reasoning"]
    assert "result=str:0" in decision["reasoning"]
    assert "assistant_text=str:0" in decision["reasoning"]
