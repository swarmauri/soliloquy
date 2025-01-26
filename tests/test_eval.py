# tests/test_eval_ops.py

import os
import json
import tempfile
import shutil
import pytest
from unittest import mock
from soliloquy import eval_ops

# Helper function to create a temporary JSON file with test results
def create_temp_test_json(summary, tests):
    content = {
        "summary": summary,
        "tests": tests
    }
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "test_results.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f)
    return temp_dir, file_path

@pytest.fixture
def temp_test_json():
    """
    Pytest fixture to create and clean up a temporary test_results.json file.
    """
    summary = {
        "total": 10,
        "passed": 8,
        "failed": 1,
        "skipped": 1
    }
    tests = [
        {"outcome": "passed", "keywords": ["unit", "featureA"]},
        {"outcome": "passed", "keywords": ["unit", "featureB"]},
        {"outcome": "passed", "keywords": ["integration", "featureA"]},
        {"outcome": "passed", "keywords": ["integration", "featureB"]},
        {"outcome": "passed", "keywords": ["integration", "featureC"]},
        {"outcome": "passed", "keywords": ["performance", "featureA"]},
        {"outcome": "passed", "keywords": ["performance", "featureB"]},
        {"outcome": "failed", "keywords": ["unit", "featureC"]},
        {"outcome": "skipped", "keywords": ["test_dependency"]},
        {"outcome": "passed", "keywords": ["test_dependency"]},
    ]
    temp_dir, file_path = create_temp_test_json(summary, tests)
    yield file_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_test_json_no_summary():
    """
    Pytest fixture to create a temporary test_results.json file without summary.
    """
    content = {
        "tests": []
    }
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "test_results.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f)
    yield file_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_test_json_invalid_json():
    """
    Pytest fixture to create a temporary invalid JSON file.
    """
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "test_results.json")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("This is not valid JSON.")
    yield file_path
    shutil.rmtree(temp_dir)

def test_evaluate_threshold():
    # Test various threshold conditions
    assert eval_ops.evaluate_threshold(80, "gt:75") == True
    assert eval_ops.evaluate_threshold(75, "gt:75") == False
    assert eval_ops.evaluate_threshold(75, "ge:75") == True
    assert eval_ops.evaluate_threshold(50, "lt:60") == True
    assert eval_ops.evaluate_threshold(60, "lt:60") == False
    assert eval_ops.evaluate_threshold(60, "le:60") == True
    assert eval_ops.evaluate_threshold(100, "eq:100") == True
    assert eval_ops.evaluate_threshold(99.99, "eq:100") == False

def test_evaluate_threshold_invalid_format():
    with pytest.raises(ValueError) as exc_info:
        eval_ops.evaluate_threshold(80, "greater_than:75")
    assert "Invalid threshold format" in str(exc_info.value)

def test_evaluate_threshold_invalid_operator():
    with pytest.raises(ValueError) as exc_info:
        eval_ops.evaluate_threshold(80, "invalid:75")
    assert "Invalid operator" in str(exc_info.value)

def test_analyze_test_file_success(temp_test_json, capsys):
    # Run the analysis
    eval_ops.analyze_test_file(
        file_path=temp_test_json,
        required_passed="gt:75",
        required_skipped="lt:20"
    )
    
    captured = capsys.readouterr()
    # Check summary table
    assert "Test Results Summary" in captured.out
    assert "Passed" in captured.out
    assert "8" in captured.out
    assert "80.00" in captured.out  # 8/10 passed
    
    # Check tag-based results
    assert "Tag-Based Results" in captured.out
    assert "unit" in captured.out
    assert "featureA" in captured.out
    assert "featureB" in captured.out
    assert "featureC" in captured.out
    assert "integration" in captured.out
    assert "performance" in captured.out
    
    # Since thresholds are met, there should be a success message
    assert "Test analysis completed successfully." in captured.out

