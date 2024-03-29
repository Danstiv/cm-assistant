"""empty message

Revision ID: babaa85cf958
Revises: 52088bf4ff2d
Create Date: 2022-09-22 01:43:16.433853

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'babaa85cf958'
down_revision = '52088bf4ff2d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('window',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chat_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('window_class_crc32', sa.LargeBinary(length=4), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=True),
    sa.Column('current_tab_index', sa.Integer(), nullable=True),
    sa.Column('input_required', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('check_box_button',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('callback_data', sa.LargeBinary(length=64), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('callback_name', sa.String(), nullable=True),
    sa.Column('text', sa.String(), nullable=True),
    sa.Column('is_checked', sa.Boolean(), nullable=False),
    sa.Column('is_unchecked_prefix', sa.String(), nullable=False),
    sa.Column('is_checked_prefix', sa.String(), nullable=False),
    sa.Column('arg', sa.String(), nullable=True),
    sa.Column('window_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['window_id'], ['window.id'], name='fk_window_id'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('callback_data')
    )
    op.create_table('group_add_staff_tab',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('index_in_window', sa.Integer(), nullable=True),
    sa.Column('text', sa.String(), nullable=True),
    sa.Column('current_input_field_index', sa.Integer(), nullable=True),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('staff_type', sa.Enum('USER', 'MODERATOR', 'ADMIN', name='userrole'), nullable=False),
    sa.Column('window_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['window_id'], ['window.id'], name='fk_window_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('group_stats_date_time_range_selection_tab',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('index_in_window', sa.Integer(), nullable=True),
    sa.Column('text', sa.String(), nullable=True),
    sa.Column('current_input_field_index', sa.Integer(), nullable=True),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('start_date_time', sa.DateTime(), nullable=False),
    sa.Column('end_date_time', sa.DateTime(), nullable=False),
    sa.Column('screen', sa.Enum('START_DATE_TIME', 'END_DATE_TIME', name='groupstatsdatetimerangeselectionscreen'), nullable=True),
    sa.Column('window_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['window_id'], ['window.id'], name='fk_window_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('group_stats_tab',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('index_in_window', sa.Integer(), nullable=True),
    sa.Column('text', sa.String(), nullable=True),
    sa.Column('current_input_field_index', sa.Integer(), nullable=True),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('start_date_time', sa.DateTime(), nullable=False),
    sa.Column('end_date_time', sa.DateTime(), nullable=False),
    sa.Column('window_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['window_id'], ['window.id'], name='fk_window_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('group_tab',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('index_in_window', sa.Integer(), nullable=True),
    sa.Column('text', sa.String(), nullable=True),
    sa.Column('current_input_field_index', sa.Integer(), nullable=True),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('window_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['window_id'], ['window.id'], name='fk_window_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pyrogram_button',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(), nullable=True),
    sa.Column('callback_data', sa.LargeBinary(length=64), nullable=True),
    sa.Column('url', sa.String(), nullable=True),
    sa.Column('web_app_url', sa.String(), nullable=True),
    sa.Column('login_url', sa.String(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('switch_inline_query', sa.String(), nullable=True),
    sa.Column('switch_inline_query_current_chat', sa.String(), nullable=True),
    sa.Column('right_button', sa.Boolean(), nullable=True),
    sa.Column('tab_index', sa.Integer(), nullable=True),
    sa.Column('window_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['window_id'], ['window.id'], name='fk_window_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tab',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('index_in_window', sa.Integer(), nullable=True),
    sa.Column('text', sa.String(), nullable=True),
    sa.Column('current_input_field_index', sa.Integer(), nullable=True),
    sa.Column('window_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['window_id'], ['window.id'], name='fk_window_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('text',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tab_index', sa.Integer(), nullable=True),
    sa.Column('tab_id', sa.Integer(), nullable=True),
    sa.Column('header', sa.String(), nullable=True),
    sa.Column('body', sa.String(), nullable=True),
    sa.Column('input_field_text', sa.String(), nullable=True),
    sa.Column('window_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['window_id'], ['window.id'], name='fk_window_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_table('simple_check_box_button')
    op.drop_table('add_staff_member_form_state')
    op.drop_table('group_user_button')
    with op.batch_alter_table('simple_button', schema=None) as batch_op:
        batch_op.add_column(sa.Column('name', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_window_id', 'window', ['window_id'], ['id'])
        batch_op.drop_column('creation_date')
        batch_op.drop_column('user_id')
        batch_op.drop_column('answer')

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('simple_button', schema=None) as batch_op:
        batch_op.add_column(sa.Column('answer', sa.BOOLEAN(), nullable=True))
        batch_op.add_column(sa.Column('user_id', sa.INTEGER(), nullable=False))
        batch_op.add_column(sa.Column('creation_date', sa.DATETIME(), nullable=False))
        batch_op.drop_constraint('fk_window_id', type_='foreignkey')
        batch_op.drop_column('window_id')
        batch_op.drop_column('name')

    op.create_table('group_user_button',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('creation_date', sa.DATETIME(), nullable=False),
    sa.Column('callback_data', sa.BLOB(), nullable=False),
    sa.Column('answer', sa.BOOLEAN(), nullable=True),
    sa.Column('callback_name', sa.VARCHAR(), nullable=True),
    sa.Column('group_id', sa.INTEGER(), nullable=False),
    sa.Column('member_id', sa.INTEGER(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('callback_data')
    )
    op.create_table('add_staff_member_form_state',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('chat_id', sa.INTEGER(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('current_state', sa.VARCHAR(), nullable=True),
    sa.Column('staff_type', sa.VARCHAR(length=9), nullable=True),
    sa.Column('message_id', sa.INTEGER(), nullable=True),
    sa.Column('group_id', sa.INTEGER(), nullable=True),
    sa.Column('username', sa.VARCHAR(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('chat_id', 'user_id', name='unique_state')
    )
    op.create_table('simple_check_box_button',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('creation_date', sa.DATETIME(), nullable=False),
    sa.Column('callback_data', sa.BLOB(), nullable=False),
    sa.Column('answer', sa.BOOLEAN(), nullable=True),
    sa.Column('unchecked_prefix', sa.VARCHAR(), nullable=False),
    sa.Column('checked_prefix', sa.VARCHAR(), nullable=False),
    sa.Column('is_checked', sa.BOOLEAN(), nullable=False),
    sa.Column('arg', sa.VARCHAR(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('callback_data')
    )
    op.drop_table('text')
    op.drop_table('tab')
    op.drop_table('pyrogram_button')
    op.drop_table('group_tab')
    op.drop_table('group_stats_tab')
    op.drop_table('group_stats_date_time_range_selection_tab')
    op.drop_table('group_add_staff_tab')
    op.drop_table('check_box_button')
    op.drop_table('window')
    # ### end Alembic commands ###
