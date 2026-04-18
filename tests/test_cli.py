import pytest

from weatherbot import cli


class RuntimeStub:
    def __init__(self):
        self.calls = []
        self._cal = None

    def load_cal(self):
        self.calls.append(("load_cal",))
        return {"sigma": 1.23}

    def run_loop(self):
        self.calls.append(("run_loop",))

    def print_status(self):
        self.calls.append(("print_status", self._cal))

    def print_report(self):
        self.calls.append(("print_report", self._cal))

    def print_replay(self, limit=5, market_filter=None, order_filter=None):
        self.calls.append(("print_replay", limit, market_filter, order_filter))


@pytest.mark.parametrize(
    ("argv", "expected_calls"),
    [
        ([], [("run_loop",)]),
        (["run"], [("run_loop",)]),
        (["status"], [("load_cal",), ("print_status", {"sigma": 1.23})]),
        (["report"], [("load_cal",), ("print_report", {"sigma": 1.23})]),
        (
            ["replay", "--limit", "9", "--market", "nyc", "--order", "filled"],
            [("print_replay", 9, "nyc", "filled")],
        ),
    ],
)
def test_main_dispatches_runtime_commands(argv, expected_calls):
    runtime = RuntimeStub()

    cli.main(argv, runtime=runtime)

    assert runtime.calls == expected_calls


def test_main_rejects_unknown_command_with_nonzero_exit():
    runtime = RuntimeStub()

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["wat"], runtime=runtime)

    assert excinfo.value.code == 1


def test_main_rejects_unknown_replay_args_with_nonzero_exit():
    runtime = RuntimeStub()

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["replay", "--bogus"], runtime=runtime)

    assert excinfo.value.code == 1
