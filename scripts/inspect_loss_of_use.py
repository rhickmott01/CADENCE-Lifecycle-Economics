"""Read-only audit of one HAZUS partition; optionally save an immutable JSON record."""
import argparse
import json
from pathlib import Path

from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.hazus import inspect_loss_of_use_partition


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("partition",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    report=inspect_loss_of_use_partition(str(args.partition))
    payload=json.dumps(report,indent=2,sort_keys=True)+"\n"
    if args.output:
        root=Path(__file__).resolve().parents[1]
        output=args.output.resolve()
        if not output.is_relative_to(root):
            raise ContractViolationError("Inspection output must stay inside the lifecycle repository")
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open("x") as destination:
            destination.write(payload)
        print(f"Inspection saved: {output}")
    else:
        print(payload)


if __name__=="__main__":
    main()
