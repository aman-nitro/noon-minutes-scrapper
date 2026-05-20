"""inventory making integer filed

Revision ID: 4116533afa71
Revises: da5f7ab2989d
Create Date: 2026-05-19 12:16:36.240283

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4116533afa71'
down_revision: Union[str, Sequence[str], None] = 'da5f7ab2989d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.alter_column(
        'noon_product',
        'inventory',
        existing_type=sa.TEXT(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using='inventory::integer'
    )


def downgrade() -> None:
    op.alter_column(
        'noon_product',
        'inventory',
        existing_type=sa.Integer(),
        type_=sa.TEXT(),
        existing_nullable=False,
        postgresql_using='inventory::text'
    )