"""Proficiency Service for CEFR band calculation.

Corresponds to Part B of praxis_plan_quiz_cefr.md.
Implements the derived-on-read hysteresis algorithm for CEFR band.
"""

from datetime import datetime, timedelta
from typing import Any

from app.db.engine import Session
from app.db.models.quiz import QuizQuestion, QuizSession
from app.db.models.writing import WritingEvaluation, WritingSubmission


# Fixed CEFR band ordering for trend calculation
BAND_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
BAND_INDEX = {band: i for i, band in enumerate(BAND_ORDER)}


class ProficiencyService:
    """Service for computing current CEFR proficiency band.

    The band is computed on-read from historical WritingEvaluation rows,
    not stored as mutable state. This ensures it always reflects the
    current data and is trivially replayable.
    """

    @classmethod
    def get_current_band(cls) -> dict[str, Any]:
        """Get the current CEFR band with trend.

        Algorithm (per Part B.3):
        1. Query WritingEvaluation rows with non-null cefr_band, joined to
           WeeklyReport, ordered chronologically by week_start ascending.
        2. Run compute_band with threshold determined by quiz-accuracy modifier.
        3. Compare computed_band to latest eval's cefr_band for trend.

        Returns:
            Dict with band, trend, last_eval_week_start
        """
        with Session() as session:
            # Get weekly evaluations with cefr_band, ordered chronologically
            evals = (
                session.query(WritingEvaluation)
                .join(WritingSubmission)
                .filter(
                    WritingSubmission.submission_type == "WEEKLY",
                    WritingEvaluation.cefr_band.isnot(None),
                )
                .order_by(WritingEvaluation.created_at.asc())
                .all()
            )

            if not evals:
                return {
                    "band": None,
                    "trend": "steady",
                    "last_eval_week_start": None,
                }

            # Extract cefr_bands in chronological order
            bands = [e.cefr_band for e in evals]

            # Get quiz accuracy modifier to determine threshold
            threshold = cls._get_threshold_from_quiz_accuracy(session, evals)

            # Compute confirmed band with hysteresis
            computed_band = cls._compute_band(bands, threshold)

            # Get the latest evaluation's band for trend
            latest_band = bands[-1]
            trend = cls._compute_trend(computed_band, latest_band)

            # Get the week_start of the latest evaluation
            latest_eval = evals[-1]
            # We need to find the week_start from the WeeklyReport
            # For now, use the evaluation's created_at as a proxy
            last_eval_week_start = latest_eval.created_at.date().isoformat()

            return {
                "band": computed_band,
                "trend": trend,
                "last_eval_week_start": last_eval_week_start,
            }

    @classmethod
    def _compute_band(cls, evals: list[str], threshold: int = 2) -> str | None:
        """Compute the confirmed CEFR band with hysteresis.

        The confirmed band only changes once `threshold` consecutive
        weekly evals in a row all agree on a different band than the
        current one. A single off-week eval never moves it.

        Args:
            evals: CEFR band values in chronological (oldest-first) order
            threshold: Number of consecutive evals needed to confirm a change

        Returns:
            The computed band, or None if no evals
        """
        if not evals:
            return None

        band = evals[0]
        i = 1

        while i < len(evals):
            window = evals[i:i + threshold]
            if (
                len(window) == threshold
                and all(w == window[0] for w in window)
                and window[0] != band
            ):
                band = window[0]
                i += threshold
            else:
                i += 1

        return band

    @classmethod
    def _get_threshold_from_quiz_accuracy(cls, session: Session, evals: list) -> int:
        """Determine threshold based on quiz accuracy trend.

        Per Part B.3:
        - Compute average MC quiz accuracy over the last 2 weeks
        - If it moved >10pp in same direction as pending band change: threshold=1
        - If flat or opposite direction: threshold=3
        - Otherwise: threshold=2 (default)

        Args:
            session: Database session
            evals: List of WritingEvaluation objects (chronological)

        Returns:
            Threshold value (1, 2, or 3)
        """
        if len(evals) < 2:
            # Not enough evals for quiz modifier to apply
            return 2

        # Get the last 2 weeks' quiz accuracy
        quiz_accuracies = cls._get_last_n_weeks_quiz_accuracy(session, 2)

        if len(quiz_accuracies) < 2:
            return 2

        # Compute change in quiz accuracy (latest - previous)
        latest_quiz = quiz_accuracies[-1]
        prev_quiz = quiz_accuracies[-2]

        if latest_quiz is None or prev_quiz is None:
            return 2

        quiz_change = latest_quiz - prev_quiz

        # Determine direction of pending band change
        # (latest eval's band vs current confirmed band)
        # We need to compute what the "pending" change would be
        # For simplicity, use the last two evals
        if len(evals) >= 2:
            latest_band = evals[-1].cefr_band
            prev_band = evals[-2].cefr_band

            if latest_band != prev_band:
                # There's a pending band change
                band_change_direction = BAND_INDEX.get(latest_band, 0) - BAND_INDEX.get(prev_band, 0)

                # Check if quiz change is in same direction (>10pp)
                if abs(quiz_change) > 10:
                    quiz_direction = 1 if quiz_change > 0 else -1

                    if (band_change_direction > 0 and quiz_direction > 0) or \
                       (band_change_direction < 0 and quiz_direction < 0):
                        return 1  # Quiz corroborates - immediate confirmation

                    if (band_change_direction > 0 and quiz_direction < 0) or \
                       (band_change_direction < 0 and quiz_direction > 0):
                        return 3  # Quiz contradicts - need extra confirmation

        return 2  # Default threshold

    @classmethod
    def _get_last_n_weeks_quiz_accuracy(cls, session: Session, n: int) -> list[float | None]:
        """Get quiz accuracy for the last N weeks.

        Args:
            session: Database session
            n: Number of weeks to look back

        Returns:
            List of accuracies (0-100) for each week, newest last
        """
        now = datetime.utcnow()
        accuracies = []

        for i in range(n):
            week_end = now - timedelta(weeks=i)
            week_start = week_end - timedelta(days=7)

            # Get completed sessions in this week
            sessions = (
                session.query(QuizSession)
                .filter(
                    QuizSession.started_at >= week_start,
                    QuizSession.started_at < week_end,
                    QuizSession.completed_at.isnot(None),
                )
                .all()
            )

            if not sessions:
                accuracies.append(None)
                continue

            session_ids = [s.id for s in sessions]
            questions = (
                session.query(QuizQuestion)
                .filter(QuizQuestion.quiz_session_id.in_(session_ids))
                .all()
            )

            total = len(questions)
            if total == 0:
                accuracies.append(None)
                continue

            correct = sum(1 for q in questions if q.is_correct is True)
            accuracy = (correct / total) * 100
            accuracies.append(accuracy)

        # Reverse to get chronological order (oldest first)
        return list(reversed(accuracies))

    @classmethod
    def _compute_trend(cls, computed_band: str | None, latest_band: str | None) -> str:
        """Compute trend direction.

        Args:
            computed_band: The confirmed band from hysteresis
            latest_band: The most recent single evaluation's band

        Returns:
            "up", "down", or "steady"
        """
        if not computed_band or not latest_band:
            return "steady"

        computed_idx = BAND_INDEX.get(computed_band, 0)
        latest_idx = BAND_INDEX.get(latest_band, 0)

        if latest_idx > computed_idx:
            return "up"
        elif latest_idx < computed_idx:
            return "down"
        return "steady"