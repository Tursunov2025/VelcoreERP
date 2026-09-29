from sqlalchemy import inspect


def upgrade_yigish_lines(engine):
    from models import MesYigishLine

    inspector = inspect(engine)

    if "mes_yigish_lines" not in inspector.get_table_names():
        MesYigishLine.__table__.create(bind=engine, checkfirst=True)
        print("Created table: mes_yigish_lines")
    else:
        print("Table already exists: mes_yigish_lines")
