import sys


def main(argv=None, runtime=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if runtime is None:
        from weatherbot import load_cal, print_report, print_replay, print_status, run_loop
    else:
        load_cal = runtime.load_cal
        print_report = runtime.print_report
        print_replay = runtime.print_replay
        print_status = runtime.print_status
        run_loop = runtime.run_loop

    cmd = argv[0] if argv else "run"
    if cmd == "run":
        run_loop()
    elif cmd == "status":
        runtime._cal = load_cal() if runtime is not None else load_cal()
        print_status()
    elif cmd == "report":
        runtime._cal = load_cal() if runtime is not None else load_cal()
        print_report()
    elif cmd == "replay":
        limit = 5
        market_filter = None
        order_filter = None
        idx = 1
        while idx < len(argv):
            token = argv[idx]
            if token == "--limit" and idx + 1 < len(argv):
                limit = int(argv[idx + 1])
                idx += 2
            elif token == "--market" and idx + 1 < len(argv):
                market_filter = argv[idx + 1]
                idx += 2
            elif token == "--order" and idx + 1 < len(argv):
                order_filter = argv[idx + 1]
                idx += 2
            else:
                raise SystemExit(f"Unknown replay arg: {token}")
        print_replay(limit=limit, market_filter=market_filter, order_filter=order_filter)
    else:
        print(f"Unknown command: {cmd}")
        raise SystemExit(1)
