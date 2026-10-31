from alembic import context
from sqlalchemy import create_engine

from atlas.db import Base

url = context.config.get_main_option("sqlalchemy.url")
engine = create_engine(url)

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True,
                      include_object=lambda obj, name, kind, reflected, compare_to: not (kind == "table" and name.startswith("doc_chunks")))
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
