from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Load .env before importing settings (pydantic-settings reads env on class instantiation)
from dotenv import load_dotenv
load_dotenv()

from app.database.base import Base
from app.core.settings import settings

# Import every model explicitly so SQLAlchemy registers them with Base.metadata
# Missing any model here means that table won't appear in autogenerate migrations
from app.models.users import User  # noqa: F401
from app.models.products import Product  # noqa: F401
from app.models.orders import Order  # noqa: F401
from app.models.order_items import OrderLineItem  # noqa: F401
from app.models.payments import Payment  # noqa: F401
from app.models.shipments import Shipment  # noqa: F401
from app.models.event_logs import EventLog  # noqa: F401

config = context.config

# Override sqlalchemy.url from Settings (built from individual env vars in .env)
# This means alembic.ini never needs to contain real credentials
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
