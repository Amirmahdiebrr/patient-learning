"""merge procedure_intro and other branch

Revision ID: 61de18543736
Revises: 9a1c5e7f2b4d, 9d4f2e7a1c3b
Create Date: 2026-08-21 02:41:22.093686

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61de18543736'
down_revision: Union[str, Sequence[str], None] = ('9a1c5e7f2b4d', '9d4f2e7a1c3b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
