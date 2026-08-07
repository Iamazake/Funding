from app.cli import build_parser


def test_force_flag_is_explicit() -> None:
    regular = build_parser().parse_args(["sync-operational-excel"])
    forced = build_parser().parse_args(["sync-operational-excel", "--force"])
    assert regular.force is False
    assert forced.force is True
