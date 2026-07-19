from fluidsender_addon.sanitize import sanitize_filename, sanitize_folder


def test_filename_allows_safe_characters() -> None:
    assert sanitize_filename("part1.nc") == "part1.nc"
    assert sanitize_filename("Part-1_v2.nc") == "Part-1_v2.nc"


def test_filename_replaces_disallowed_characters() -> None:
    assert sanitize_filename("part #1.nc") == "part__1.nc"
    assert sanitize_filename("a/b.nc") == "a_b.nc"
    assert sanitize_filename("café.nc") == "caf_.nc"


def test_filename_empty_string() -> None:
    assert sanitize_filename("") == ""


def test_folder_sanitizes_each_segment() -> None:
    assert sanitize_folder("jobs/panels") == "jobs/panels"
    assert sanitize_folder("jobs/panel #1") == "jobs/panel__1"


def test_folder_drops_empty_segments() -> None:
    assert sanitize_folder("/jobs/panels/") == "jobs/panels"
    assert sanitize_folder("jobs//panels") == "jobs/panels"
    assert sanitize_folder("") == ""
    assert sanitize_folder("///") == ""
