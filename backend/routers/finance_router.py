from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from auth.deps import require_admin, require_permission
from database import get_db
from models import (
    Expense,
    Income,
    User,
    FinanceAccount,
    FinanceCategory,
    FinanceCounterparty,
    FinanceTransaction,
    FinanceObligation,
    FinanceObligationPayment,
)
from schemas import (
    ExpenseCreate,
    FinanceRecord,
    FinanceSummary,
    IncomeCreate,
    FinanceAccountResponse,
    FinanceCategoryResponse,
    FinanceCounterpartyResponse,
    FinanceTransactionResponse,
    FinanceObligationResponse,
    FinanceProfessionalDashboard,
    FinanceCounterpartyCreate,
    FinanceTransactionCreate,
    FinanceTransferCreate,
    FinanceObligationCreate,
    FinanceObligationPaymentCreate,
    FinanceObligationPaymentResponse,
)

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/summary", response_model=FinanceSummary)
def finance_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("finance")),
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
    _: User = Depends(require_permission("finance")),
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


# ===========================================================================
# Professional Finance API
# ===========================================================================

@router.get("/pro/dashboard", response_model=FinanceProfessionalDashboard)
def professional_finance_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("finance")),
):
    transactions = (
        db.query(FinanceTransaction)
        .filter(FinanceTransaction.status == "posted")
        .all()
    )

    total_income = sum(
        float(row.amount_uzs or 0)
        for row in transactions
        if row.transaction_type == "income"
    )
    total_expense = sum(
        float(row.amount_uzs or 0)
        for row in transactions
        if row.transaction_type == "expense"
    )

    accounts = (
        db.query(FinanceAccount)
        .filter(FinanceAccount.is_active.is_(True))
        .all()
    )

    cash_balance = sum(
        float(row.current_balance or 0)
        for row in accounts
        if row.account_type == "cash" and row.currency_code == "UZS"
    )
    bank_balance = sum(
        float(row.current_balance or 0)
        for row in accounts
        if row.account_type == "bank" and row.currency_code == "UZS"
    )

    obligations = db.query(FinanceObligation).all()

    receivable = sum(
        max(float(row.original_amount or 0) - float(row.paid_amount or 0), 0)
        for row in obligations
        if row.obligation_type == "receivable"
        and row.status not in ("paid", "cancelled")
        and row.currency_code == "UZS"
    )

    payable = sum(
        max(float(row.original_amount or 0) - float(row.paid_amount or 0), 0)
        for row in obligations
        if row.obligation_type == "payable"
        and row.status not in ("paid", "cancelled")
        and row.currency_code == "UZS"
    )

    return FinanceProfessionalDashboard(
        total_income_uzs=total_income,
        total_expense_uzs=total_expense,
        net_profit_uzs=total_income - total_expense,
        cash_balance_uzs=cash_balance,
        bank_balance_uzs=bank_balance,
        receivable_uzs=receivable,
        payable_uzs=payable,
        transactions_count=len(transactions),
    )


@router.get("/pro/accounts", response_model=list[FinanceAccountResponse])
def professional_finance_accounts(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("finance")),
):
    return (
        db.query(FinanceAccount)
        .order_by(FinanceAccount.account_type, FinanceAccount.id)
        .all()
    )


@router.get("/pro/categories", response_model=list[FinanceCategoryResponse])
def professional_finance_categories(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("finance")),
):
    return (
        db.query(FinanceCategory)
        .order_by(FinanceCategory.category_type, FinanceCategory.id)
        .all()
    )


@router.get("/pro/counterparties", response_model=list[FinanceCounterpartyResponse])
def professional_finance_counterparties(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("finance")),
):
    return (
        db.query(FinanceCounterparty)
        .order_by(FinanceCounterparty.name)
        .all()
    )


@router.get("/pro/transactions", response_model=list[FinanceTransactionResponse])
def professional_finance_transactions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("finance")),
):
    return (
        db.query(FinanceTransaction)
        .order_by(
            FinanceTransaction.transaction_date.desc(),
            FinanceTransaction.id.desc(),
        )
        .limit(500)
        .all()
    )


@router.get("/pro/obligations", response_model=list[FinanceObligationResponse])
def professional_finance_obligations(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("finance")),
):
    return (
        db.query(FinanceObligation)
        .order_by(FinanceObligation.id.desc())
        .limit(500)
        .all()
    )