def test_analyze_test_file_fail_passed_threshold(temp_test_json, capsys):
    # Modify the summary to have lower passed percentage
    summary = {
        "total": 10,
        "passed": 6,
        "failed": 2,
        "skipped": 2
    }
    tests = [
        {"outcome": "passed", "keywords": ["unit", "featureA"]},
        {"outcome": "passed", "keywords": ["unit", "featureB"]},
        {"outcome": "passed", "keywords": ["integration", "featureA"]},
        {"outcome": "passed", "keywords": ["integration", "featureB"]},
        {"outcome": "passed", "keywords": ["integration", "featureC"]},
        {"outcome": "passed", "keywords": ["performance", "featureA"]},
        {"outcome": "failed", "keywords": ["unit", "featureC"]},
        {"outcome": "failed", "keywords": ["integration", "featureD"]},
        {"outcome": "skipped", "keywords": ["test_dependency"]},
        {"outcome": "passed", "keywords": ["test_dependency"]},
    ]
    temp_dir, file_path = create_temp_test_json(summary, tests)
    with pytest.raises(SystemExit) as exc_info:
        eval_ops.analyze_test_file(
            file_path=file_path,
            required_passed="gt:75",
            required_skipped="lt:20"
        )
    captured = capsys.readouterr()
    assert "WARNING: Passed percentage (60.00%) does not meet the condition 'gt:75'!" in captured.out
    assert exc_info.value.code == 1
    shutil.rmtree(temp_dir)

def test_analyze_test_file_fail_skipped_threshold(temp_test_json, capsys):
    # Modify the summary to have higher skipped percentage
    summary = {
        "total": 10,
        "passed": 8,
        "failed": 1,
        "skipped": 1
    }
    tests = [
        {"outcome": "passed", "keywords": ["unit", "featureA"]},
        {"outcome": "passed", "keywords": ["unit", "featureB"]},
        {"outcome": "passed", "keywords": ["integration", "featureA"]},
        {"outcome": "passed", "keywords": ["integration", "featureB"]},
        {"outcome": "passed", "keywords": ["integration", "featureC"]},
        {"outcome": "passed", "keywords": ["performance", "featureA"]},
        {"outcome": "passed", "keywords": ["performance", "featureB"]},
        {"outcome": "failed", "keywords": ["unit", "featureC"]},
        {"outcome": "skipped", "keywords": ["test_dependency"]},
        {"outcome": "skipped", "keywords": ["test_dependency"]},
    ]
    temp_dir, file_path = create_temp_test_json(summary, tests)
    with pytest.raises(SystemExit) as exc_info:
        eval_ops.analyze_test_file(
            file_path=file_path,
            required_passed="gt:75",
            required_skipped="lt:20"
        )
    captured = capsys.readouterr()
    assert "WARNING: Skipped percentage (20.00%) does not meet the condition 'lt:20'!" in captured.out
    assert exc_info.value.code == 1
    shutil.rmtree(temp_dir)

def test_analyze_test_file_fail_both_thresholds(temp_test_json, capsys):
    # Modify the summary to fail both thresholds
    summary = {
        "total": 10,
        "passed": 6,
        "failed": 2,
        "skipped": 2
    }
    tests = [
        {"outcome": "passed", "keywords": ["unit", "featureA"]},
        {"outcome": "passed", "keywords": ["unit", "featureB"]},
        {"outcome": "passed", "keywords": ["integration", "featureA"]},
        {"outcome": "passed", "keywords": ["integration", "featureB"]},
        {"outcome": "passed", "keywords": ["integration", "featureC"]},
        {"outcome": "passed", "keywords": ["performance", "featureA"]},
        {"outcome": "failed", "keywords": ["unit", "featureC"]},
        {"outcome": "failed", "keywords": ["integration", "featureD"]},
        {"outcome": "skipped", "keywords": ["test_dependency"]},
        {"outcome": "skipped", "keywords": ["test_dependency"]},
    ]
    temp_dir, file_path = create_temp_test_json(summary, tests)
    with pytest.raises(SystemExit) as exc_info:
        eval_ops.analyze_test_file(
            file_path=file_path,
            required_passed="gt:75",
            required_skipped="lt:20"
        )
    captured = capsys.readouterr()
    assert "WARNING: Passed percentage (60.00%) does not meet the condition 'gt:75'!" in captured.out
    assert "WARNING: Skipped percentage (20.00%) does not meet the condition 'lt:20'!" in captured.out
    assert exc_info.value.code == 1
    shutil.rmtree(temp_dir)

