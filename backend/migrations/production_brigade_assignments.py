from sqlalchemy import inspect, text


def upgrade(engine):
    inspector = inspect(engine)
    columns = {
        col["name"]
        for col in inspector.get_columns("mes_job_route_steps")
    }

    with engine.begin() as conn:
        if "brigade_id" not in columns:
            conn.execute(text("""
                ALTER TABLE mes_job_route_steps
                ADD COLUMN brigade_id INTEGER
                REFERENCES mes_terminal_brigades(id)
            """))

        if "accepted_by_user_id" not in columns:
            conn.execute(text("""
                ALTER TABLE mes_job_route_steps
                ADD COLUMN accepted_by_user_id INTEGER
                REFERENCES users(id)
            """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS
            ix_mes_job_route_steps_brigade_id
            ON mes_job_route_steps (brigade_id)
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS
            ix_mes_job_route_steps_accepted_by_user_id
            ON mes_job_route_steps (accepted_by_user_id)
        """))

    print("PRODUCTION BRIGADE ASSIGNMENTS MIGRATION COMPLETED")