@router.post("/pro/counterparties", response_model=FinanceCounterpartyResponse)
def create_finance_counterparty(
    data: FinanceCounterpartyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("finance")),
):
    row = FinanceCounterparty(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/pro/transactions", response_model=FinanceTransactionResponse)
def create_finance_transaction(
    data: FinanceTransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("finance")),
):
    if data.transaction_type not in ("income", "expense"):
        raise HTTPException(status_code=400, detail="Invalid transaction_type")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")

    account = (
        db.query(FinanceAccount)
        .filter(FinanceAccount.id == data.account_id)
        .with_for_update()
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Finance account not found")

    if not account.is_active:
        raise HTTPException(status_code=400, detail="Finance account is inactive")

    rate = float(data.exchange_rate or 1)
    if rate <= 0:
        raise HTTPException(status_code=400, detail="Exchange rate must be greater than zero")

    amount_uzs = float(data.amount) * rate

    prefix = "FIN-IN" if data.transaction_type == "income" else "FIN-OUT"
    document_no = f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    row = FinanceTransaction(
        document_no=document_no,
        transaction_type=data.transaction_type,
        account_id=data.account_id,
        category_id=data.category_id,
        counterparty_id=data.counterparty_id,
        amount=data.amount,
        currency_code=data.currency_code,
        exchange_rate=data.exchange_rate,
        amount_uzs=amount_uzs,
        description=data.description,
        project_id=data.project_id,
        status="posted",
        transaction_date=data.transaction_date or datetime.utcnow(),
        created_by=user.username,
    )

    current = float(account.current_balance or 0)
    if data.transaction_type == "income":
        account.current_balance = current + float(data.amount)
    else:
        if current < float(data.amount):
            raise HTTPException(status_code=400, detail="Insufficient account balance")
        account.current_balance = current - float(data.amount)

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/pro/transfers")
def create_finance_transfer(
    data: FinanceTransferCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("finance")),
):
    if data.from_account_id == data.to_account_id:
        raise HTTPException(status_code=400, detail="Source and destination accounts must differ")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")

    accounts = (
        db.query(FinanceAccount)
        .filter(FinanceAccount.id.in_([data.from_account_id, data.to_account_id]))
        .with_for_update()
        .all()
    )

    by_id = {a.id: a for a in accounts}
    source = by_id.get(data.from_account_id)
    target = by_id.get(data.to_account_id)

    if not source or not target:
        raise HTTPException(status_code=404, detail="Finance account not found")

    if source.currency_code != target.currency_code:
        raise HTTPException(status_code=400, detail="Cross-currency transfer is not supported yet")

    total_debit = float(data.amount) + float(data.commission_amount or 0)
    if float(source.current_balance or 0) < total_debit:
        raise HTTPException(status_code=400, detail="Insufficient account balance")

    source.current_balance = float(source.current_balance or 0) - total_debit
    target.current_balance = float(target.current_balance or 0) + float(data.amount)

    document_no = f"FIN-TR-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    from models import FinanceTransfer

    row = FinanceTransfer(
        document_no=document_no,
        from_account_id=data.from_account_id,
        to_account_id=data.to_account_id,
        amount=data.amount,
        commission_amount=data.commission_amount,
        description=data.description,
        transfer_date=data.transfer_date or datetime.utcnow(),
        created_by=user.username,
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "id": row.id,
        "document_no": row.document_no,
        "status": "posted",
    }


