from sqlalchemy import inspect


def upgrade_job_yigish_lines(engine):
    from models import MesJobYigishLine

    inspector = inspect(engine)

    if "mes_job_yigish_lines" not in inspector.get_table_names():
        MesJobYigishLine.__table__.create(
            bind=engine,
            checkfirst=True,
        )
        print("Created table: mes_job_yigish_lines")
    else:
        print("Table already exists: mes_job_yigish_lines")
