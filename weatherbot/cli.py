import sys


def main(argv=None, runtime=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    runtime = runtime
    if runtime is None:
        import bot_v2 as runtime  # pragma: no cover

    if argv and argv[0] == "status":
        runtime.print_status()
    elif argv and argv[0] == "report":
        runtime.print_report()
    else:
        runtime.run_loop()