def test_analyze_test_file_no_thresholds(temp_test_json, capsys):
    # Run the analysis without specifying thresholds
    eval_ops.analyze_test_file(
        file_path=temp_test_json,
        required_passed=None,
        required_skipped=None
    )
    captured = capsys.readouterr()
    # Check that no warnings about thresholds are present
    assert "WARNING" not in captured.out
    # Check that the success message is present
    assert "Test analysis completed successfully." in captured.out

def test_analyze_test_file_invalid_file(temp_test_json_invalid_json, capsys):
    with pytest.raises(SystemExit) as exc_info:
        eval_ops.analyze_test_file(
            file_path=temp_test_json_invalid_json,
            required_passed="gt:75",
            required_skipped="lt:20"
        )
    captured = capsys.readouterr()
    assert "Error: Could not decode JSON" in captured.out
    assert exc_info.value.code == 1

def test_analyze_test_file_missing_summary(temp_test_json_no_summary, capsys):
    with pytest.raises(SystemExit) as exc_info:
        eval_ops.analyze_test_file(
            file_path=temp_test_json_no_summary,
            required_passed="gt:75",
            required_skipped="lt:20"
        )
    captured = capsys.readouterr()
    assert "No test data or summary found in the provided file." in captured.out
    assert exc_info.value.code == 1

def test_analyze_test_file_tags_exclusion(temp_test_json, capsys):
    # Ensure that unwanted tags are excluded
    summary = {
        "total": 5,
        "passed": 4,
        "failed": 1,
        "skipped": 0
    }
    tests = [
        {"outcome": "passed", "keywords": ["tests", "featureA"]},
        {"outcome": "passed", "keywords": ["test_featureB"]},
        {"outcome": "passed", "keywords": ["featureC_test.py"]},
        {"outcome": "passed", "keywords": ["featureD"]},
        {"outcome": "failed", "keywords": ["featureE"]},
    ]
    temp_dir, file_path = create_temp_test_json(summary, tests)
    eval_ops.analyze_test_file(
        file_path=file_path,
        required_passed="gt:75",
        required_skipped="lt:20"
    )
    captured = capsys.readouterr()
    # Only "featureA", "featureD", "featureE" should be included
    assert "featureA" in captured.out
    assert "featureD" in captured.out
    assert "featureE" in captured.out
    # "tests", "test_featureB", "featureC_test.py" should be excluded
    assert "tests" not in captured.out
    assert "test_featureB" not in captured.out
    assert "featureC_test.py" not in captured.out
    shutil.rmtree(temp_dir)

def test_analyze_test_file_empty_tags(temp_test_json, capsys):
    # Tests with empty tags
    summary = {
        "total": 3,
        "passed": 2,
        "failed": 1,
        "skipped": 0
    }
    tests = [
        {"outcome": "passed", "keywords": [""]},
        {"outcome": "passed", "keywords": ["featureA"]},
        {"outcome": "failed", "keywords": ["featureB"]},
    ]
    temp_dir, file_path = create_temp_test_json(summary, tests)
    eval_ops.analyze_test_file(
        file_path=file_path,
        required_passed="gt:50",
        required_skipped="lt:50"
    )
    captured = capsys.readouterr()
    # Only "featureA" and "featureB" should be included
    assert "featureA" in captured.out
    assert "featureB" in captured.out
    assert "" not in captured.out  # Empty tag should be excluded
    shutil.rmtree(temp_dir)

def test_analyze_test_file_no_tags(temp_test_json, capsys):
    # Tests with no tags
    summary = {
        "total": 2,
        "passed": 2,
        "failed": 0,
        "skipped": 0
    }
    tests = [
        {"outcome": "passed", "keywords": []},
        {"outcome": "passed", "keywords": []},
    ]
    temp_dir, file_path = create_temp_test_json(summary, tests)
    eval_ops.analyze_test_file(
        file_path=file_path,
        required_passed="gt:75",
        required_skipped="lt:20"
    )
    captured = capsys.readouterr()
    # No tags should be printed
    assert "Tag-Based Results" in captured.out
    assert "No Git dependencies found." not in captured.out  # Just ensure no errors
    # Since there are no tags, nothing related to tags should appear
    assert "Feature" not in captured.out
    shutil.rmtree(temp_dir)
