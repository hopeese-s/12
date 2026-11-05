"""One-shot conversion worker.

Run as:  python -m app.convert_worker <job_file> <result_file>

The job file holds a pickled (function_name, kwargs) for one function in
app.converter. The worker runs it, writes a pickled ("ok", result) or
("err", message) to the result file, and exits. Every byte PyMuPDF / Pillow
allocated goes back to the OS when this process ends, so the long-running
web server never grows from conversions.
"""
import pickle
import sys


def main() -> int:
    job_path, result_path = sys.argv[1], sys.argv[2]
    with open(job_path, "rb") as f:
        fn_name, kwargs = pickle.load(f)
    try:
        from app import converter
        fn = getattr(converter, fn_name)
        out = ("ok", fn(**kwargs))
    except Exception as e:  # report to the parent as a normal error
        out = ("err", str(e) or e.__class__.__name__)
    with open(result_path, "wb") as f:
        pickle.dump(out, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
