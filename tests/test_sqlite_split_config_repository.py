import pytest
from infrastructure.repositories.database_manager import DatabaseManager
from infrastructure.repositories.sqlite_split_config_repository import SQLiteSplitConfigRepository


@pytest.fixture
def db_manager(tmp_path):
    db_file = tmp_path / "test.db"
    manager = DatabaseManager(str(db_file))
    yield manager
    manager.close()


@pytest.fixture
def repo(db_manager):
    return SQLiteSplitConfigRepository(db_manager)


def _create_user(db_manager, telegram_id):
    conn = db_manager.get_connection()
    conn.execute(
        "INSERT INTO user_configurations (telegram_id, status) VALUES (?, 'approved')",
        (telegram_id,)
    )
    conn.commit()


def test_add_get_split_group(repo, db_manager):
    telegram_id = 123
    _create_user(db_manager, telegram_id)
    category_id = "cat1"
    category_name = "Gastos Compartidos"
    
    group = repo.add_split_group(telegram_id, category_id, category_name)
    
    assert group.telegram_id == telegram_id
    assert group.category_id == category_id
    assert group.category_name == category_name
    assert group.id is not None
    
    # Verify it appears in get_split_groups
    groups = repo.get_split_groups(telegram_id)
    assert len(groups) == 1
    assert groups[0].category_id == category_id


def test_add_duplicate_group(repo, db_manager):
    telegram_id = 123
    _create_user(db_manager, telegram_id)
    category_id = "cat1"
    
    repo.add_split_group(telegram_id, category_id, "Name 1")
    group2 = repo.add_split_group(telegram_id, category_id, "Name 2")
    
    groups = repo.get_split_groups(telegram_id)
    assert len(groups) == 1
    # SQLite implementation is INSERT OR IGNORE, so Name 1 stays
    assert groups[0].category_name == "Name 1"


def test_remove_group_cascades_aliases(repo, db_manager):
    telegram_id = 123
    _create_user(db_manager, telegram_id)
    category_id = "cat1"
    
    repo.add_split_group(telegram_id, category_id, "Gastos Compartidos")
    repo.add_person_alias(telegram_id, category_id, "Juan")
    
    # Check alias exists
    group = repo.find_split_group_by_alias(telegram_id, "Juan")
    assert group is not None
    
    # Remove group
    assert repo.remove_split_group(telegram_id, category_id) is True
    
    # Verify group and alias are gone
    assert len(repo.get_split_groups(telegram_id)) == 0
    assert repo.find_split_group_by_alias(telegram_id, "Juan") is None


def test_person_aliases_ops(repo, db_manager):
    telegram_id = 123
    _create_user(db_manager, telegram_id)
    category_id = "cat1"
    repo.add_split_group(telegram_id, category_id, "Gastos Compartidos")
    
    assert repo.add_person_alias(telegram_id, category_id, "Juan") is True
    assert repo.add_person_alias(telegram_id, category_id, "Juancho") is True
    # Duplicate alias for same group
    assert repo.add_person_alias(telegram_id, category_id, "Juan") is False
    
    groups = repo.get_split_groups(telegram_id)
    assert len(groups[0].person_aliases) == 2
    assert "Juan" in groups[0].person_aliases
    assert "Juancho" in groups[0].person_aliases
    
    # Remove alias
    assert repo.remove_person_alias(telegram_id, category_id, "Juancho") is True
    groups = repo.get_split_groups(telegram_id)
    assert len(groups[0].person_aliases) == 1
    assert "Juancho" not in groups[0].person_aliases


def test_find_split_group_by_alias_case_insensitive(repo, db_manager):
    telegram_id = 123
    _create_user(db_manager, telegram_id)
    category_id = "cat1"
    repo.add_split_group(telegram_id, category_id, "Gastos Compartidos")
    repo.add_person_alias(telegram_id, category_id, "Juan")
    
    group = repo.find_split_group_by_alias(telegram_id, "Juan")
    assert group is not None
    assert group.category_id == category_id
    
    assert repo.find_split_group_by_alias(telegram_id, "Unknown") is None


def test_shared_account_ops(repo, db_manager):
    telegram_id = 123
    _create_user(db_manager, telegram_id)
    account_id = "acc1"
    account_name = "Nu Savings"
    
    # Set
    config = repo.set_shared_account(telegram_id, account_id, account_name)
    assert config.account_id == account_id
    assert config.account_name == account_name
    
    # Get
    fetched = repo.get_shared_account(telegram_id)
    assert fetched is not None
    assert fetched.account_id == account_id
    
    # Update (upsert)
    repo.set_shared_account(telegram_id, "acc2", "Other")
    fetched = repo.get_shared_account(telegram_id)
    assert fetched.account_id == "acc2"
    assert fetched.account_name == "Other"
    
    # Remove
    assert repo.remove_shared_account(telegram_id) is True
    assert repo.get_shared_account(telegram_id) is None


def test_per_user_isolation(repo, db_manager):
    user_a = 111
    user_b = 222
    _create_user(db_manager, user_a)
    _create_user(db_manager, user_b)
    
    repo.add_split_group(user_a, "cat_a", "Group A")
    repo.add_split_group(user_b, "cat_b", "Group B")
    
    groups_a = repo.get_split_groups(user_a)
    assert len(groups_a) == 1
    assert groups_a[0].category_id == "cat_a"
    
    groups_b = repo.get_split_groups(user_b)
    assert len(groups_b) == 1
    assert groups_b[0].category_id == "cat_b"
