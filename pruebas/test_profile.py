import pytest
from pydantic import ValidationError

from motor.profile import (
    CandidateProfile,
    JobPreferences,
    ScoringConfig,
)


def test_unknown_experience():
    profile = CandidateProfile(years_experience=None)
    assert profile.years_experience is None


def test_negative_experience():
    with pytest.raises(ValidationError):
        CandidateProfile(years_experience=-1)


def test_independent_preferences():
    engineer = JobPreferences(
        work_modes=["remote", "hybrid"]
    )
    lawyer = JobPreferences(
        work_modes=["onsite", "hybrid"]
    )

    assert "onsite" not in engineer.work_modes
    assert "onsite" in lawyer.work_modes


@pytest.mark.parametrize("weights", [
    {"skills": 45, "experience": 55},
    {"skills": 20, "experience": 80},
])
def test_custom_weights(weights):
    config = ScoringConfig(weights=weights)
    assert config.weights == weights


@pytest.mark.parametrize("weights", [
    {"skills": 45, "experience": 25},
    {"skills": -10, "experience": 110},
])
def test_invalid_weights(weights):
    with pytest.raises(ValidationError):
        ScoringConfig(weights=weights)

@pytest.mark.parametrize("weights", [
    {"skills": 100},
    {"skills": 0, "experience": 100},
    {"skills": 45, "experience": 25,
     "similarity": 20, "role": 10},
])
def test_weight_boundaries(weights):
    assert ScoringConfig(weights=weights).weights == weights


@pytest.mark.parametrize("weights", [
    {},
    {"skills": 120},
    {"skills": "45", "experience": 55},
    {"skills": True, "experience": 99},
    {"skills": 45.0, "experience": 55},
    {"skills": None, "experience": 100},
    {"unknown": 100},
])
def test_invalid_weight_types(weights):
    with pytest.raises(ValidationError):
        ScoringConfig(weights=weights)


@pytest.mark.parametrize("years", [0, 4.5, 30])
def test_valid_experience(years):
    assert CandidateProfile(years_experience=years).years_experience == years


@pytest.mark.parametrize("years", ["4", True, float("inf"), float("nan")])
def test_invalid_experience_types(years):
    with pytest.raises(ValidationError):
        CandidateProfile(years_experience=years)


@pytest.mark.parametrize("salary", [-1, "60000", True])
def test_invalid_salary(salary):
    with pytest.raises(ValidationError):
        JobPreferences(min_salary=salary)


def test_invalid_modality():
    with pytest.raises(ValidationError):
        JobPreferences(work_modes=["unknown"])


def test_conflicting_roles():
    with pytest.raises(ValidationError):
        JobPreferences(
            target_roles=["lawyer"],
            excluded_roles=["lawyer"],
        )


@pytest.mark.parametrize("thresholds", [
    {"lead": 35, "review": 60},
    {"lead": 60, "review": 60},
    {"lead": 110, "review": 35},
    {"lead": 60, "review": -1},
])
def test_invalid_thresholds(thresholds):
    with pytest.raises(ValidationError):
        ScoringConfig(
            weights={"skills": 100},
            thresholds=thresholds,
        )


def test_unknown_field():
    with pytest.raises(ValidationError):
        JobPreferences(unexpected_field=True)