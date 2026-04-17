from datetime import datetime
from domain.models.split_config import SplitGroup, SharedAccountConfig


def test_split_group_add_alias():
    group = SplitGroup(telegram_id=123, category_id="cat1", category_name="Gastos Compartidos")
    
    group.add_alias("Juan")
    assert "Juan" in group.person_aliases
    
    # Case-insensitive dedup
    group.add_alias("Juan")
    assert len(group.person_aliases) == 1
    
    group.add_alias(" Juancho ")
    assert "Juancho" in group.person_aliases
    assert len(group.person_aliases) == 2


def test_split_group_remove_alias():
    group = SplitGroup(
        telegram_id=123, 
        category_id="cat1", 
        category_name="Gastos Compartidos",
        person_aliases=["Juan", "Juancho"]
    )
    
    assert group.remove_alias("Juan") is True
    assert "Juan" not in group.person_aliases
    assert len(group.person_aliases) == 1
    
    assert group.remove_alias("Unknown") is False
    assert len(group.person_aliases) == 1


def test_split_group_matches_alias():
    group = SplitGroup(
        telegram_id=123, 
        category_id="cat1", 
        category_name="Gastos Compartidos",
        person_aliases=["Juan", "Juancho"]
    )
    
    assert group.matches_alias("Juan") is True
    assert group.matches_alias("Juancho") is True
    assert group.matches_alias(" Juan ") is True  # strip before matching
    assert group.matches_alias("Pedro") is False


def test_split_group_empty_alias():
    group = SplitGroup(telegram_id=123, category_id="cat1", category_name="Gastos Compartidos")
    group.add_alias("")
    group.add_alias("   ")
    assert len(group.person_aliases) == 0


def test_shared_account_config_creation():
    now = datetime.now()
    config = SharedAccountConfig(
        telegram_id=123,
        account_id="acc1",
        account_name="Shared Account",
        created_at=now,
        updated_at=now
    )
    
    assert config.telegram_id == 123
    assert config.account_id == "acc1"
    assert config.account_name == "Shared Account"
    assert config.created_at == now
    assert config.updated_at == now
