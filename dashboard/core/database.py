from pathlib import Path
import os

import pandas as pd
import streamlit as st

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@st.cache_resource
def get_engine():
    required = [
        "PGHOST", "PGPORT", "PGDATABASE",
        "PGUSER", "PGPASSWORD"
    ]

    values = {key: os.getenv(key) for key in required}
    missing = [key for key, value in values.items() if not value]

    if missing:
        raise RuntimeError(
            f"Missing PostgreSQL settings: {missing}"
        )

    pg_user = values["PGUSER"]
    pg_password = values["PGPASSWORD"]
    pg_host = values["PGHOST"]
    pg_port_value = values["PGPORT"]
    pg_database = values["PGDATABASE"]

    if not all(
        [pg_user, pg_password, pg_host, pg_port_value, pg_database]
    ):
        raise RuntimeError(
            f"Missing PostgreSQL settings: {missing}"
        )

    if pg_port_value is None:
        raise RuntimeError("Missing PostgreSQL settings: PGPORT")

    pg_port = int(pg_port_value)

    url = URL.create(
        "postgresql+psycopg",
        username=pg_user,
        password=pg_password,
        host=pg_host,
        port=pg_port,
        database=pg_database,
    )

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800
    )


@st.cache_data(ttl=300, show_spinner=False)
def query_data(sql: str) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql_query(text(sql), conn)


@st.cache_data(show_spinner=False)
def load_report(relative_path: str) -> pd.DataFrame:
    path = ROOT / "data" / "reports" / relative_path

    if not path.is_file():
        raise FileNotFoundError(
            f"Report not found: {path}"
        )

    return pd.read_csv(path)


def refresh_data():
    query_data.clear()
    load_report.clear()