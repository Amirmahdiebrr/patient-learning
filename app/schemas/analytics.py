from pydantic import BaseModel


class LessonCompletionResponse(BaseModel):
    total_started: int
    total_completed: int
    completion_rate_percent: float


class QuizSuccessResponse(BaseModel):
    total_attempts: int
    correct_attempts: int
    success_rate_percent: float


class MostViewedLessonResponse(BaseModel):
    lesson_id: str
    title: str
    view_count: int


class StageDistributionResponse(BaseModel):
    stage: str
    count: int


class DashboardSummaryResponse(BaseModel):
    today_new_patients: int
    discharged_last_30_days: int
    lesson_completion: LessonCompletionResponse
    quiz_success: QuizSuccessResponse
    average_completion_time_hours: float | None
    most_viewed_lessons: list[MostViewedLessonResponse]
    stage_distribution: list[StageDistributionResponse]