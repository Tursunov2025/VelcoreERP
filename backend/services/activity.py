from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models import OperatorActivity, Order, User

ONLINE_THRESHOLD_MINUTES = 5
ACTIVITY_TOUCH_SECONDS = 60


def touch_activity(db: Session, user: User):
    activity = (
        db.query(OperatorActivity)
        .filter(OperatorActivity.user_id == user.id)
        .first()
    )
    now = datetime.utcnow()
    if (
        activity
        and activity.last_activity
        and (now - activity.last_activity).total_seconds() < ACTIVITY_TOUCH_SECONDS
    ):
        return

    active_count = (
        db.query(Order)
        .filter(
            Order.status == user.department,
            Order.in_warehouse.is_(False),
            Order.deleted_at.is_(None),
        )
        .count()
        if user.role != "admin" and user.department != "Admin"
        else db.query(Order)
        .filter(Order.in_warehouse.is_(False), Order.deleted_at.is_(None))
        .count()
    )

    if not activity:
        activity = OperatorActivity(
            user_id=user.id,
            username=user.username,
            department=user.department or "Admin",
        )
        db.add(activity)

    activity.username = user.username
    activity.department = user.department or user.role
    activity.is_online = True
    activity.last_activity = datetime.utcnow()
    activity.active_orders_count = active_count
    db.commit()


def record_login(db: Session, user: User):
    activity = (
        db.query(OperatorActivity)
        .filter(OperatorActivity.user_id == user.id)
        .first()
    )
    now = datetime.utcnow()
    if not activity:
        activity = OperatorActivity(
            user_id=user.id,
            username=user.username,
            department=user.department or "Admin",
            login_at=now,
            last_activity=now,
        )
        db.add(activity)
    else:
        activity.login_at = now
        activity.last_activity = now
        activity.is_online = True
    db.commit()


def get_online_operators(db: Session):
    return get_online_operators_detailed(db)


def get_online_operators_detailed(db: Session):
    threshold = datetime.utcnow() - timedelta(minutes=ONLINE_THRESHOLD_MINUTES)
    rows = db.query(OperatorActivity).all()
    result = []
    for row in rows:
        online = row.last_activity and row.last_activity >= threshold
        result.append(
            {
                "username": row.username,
                "department": row.department,
                "is_online": online,
                "last_activity": row.last_activity,
                "login_at": row.login_at,
                "active_orders_count": row.active_orders_count,
            }
        )
    return sorted(result, key=lambda x: (not x["is_online"], x["username"]))
