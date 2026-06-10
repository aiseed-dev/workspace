from kura.fscheck import check_tar, measure_group_capacity, run


def test_capacity_measured(tmp_path):
    cap = measure_group_capacity(tmp_path)
    # 上限があるなら数十以上（spec の対象規模に足りる）、ないなら None
    if cap["capacity"] is not None:
        assert cap["capacity"] >= 30
        assert cap["atomic_on_overflow"] is True


def test_tar_preserves_xattrs(tmp_path):
    assert check_tar(tmp_path) is not False


def test_run_reports_all_keys(tmp_path):
    r = run(tmp_path)
    assert set(r) == {"path", "group_capacity_per_dir", "atomic_on_overflow",
                      "tar_xattrs_ok", "rsync_X_ok"}
