from fluidsender_addon.config import InstanceConfig, InstanceStore, new_instance_id
from tests.fakes import FakeParameterGroup


def make_store() -> InstanceStore:
    return InstanceStore(FakeParameterGroup())


def test_list_instances_empty_initially() -> None:
    store = make_store()
    assert store.list_instances() == []


def test_save_and_list_instance() -> None:
    store = make_store()
    instance = InstanceConfig(
        id=new_instance_id(),
        label="Shop FluidSender",
        url="http://fluidsender.local:3000",
        token="fst_abc",
    )
    store.save_instance(instance)

    listed = store.list_instances()
    assert len(listed) == 1
    assert listed[0] == instance


def test_save_instance_overwrites_by_id() -> None:
    store = make_store()
    instance_id = new_instance_id()
    store.save_instance(
        InstanceConfig(id=instance_id, label="Old Label", url="http://a", token="t1")
    )
    store.save_instance(
        InstanceConfig(id=instance_id, label="New Label", url="http://a", token="t2")
    )

    listed = store.list_instances()
    assert len(listed) == 1
    assert listed[0].label == "New Label"
    assert listed[0].token == "t2"


def test_delete_instance() -> None:
    store = make_store()
    instance = InstanceConfig(id=new_instance_id(), label="A", url="http://a", token="t")
    store.save_instance(instance)
    store.delete_instance(instance.id)

    assert store.list_instances() == []


def test_last_selected_round_trips() -> None:
    store = make_store()
    instance = InstanceConfig(id=new_instance_id(), label="A", url="http://a", token="t")
    store.save_instance(instance)
    store.set_last_selected_id(instance.id)

    assert store.get_last_selected_id() == instance.id
    assert store.get_last_selected() == instance


def test_last_selected_none_when_never_set() -> None:
    store = make_store()
    assert store.get_last_selected_id() is None
    assert store.get_last_selected() is None


def test_last_selected_falls_back_to_none_when_instance_deleted() -> None:
    store = make_store()
    instance = InstanceConfig(id=new_instance_id(), label="A", url="http://a", token="t")
    store.save_instance(instance)
    store.set_last_selected_id(instance.id)

    store.delete_instance(instance.id)

    assert store.get_last_selected_id() is None
    assert store.get_last_selected() is None


def test_deleting_a_different_instance_keeps_last_selected() -> None:
    store = make_store()
    kept = InstanceConfig(id=new_instance_id(), label="Kept", url="http://a", token="t")
    other = InstanceConfig(id=new_instance_id(), label="Other", url="http://b", token="t2")
    store.save_instance(kept)
    store.save_instance(other)
    store.set_last_selected_id(kept.id)

    store.delete_instance(other.id)

    assert store.get_last_selected_id() == kept.id
