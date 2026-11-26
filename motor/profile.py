from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
NonNegative = Annotated[float, Field(ge=0)]
Score = Annotated[int, Field(ge=0, le=100)]

WorkMode = Literal["remote", "hybrid", "onsite"]
Criterion = Literal["skills", "experience", "similarity", "role"]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        allow_inf_nan=False,
    )


class CandidateProfile(StrictModel):
    skills: list[Text] = Field(default_factory=list)
    years_experience: NonNegative | None = None
    previous_roles: list[Text] = Field(default_factory=list)


class JobPreferences(StrictModel):
    objective: Text | None = None
    target_roles: list[Text] = Field(default_factory=list)
    min_salary: Annotated[int, Field(ge=0)] | None = None
    locations: list[Text] = Field(default_factory=list)
    work_modes: list[WorkMode] = Field(default_factory=list)
    excluded_roles: list[Text] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_roles(self) -> Self:
        targets = {role.casefold() for role in self.target_roles}
        exclusions = {role.casefold() for role in self.excluded_roles}

        if targets & exclusions:
            raise ValueError("Conflicting target and excluded roles")

        return self


class ScoringThresholds(StrictModel):
    lead: Score
    review: Score

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.review >= self.lead:
            raise ValueError("Review must be below lead")
        return self


class ScoringConfig(StrictModel):
    weights: dict[Criterion, Score]
    skill_groups: dict[Text, list[Text]] = Field(default_factory=dict)
    thresholds: ScoringThresholds | None = None

    @model_validator(mode="after")
    def validate_weights(self) -> Self:
        if sum(self.weights.values()) != 100:
            raise ValueError("Weights must sum to 100")
        return self