@router.post("/pro/obligations", response_model=FinanceObligationResponse)
def create_finance_obligation(
    data: FinanceObligationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("finance")),
):
    if data.obligation_type not in ("receivable", "payable"):
        raise HTTPException(status_code=400, detail="Invalid obligation_type")

    if data.original_amount <= 0:
        raise HTTPException(status_code=400, detail="Original amount must be greater than zero")

    if data.paid_amount < 0 or data.paid_amount > data.original_amount:
        raise HTTPException(status_code=400, detail="Invalid paid_amount")

    status_value = "paid" if data.paid_amount >= data.original_amount else "open"

    row = FinanceObligation(
        obligation_type=data.obligation_type,
        counterparty_id=data.counterparty_id,
        project_id=data.project_id,
        document_no=data.document_no,
        original_amount=data.original_amount,
        paid_amount=data.paid_amount,
        currency_code=data.currency_code,
        due_date=data.due_date,
        status=status_value,
        description=data.description,
    )

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/pro/obligations/{obligation_id}/payments",
    response_model=FinanceObligationPaymentResponse,
)
def create_finance_obligation_payment(
    obligation_id: int,
    data: FinanceObligationPaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("finance")),
):
    obligation = (
        db.query(FinanceObligation)
        .filter(FinanceObligation.id == obligation_id)
        .with_for_update()
        .first()
    )

    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    if data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Payment amount must be greater than zero",
        )

    remaining = float(obligation.original_amount) - float(obligation.paid_amount)

    if remaining <= 0:
        raise HTTPException(
            status_code=400,
            detail="Obligation is already fully paid",
        )

    if data.amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Payment exceeds remaining amount: {remaining:.2f}",
        )

    account = None
    transaction_id = None

    if data.account_id is not None:
        account = (
            db.query(FinanceAccount)
            .filter(FinanceAccount.id == data.account_id)
            .with_for_update()
            .first()
        )

        if not account:
            raise HTTPException(status_code=404, detail="Finance account not found")

        if not account.is_active:
            raise HTTPException(status_code=400, detail="Finance account is inactive")

        if account.currency_code != obligation.currency_code:
            raise HTTPException(
                status_code=400,
                detail="Account currency does not match obligation currency",
            )

        # Debitor to‘lovi = kassaga/bankka kirim.
        # Kreditor to‘lovi = kassadan/bankdan chiqim.
        if obligation.obligation_type == "receivable":
            account.current_balance = (
                float(account.current_balance or 0) + float(data.amount)
            )
        elif obligation.obligation_type == "payable":
            current_balance = float(account.current_balance or 0)

            if current_balance < float(data.amount):
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient account balance",
                )

            account.current_balance = current_balance - float(data.amount)

    payment = FinanceObligationPayment(
        obligation_id=obligation.id,
        account_id=data.account_id,
        transaction_id=transaction_id,
        amount=data.amount,
        currency_code=obligation.currency_code,
        payment_date=data.payment_date or datetime.utcnow(),
        payment_method=data.payment_method,
        document_no=data.document_no,
        description=data.description,
        created_by=user.username,
    )

    new_paid = float(obligation.paid_amount or 0) + float(data.amount)
    obligation.paid_amount = new_paid

    if new_paid >= float(obligation.original_amount):
        obligation.status = "paid"
    elif new_paid > 0:
        obligation.status = "partial"
    else:
        obligation.status = "open"

    obligation.updated_at = datetime.utcnow()

    db.add(payment)
    db.commit()
    db.refresh(payment)

    return payment


@router.get(
    "/pro/obligations/{obligation_id}/payments",
    response_model=list[FinanceObligationPaymentResponse],
)
def list_finance_obligation_payments(
    obligation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("finance")),
):
    obligation = (
        db.query(FinanceObligation)
        .filter(FinanceObligation.id == obligation_id)
        .first()
    )

    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    return (
        db.query(FinanceObligationPayment)
        .filter(FinanceObligationPayment.obligation_id == obligation_id)
        .order_by(
            FinanceObligationPayment.payment_date.desc(),
            FinanceObligationPayment.id.desc(),
        )
        .all()
    )


@router.get("/pro/receivables/summary")
def finance_receivables_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("finance")),
):
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    tomorrow_start = today_start + timedelta(days=1)

    rows = (
        db.query(FinanceObligation)
        .filter(FinanceObligation.obligation_type == "receivable")
        .all()
    )

    total_open = 0.0
    overdue_total = 0.0
    due_today_total = 0.0

    aging = {
        "current": 0.0,
        "days_0_30": 0.0,
        "days_31_60": 0.0,
        "days_61_90": 0.0,
        "days_90_plus": 0.0,
    }

    by_counterparty = {}

    for row in rows:
        original = float(row.original_amount or 0)
        paid = float(row.paid_amount or 0)
        remaining = max(original - paid, 0.0)

        if remaining <= 0:
            continue

        total_open += remaining
        by_counterparty[row.counterparty_id] = (
            by_counterparty.get(row.counterparty_id, 0.0) + remaining
        )

        due = row.due_date

        if due is None:
            aging["current"] += remaining
            continue

        if today_start <= due < tomorrow_start:
            due_today_total += remaining

        if due >= today_start:
            aging["current"] += remaining
            continue

        overdue_total += remaining
        overdue_days = (today_start - due).days

        if overdue_days <= 30:
            aging["days_0_30"] += remaining
        elif overdue_days <= 60:
            aging["days_31_60"] += remaining
        elif overdue_days <= 90:
            aging["days_61_90"] += remaining
        else:
            aging["days_90_plus"] += remaining

    counterparties = {
        row.id: row.name
        for row in db.query(FinanceCounterparty).all()
    }

    top_debtors = [
        {
            "counterparty_id": cp_id,
            "counterparty_name": counterparties.get(cp_id, "—"),
            "remaining_amount": amount,
        }
        for cp_id, amount in sorted(
            by_counterparty.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:10]
    ]

    return {
        "total_open": round(total_open, 2),
        "overdue_total": round(overdue_total, 2),
        "due_today_total": round(due_today_total, 2),
        "debtor_count": len(by_counterparty),
        "aging": {k: round(v, 2) for k, v in aging.items()},
        "top_debtors": top_debtors,
    }
