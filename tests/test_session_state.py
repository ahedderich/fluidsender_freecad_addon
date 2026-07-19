from fluidsender_addon.session_state import DialogSessionState


def test_defaults() -> None:
    state = DialogSessionState()
    assert state.last_folder == ""
    assert state.last_filename is None
    assert state.last_unchecked_operation_names == set()


def test_fields_are_mutable_independently() -> None:
    state = DialogSessionState()
    state.last_folder = "jobs/panels"
    state.last_filename = "part1.nc"

    assert state.last_folder == "jobs/panels"
    assert state.last_filename == "part1.nc"


def test_unchecked_operation_names_default_is_independent_per_instance() -> None:
    a = DialogSessionState()
    b = DialogSessionState()
    a.last_unchecked_operation_names.add("Drill")

    assert a.last_unchecked_operation_names == {"Drill"}
    assert b.last_unchecked_operation_names == set()
