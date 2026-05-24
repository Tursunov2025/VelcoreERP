from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from database import get_db
from models import Expense, Income, User
from schemas import ExpenseCreate, FinanceRecord, FinanceSummary, IncomeCreate

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/summary", response_model=FinanceSummary)
def finance_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    total_income = sum(i.amount for i in db.query(Income).all())
    total_expenses = sum(e.amount for e in db.query(Expense).all())
    return FinanceSummary(
        total_income=total_income,
        total_expenses=total_expenses,
        net_profit=total_income - total_expenses,
    )


@router.get("/records", response_model=list[FinanceRecord])
def finance_records(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    records = []
    for income in db.query(Income).order_by(Income.created_at.desc()).all():
        records.append(
            FinanceRecord(
                id=income.id,
                title=income.title,
                amount=income.amount,
                type="income",
                category=income.source,
                created_at=income.created_at,
            )
        )
    for expense in db.query(Expense).order_by(Expense.created_at.desc()).all():
        records.append(
            FinanceRecord(
                id=expense.id,
                title=expense.title,
                amount=expense.amount,
                type="expense",
                category=expense.category,
                created_at=expense.created_at,
            )
        )
    records.sort(key=lambda r: r.created_at or "", reverse=True)
    return records


@router.post("/expenses")
def add_expense(
    data: ExpenseCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    expense = Expense(**data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.post("/income")
def add_income(
    data: IncomeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    income = Income(**data.model_dump())
    db.add(income)
    db.commit()
    db.refresh(income)
    return income
