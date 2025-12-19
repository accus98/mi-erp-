from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import MetaData, Table, Column, Integer, String, Boolean, Float, Text, Date, DateTime, BigInteger

from alembic import context
import os
import sys

# Add Project Root
sys.path.append(os.getcwd())

# Load Application logic to populate Registry
# We import http_fastapi which calls load_modules()
try:
    import core.http_fastapi
    from core.registry import Registry
    from core.db_sync import Database
except ImportError as e:
    print(f"Could not load Nexus App: {e}")
    sys.exit(1)

# Config
config = context.config

# Set DB URL dynamically
db_url = os.getenv('DATABASE_URL_SYNC') or os.getenv('DATABASE_URL')
if not db_url:
    # Fallback to defaults
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_user = os.getenv('DB_USER', 'postgres')
    db_pass = os.getenv('DB_PASSWORD', '1234')
    db_name = os.getenv('DB_NAME', 'nexo')
    db_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -----------------------------------------------------------------
# Generate MetaData from Registry
# -----------------------------------------------------------------
def get_metadata():
    metadata = MetaData()
    
    # 1. Models
    for model_name, model_cls in Registry._models.items():
        table_name = model_cls._table
        
        columns = []
        # Standard ID
        columns.append(Column('id', Integer, primary_key=True))
        
        # Magic Fields (create_uid, etc) - Check if they exist in _fields?
        # ORM adds them to _fields.
        
        for field_name, field in model_cls._fields.items():
            if field_name == 'id': continue
            
            col_type = None
            if field._type == 'char':
                col_type = String
            elif field._type == 'text' or field._type == 'html':
                col_type = Text
            elif field._type == 'integer':
                col_type = Integer
            elif field._type == 'float':
                col_type = Float
            elif field._type == 'boolean':
                col_type = Boolean
            elif field._type == 'date':
                col_type = Date
            elif field._type == 'datetime':
                col_type = DateTime
            elif field._type == 'selection':
                col_type = String
            elif field._type == 'many2one':
                col_type = Integer
                # TODO: ForeignKey constraint
            elif field._type == 'binary':
                col_type = Text # or LargeBinary
            
            if col_type:
                # Nullability
                nullable = not field.required
                columns.append(Column(field_name, col_type, nullable=nullable))

        # Create Table
        Table(table_name, metadata, *columns)
        
        # 2. M2M Relations
        for field_name, field in model_cls._fields.items():
            if field._type == 'many2many':
                rel_table = field.relation
                col1 = field.column1
                col2 = field.column2
                
                # Auto-calculate relation table if not set
                if not rel_table:
                    comodel = Registry._models.get(field.comodel_name)
                    if comodel:
                        # Sort tables to ensure consistency? Odoo convention usually sorts?
                        # For now, simplistic approach: current_comodel_rel
                        # Odoo default: model_field_rel? No.
                        # Using: model_comodel_rel
                        t1 = model_cls._table
                        t2 = comodel._table
                        # Naming convention matches what core might expect
                        # Check core usage if possible, else best guess
                        rel_table = f"{t1}_{field_name}_rel" 
                
                if not col1: col1 = f"{model_cls._table}_id"
                if not col2: col2 = f"{field.comodel_name.replace('.', '_')}_id"

                if rel_table and rel_table not in metadata.tables:
                    Table(rel_table, metadata,
                          Column(col1, Integer, primary_key=True),
                          Column(col2, Integer, primary_key=True)
                    )

    return metadata

target_metadata = get_metadata()

# -----------------------------------------------------------------

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
    
    print(f"DEBUG IN ENV.PY: target_metadata tables: {target_metadata.tables.keys()}")

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

