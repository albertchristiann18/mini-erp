from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, QuerySet, Sum

from apps.finance.models import Expense


class ExpenseService:
    @transaction.atomic
    def create_expense(self, data: dict) -> Expense:
        """Create expense. expense_number is auto-set by PG trigger."""
        if data.get("amount", 0) <= 0:
            raise ValidationError({"amount": "Expense amount must be greater than zero."})
        expense = Expense.objects.create(**data)
        return expense

    @transaction.atomic
    def update_expense(self, expense: Expense, data: dict) -> Expense:
        """Update expense fields."""
        for field, value in data.items():
            setattr(expense, field, value)
        expense.save()
        return expense

    @transaction.atomic
    def delete_expense(self, expense: Expense) -> None:
        """Hard delete expense."""
        expense.delete()

    def get_expenses_by_period(
        self,
        company_id: str,
        start_date: date,
        end_date: date,
        category_id: str | None = None,
    ) -> QuerySet:
        """Return queryset filtered by date range and optionally category."""
        qs = Expense.objects.filter(
            company_id=company_id,
            expense_date__gte=start_date,
            expense_date__lte=end_date,
        )
        if category_id:
            qs = qs.filter(category_id=category_id)
        return qs

    def get_expense_summary_by_category(
        self,
        company_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """
        Return list of dicts: [{category_name, total_amount, count}]
        """
        return list(
            Expense.objects.filter(
                company_id=company_id,
                expense_date__gte=start_date,
                expense_date__lte=end_date,
            )
            .values("category__name")
            .annotate(
                total_amount=Sum("amount"),
                count=Count("id"),
            )
            .values("category__name", "total_amount", "count")
            .order_by("-total_amount")
        )
